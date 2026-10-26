"""Hugging Face Transformers backend: the base model, optionally 4-bit, with an optional LoRA adapter.

Used on a GPU (training notebook, GPU server). Requires the ``train`` extra.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Sequence

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, DataCollatorForSeq2Seq

from ..prompts import Message
from ..training.dataset import ChatExample
from ..training.encoding import IGNORE_INDEX, ChatEncoder
from .base import ChatModel, GenerationSettings


def compute_dtype() -> torch.dtype:
    """bfloat16 where the GPU supports it, else float16 (e.g. the Colab T4)."""
    return torch.bfloat16 if torch.cuda.is_available() and torch.cuda.is_bf16_supported() else torch.float16


def load_tokenizer(name_or_path: str | Path):
    tokenizer = AutoTokenizer.from_pretrained(str(name_or_path))
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    return tokenizer


def attention_implementation(name_or_path: str | Path) -> str | None:
    """Gemma 2 and 3 cap their attention scores ("soft-capping"), which only the eager attention code
    computes exactly; Google recommends it for fine-tuning. Other models use the library default."""
    return "eager" if "gemma" in str(name_or_path).lower() else None


def load_causal_lm(name_or_path: str | Path, quantize_4bit: bool = True):
    """Load a causal LM, as 4-bit NF4 (QLoRA) on a GPU or in float32 on a CPU."""
    attention = {"attn_implementation": impl} if (impl := attention_implementation(name_or_path)) else {}
    if not torch.cuda.is_available():
        return AutoModelForCausalLM.from_pretrained(str(name_or_path), dtype=torch.float32, **attention)
    dtype = compute_dtype()
    quantization = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=dtype,
    ) if quantize_4bit else None
    return AutoModelForCausalLM.from_pretrained(
        str(name_or_path), quantization_config=quantization, device_map={"": 0}, dtype=dtype, **attention
    )


class TransformersChatModel(ChatModel):
    """Batched greedy generation and answer perplexity for a (possibly adapted) causal LM."""

    def __init__(self, model, tokenizer, settings: GenerationSettings | None = None, name: str = "transformers") -> None:
        super().__init__(settings)
        self.model = model
        self.tokenizer = tokenizer
        self.encoder = ChatEncoder(tokenizer)
        self.name = name

    @classmethod
    def from_pretrained(cls, base_model: str, adapter_path: str | Path | None = None, quantize_4bit: bool = True,
                        settings: GenerationSettings | None = None) -> "TransformersChatModel":
        model = load_causal_lm(base_model, quantize_4bit)
        tokenizer = load_tokenizer(adapter_path or base_model)
        name = base_model
        if adapter_path is not None:
            from peft import PeftModel

            model = PeftModel.from_pretrained(model, str(adapter_path))
            name = f"{base_model} + {Path(adapter_path).name}"
        return cls(model, tokenizer, settings, name)

    @torch.no_grad()
    def generate_batch(self, conversations: Sequence[Sequence[Message]]) -> list[str]:
        self.model.eval()
        self.model.config.use_cache = True
        self.tokenizer.padding_side = "left"  # generation continues from the right edge of every row
        prompts = [self.encoder.render_prompt(conversation) for conversation in conversations]
        # Batching prompts of similar length wastes less compute on padding.
        order = sorted(range(len(prompts)), key=lambda i: len(prompts[i]))
        replies: list[str] = [""] * len(prompts)
        for start in range(0, len(order), self.settings.batch_size):
            indices = order[start:start + self.settings.batch_size]
            batch = self.tokenizer([prompts[i] for i in indices], return_tensors="pt", padding=True,
                                   add_special_tokens=False).to(self.model.device)
            output = self.model.generate(
                **batch,
                max_new_tokens=self.settings.max_new_tokens,
                do_sample=False,
                repetition_penalty=self.settings.repetition_penalty,
                no_repeat_ngram_size=self.settings.no_repeat_ngram_size,
                pad_token_id=self.tokenizer.pad_token_id,
            )
            new_tokens = output[:, batch["input_ids"].shape[1]:]
            for i, tokens in zip(indices, new_tokens):
                replies[i] = self.tokenizer.decode(tokens, skip_special_tokens=True).strip()
        return replies

    @torch.no_grad()
    def perplexity(self, examples: Sequence[ChatExample], batch_size: int = 4) -> float:
        """exp(mean negative log-likelihood) of the reference answer tokens, given the prompt."""
        self.model.eval()
        self.tokenizer.padding_side = "right"
        collate = DataCollatorForSeq2Seq(self.tokenizer, padding=True, label_pad_token_id=IGNORE_INDEX)
        encoded = [self.encoder.encode(example) for example in examples]
        total_nll, total_tokens = 0.0, 0
        for start in range(0, len(encoded), batch_size):
            batch = {k: v.to(self.model.device) for k, v in collate(encoded[start:start + batch_size]).items()}
            logits = self.model(input_ids=batch["input_ids"], attention_mask=batch["attention_mask"]).logits
            # Token t is predicted from position t-1, so shift labels left by one, and keep only
            # answer positions: the full vocabulary-sized logits in float32 would not fit on a T4.
            labels = batch["labels"][:, 1:]
            answer = labels != IGNORE_INDEX
            nll = torch.nn.functional.cross_entropy(logits[:, :-1][answer].float(), labels[answer], reduction="sum")
            total_nll += nll.item()
            total_tokens += answer.sum().item()
        return math.exp(total_nll / total_tokens)
