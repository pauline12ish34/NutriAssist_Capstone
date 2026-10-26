"""The interface every answer generator implements.

Evaluation, the API and the tests depend only on :class:`ChatModel`, so the GPU
model, the CPU (GGUF) model and the scripted test double are interchangeable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence

from ..prompts import Message


@dataclass(frozen=True)
class GenerationSettings:
    max_new_tokens: int = 320
    repetition_penalty: float = 1.05   # mild: stops loops in long Kinyarwanda answers without changing wording
    no_repeat_ngram_size: int = 0      # >0 forbids repeating any n-token sequence (Transformers only); 0 = off
    batch_size: int = 8


class ChatModel(ABC):
    """Generates an assistant reply for a conversation (system + user messages)."""

    name: str = "chat-model"

    def __init__(self, settings: GenerationSettings | None = None) -> None:
        self.settings = settings or GenerationSettings()

    @abstractmethod
    def generate_batch(self, conversations: Sequence[Sequence[Message]]) -> list[str]:
        """One reply per conversation, in the same order. Decoding is greedy, so replies are reproducible."""

    def generate(self, messages: Sequence[Message]) -> str:
        return self.generate_batch([messages])[0]
