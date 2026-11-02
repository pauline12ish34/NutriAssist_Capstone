"""Checks on every model answer: is the question within the app's topics, and is the answer about it?

The model can answer the wrong question (asked about anaemia, it answered about breast milk; asked about
vaccines, about brain development) and can answer questions the app was never meant for. Neither check
needs the model: both compare meanings with LaBSE, which places English and Kinyarwanda in one space.

- :meth:`RelevanceChecker.in_scope`: the question is close in meaning to at least one reviewed question.
- :meth:`RelevanceChecker.on_topic`: the answer is close in meaning to the question. In the translation
  route this runs on the English question and answer, before translating back, so a blocked answer
  costs no second Gemini request.

When a check fails the app does not guess: it says it has no checked answer and offers the closest
reviewed questions. Thresholds come from ``scripts/calibrate_checks.py`` (no model and no Gemini calls):
each keeps about 95% of the good cases it was calibrated on.
"""

from __future__ import annotations

from typing import Callable, Sequence

import numpy as np

Embedder = Callable[[Sequence[str]], np.ndarray]

SCOPE_THRESHOLD = 0.62    # question vs the closest reviewed question: keeps 94% in scope, declines 85% out
ANSWER_THRESHOLD = 0.27   # question vs the answer: keeps 95% right, blocks 64% (en) / 32% (rw) wrong-topic


class RelevanceChecker:
    def __init__(self, embedder: Embedder, reviewed_questions: Sequence[str],
                 scope_threshold: float = SCOPE_THRESHOLD, answer_threshold: float = ANSWER_THRESHOLD) -> None:
        self.embedder = embedder
        self.questions = embedder(list(reviewed_questions))
        self.scope_threshold = scope_threshold
        self.answer_threshold = answer_threshold

    def scope_score(self, question: str) -> float:
        return float(np.max(self.questions @ self.embedder([question])[0]))

    def answer_score(self, question: str, answer: str) -> float:
        q, a = self.embedder([question, answer])
        return float(q @ a)

    def in_scope(self, question: str) -> bool:
        return self.scope_score(question) >= self.scope_threshold

    def on_topic(self, question: str, answer: str) -> bool:
        return self.answer_score(question, answer) >= self.answer_threshold
