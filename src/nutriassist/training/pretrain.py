"""Continued pre-training: more Kinyarwanda for the base model, before the nutrition fine-tune.

181 Kinyarwanda training pairs teach the assistant's style but cannot teach the language
(``docs/kinyarwanda.md``). This step first trains LoRA adapters on plain Kinyarwanda text (predicting
every next token), then merges them into the base weights. The merged model is the base model of an
ordinary fine-tuning experiment, so the rest of the notebook treats it like Qwen or Gemma.

Like fine-tuning, training resumes from its last checkpoint after a Colab disconnect. The adapter
(small) is saved to Drive; the merged model (as large as the base model) is rebuilt from it on the
Colab disk whenever it is missing. Requires a CUDA GPU and the ``train`` extra.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

import torch
from transformers import Trainer, TrainingArguments, default_data_collator, set_seed
from transformers.trainer_utils import get_last_checkpoint

from ..inference.transformers_model import compute_dtype, load_causal_lm, load_tokenizer
from .config import TRAINING_SUMMARY_FILE
from .corpus import KINYARWANDA_CORPUS, clean_passages, pack_blocks, sample_runs
from .finetune import PROGRESS_FILE, _ProgressCallback, free_gpu_memory, qlora_model

MERGED_MARKER = "merge_complete"
TOKENS_PER_ROW = 50   # a corpus row is a ~30-word paragraph (~80 tokens); a low guess leaves rows to spare


@dataclass(frozen=True)
class PretrainConfig:
    name: str
    base_model: str
    corpus: str = KINYARWANDA_CORPUS
    token_budget: int = 5_000_000      # about 45 minutes for Gemma 3 4B on an L4
    block_size: int = 512
    learning_rate: float = 1e-4        # lower than fine-tuning: adapt the language, keep what the model knows
    lora_rank: int = 64                # more capacity than the fine-tune: a language, not a style
    lora_dropout: float = 0.0
    batch_size: int = 4
    grad_accum: int = 8
    warmup_ratio: float = 0.03
    eval_blocks: int = 64              # held-out corpus blocks for the validation loss
    save_steps: int = 25
    seed: int = 42

    @property
    def lora_alpha(self) -> int:
        return self.lora_rank

    @property
    def max_blocks(self) -> int:
        return self.token_budget // self.block_size + self.eval_blocks


class ContinuedPretrainer:
    def __init__(self, config: PretrainConfig, output_dir: str | Path, checkpoints_dir: str | Path,
                 merged_root: str | Path = "/content") -> None:
        if not torch.cuda.is_available():
            raise RuntimeError("Continued pre-training needs a CUDA GPU. In Colab: Runtime > Change runtime type > L4.")
        self.config = config
        self.adapter_dir = Path(output_dir) / "pretrain" / config.name
        self.checkpoint_dir = Path(checkpoints_dir) / config.name
        self.merged_dir = Path(merged_root) / f"{config.name}-merged"

    @property
    def summary_path(self) -> Path:
        return self.adapter_dir / TRAINING_SUMMARY_FILE

    def is_trained(self) -> bool:
        return self.summary_path.exists()

    def summary(self) -> dict:
        return json.loads(self.summary_path.read_text())

    def load_passages(self, held_out: Sequence[str]) -> list[str]:
        """Clean Kinyarwanda passages from the corpus, enough for the token budget."""
        from datasets import load_dataset  # imported here: only this step needs it

        cfg = self.config
        corpus = load_dataset(cfg.corpus, split="train")
        rows = corpus.select(sample_runs(len(corpus), cfg.token_budget // TOKENS_PER_ROW, seed=cfg.seed))["text"]
        return list(clean_passages(rows, held_out))

    def train(self, passages: Sequence[str]) -> dict:
        if self.is_trained():
            print(f"[{self.config.name}] already trained; using the saved adapter")
            return self.summary()
        cfg = self.config
        set_seed(cfg.seed)
        tokenizer = load_tokenizer(cfg.base_model)
        token_lists = tokenizer(list(passages), add_special_tokens=False)["input_ids"]
        blocks = pack_blocks(token_lists, cfg.block_size, tokenizer.eos_token_id, cfg.max_blocks)
        if len(blocks) <= cfg.eval_blocks:
            raise ValueError(f"Only {len(blocks)} blocks of text: load more passages")
        as_examples = [{"input_ids": b, "attention_mask": [1] * len(b), "labels": b} for b in blocks]
        val_data, train_data = as_examples[:cfg.eval_blocks], as_examples[cfg.eval_blocks:]
        print(f"[{cfg.name}] {len(passages)} passages -> {len(train_data)} training blocks "
              f"of {cfg.block_size} tokens ({len(train_data) * cfg.block_size / 1e6:.1f}M tokens)")

        free_gpu_memory()
        torch.cuda.reset_peak_memory_stats()
        model = qlora_model(cfg.base_model, cfg.lora_rank, cfg.lora_alpha, cfg.lora_dropout)
        resume_from = get_last_checkpoint(str(self.checkpoint_dir)) if self.checkpoint_dir.is_dir() else None
        progress_path = self.checkpoint_dir / PROGRESS_FILE
        previous = json.loads(progress_path.read_text()) if resume_from and progress_path.exists() else {}
        if resume_from:
            print(f"[{cfg.name}] resuming from {Path(resume_from).name}")
        progress = _ProgressCallback(progress_path, previous, on_gpu=True)

        trainer = Trainer(model=model, args=self._training_arguments(len(train_data)), train_dataset=train_data,
                          eval_dataset=val_data, data_collator=default_data_collator, callbacks=[progress])
        trainer.train(resume_from_checkpoint=resume_from)
        val_loss = trainer.evaluate()["eval_loss"]
        totals = progress.totals()

        self.adapter_dir.mkdir(parents=True, exist_ok=True)
        model.save_pretrained(self.adapter_dir)
        history = trainer.state.log_history
        (self.adapter_dir / "log_history.json").write_text(json.dumps(history, indent=2))
        train_losses = [h["loss"] for h in history if "loss" in h]
        summary = {
            **asdict(cfg),
            "passages": len(passages),
            "train_tokens_M": round(len(train_data) * cfg.block_size / 1e6, 2),
            "train_minutes": round(totals["seconds"] / 60, 1),
            "sessions": totals["sessions"],
            "peak_gpu_reserved_GB": round(totals["peak_reserved_gb"], 2),
            "first_train_loss": train_losses[0] if train_losses else None,
            "last_train_loss": train_losses[-1] if train_losses else None,
            "val_loss": round(val_loss, 4),
        }
        # Written last: its presence means the adapter is complete and never needs training again.
        self.summary_path.write_text(json.dumps(summary, indent=2))
        shutil.rmtree(self.checkpoint_dir, ignore_errors=True)
        del trainer, model
        free_gpu_memory()
        return summary

    def merged_model(self) -> Path:
        """Folder with the base model and the trained adapter merged into one model; built if missing."""
        if (self.merged_dir / MERGED_MARKER).exists():
            return self.merged_dir
        if not self.is_trained():
            raise FileNotFoundError(f"Train {self.config.name} first: no finished adapter in {self.adapter_dir}")
        from peft import PeftModel

        shutil.rmtree(self.merged_dir, ignore_errors=True)
        base = load_causal_lm(self.config.base_model, quantize_4bit=False)   # merging needs unquantised weights
        merged = PeftModel.from_pretrained(base, self.adapter_dir).merge_and_unload()
        merged.save_pretrained(self.merged_dir)
        load_tokenizer(self.config.base_model).save_pretrained(self.merged_dir)
        (self.merged_dir / MERGED_MARKER).write_text(self.config.name)
        del merged, base
        free_gpu_memory()
        return self.merged_dir

    def _training_arguments(self, num_blocks: int) -> TrainingArguments:
        cfg = self.config
        dtype = compute_dtype()
        steps = -(-num_blocks // (cfg.batch_size * cfg.grad_accum))
        return TrainingArguments(
            output_dir=str(self.checkpoint_dir),
            per_device_train_batch_size=cfg.batch_size,
            per_device_eval_batch_size=cfg.batch_size,
            gradient_accumulation_steps=cfg.grad_accum,
            learning_rate=cfg.learning_rate,
            num_train_epochs=1,             # each block is seen once: plenty of text, no need to repeat it
            lr_scheduler_type="cosine",
            warmup_steps=max(1, round(cfg.warmup_ratio * steps)),
            optim="paged_adamw_8bit",
            fp16=dtype == torch.float16,
            bf16=dtype == torch.bfloat16,
            gradient_checkpointing=True,
            gradient_checkpointing_kwargs={"use_reentrant": False},
            logging_steps=10,
            eval_strategy="no",             # evaluated once at the end
            save_strategy="steps",
            save_steps=cfg.save_steps,
            save_total_limit=1,
            report_to="none",
            seed=cfg.seed,
        )
