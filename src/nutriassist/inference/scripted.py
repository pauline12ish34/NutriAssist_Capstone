"""A deterministic stand-in model for tests and for running the app without a GPU or model file."""

from __future__ import annotations

from typing import Callable, Sequence

from ..prompts import Message
from .base import ChatModel, GenerationSettings

Responder = Callable[[str], str]


class ScriptedChatModel(ChatModel):
    """Answers with ``responder(question)``; by default it echoes the question back."""

    name = "scripted"

    def __init__(self, responder: Responder | None = None, settings: GenerationSettings | None = None) -> None:
        super().__init__(settings)
        self.responder = responder or (lambda question: f"You asked: {question}")
        self.calls: list[str] = []

    def generate_batch(self, conversations: Sequence[Sequence[Message]]) -> list[str]:
        questions = [conversation[-1]["content"] for conversation in conversations]
        self.calls.extend(questions)
        return [self.responder(question) for question in questions]
