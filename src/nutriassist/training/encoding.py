"""Turn chat examples into token ids and loss labels for causal-LM fine-tuning."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Any, Sequence

from ..prompts import Message
from .dataset import ChatExample

IGNORE_INDEX = -100  # label value that PyTorch's cross-entropy skips


@dataclass(frozen=True)
class EncodingStats:
    count: int
    median_tokens: int
    max_tokens: int
    truncated: int

    def __str__(self) -> str:
        return (f"{self.count} examples, tokens per example: median {self.median_tokens}, "
                f"max {self.max_tokens}, truncated {self.truncated}")


class ChatEncoder:
    """Renders prompts with the model's own chat template and masks the prompt out of the loss.

    Only answer tokens get real labels, so training teaches the model to answer
    rather than to reproduce the system prompt and the question.
    """

    def __init__(self, tokenizer: Any, max_length: int = 768) -> None:
        self.tokenizer = tokenizer
        self.max_length = max_length

    def render_prompt(self, messages: Sequence[Message]) -> str:
        """Template text for the system + user turns, ending where the assistant reply begins."""
        try:
            return self.tokenizer.apply_chat_template(list(messages), tokenize=False, add_generation_prompt=True)
        except Exception:
            # Some templates (e.g. Gemma's) reject a system role: fold it into the user turn.
            system, user = messages
            merged = [{"role": "user", "content": f"{system['content']}\n\n{user['content']}"}]
            return self.tokenizer.apply_chat_template(merged, tokenize=False, add_generation_prompt=True)

    def encode(self, example: ChatExample) -> dict[str, list[int]]:
        prompt_ids = self._ids(self.render_prompt(example.prompt_messages))
        answer_ids = self._ids(example.answer) + [self.tokenizer.eos_token_id]
        input_ids = (prompt_ids + answer_ids)[: self.max_length]
        labels = ([IGNORE_INDEX] * len(prompt_ids) + answer_ids)[: self.max_length]
        return {"input_ids": input_ids, "attention_mask": [1] * len(input_ids), "labels": labels}

    def encode_many(self, examples: Sequence[ChatExample]) -> tuple[list[dict[str, list[int]]], EncodingStats]:
        encoded = [self.encode(example) for example in examples]
        lengths = [len(item["input_ids"]) for item in encoded]
        stats = EncodingStats(
            count=len(encoded),
            median_tokens=int(median(lengths)),
            max_tokens=max(lengths),
            truncated=sum(length >= self.max_length for length in lengths),
        )
        return encoded, stats

    def _ids(self, text: str) -> list[int]:
        # The chat template already adds BOS where the model needs it.
        return list(self.tokenizer(text, add_special_tokens=False)["input_ids"])
