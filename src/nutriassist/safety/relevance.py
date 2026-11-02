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

import re
from typing import Callable, Sequence

import numpy as np

Embedder = Callable[[Sequence[str]], np.ndarray]

# A question is in scope when it is very close to a reviewed question, or fairly close and uses a word of
# the domain (child, feed, umwana, konsa...). Out-of-domain questions translated by Gemini scored 0.66-0.67
# ("When will the elections be held in Rwanda?") and "What is the capital of Kenya?" 0.71, while short
# nutrition questions ("I give the child rice") scored 0.61: the score alone cannot separate them.
# On the calibration data (scripts/calibrate_checks.py) this keeps 97% of English and 95% of Kinyarwanda
# held-out questions and declines all 26 out-of-scope ones (a single 0.62 threshold: 91% / 98%, and 85%).
SCOPE_THRESHOLD = 0.75        # close enough on its own
DOMAIN_SCOPE_THRESHOLD = 0.50  # close enough when the question uses a domain word
# Question vs the answer. 0.27 kept 97% of reviewed answers but also blocked good model answers, which
# match the question more loosely ("My 2-year-old refuses vegetables" vs a sound answer: 0.21). 0.18 keeps
# every reviewed English answer and still blocks 23% of answers from another category; out-of-domain
# questions are stopped by the scope check above, before the model.
ANSWER_THRESHOLD = 0.18

DOMAIN = re.compile(
    r"\b(?:child|children|baby|babies|infant|toddler|newborn|kid|son|daughter|"
    r"food|foods|eat|eats|eating|feed|feeds|feeding|meal|meals|diet|nutrition|nutrient|nourish\w*|malnutrition|"
    r"malnourished|appetite|hungry|breastfe\w*|breast|milk|formula|porridge|pregnan\w*|mother|mum|mom|lactat\w*|"
    r"weight|growth|stunt\w*|wasting|muac|vitamin\w*|iron|zinc|calcium|protein|deworm\w*|hypothermia|"
    r"cook\w*|portion|snack\w*|drink\w*|water|"
    r"umwana|abana|uruhinja|impinja|akana|utwana|kurya|arya|ibiryo|indyo|imirire|amafunguro|ifunguro|konsa|yonsa|"
    r"amashereka|amata|utwite|batwite|umubyeyi|ababyeyi|gukura|ibiro|igikoma|guteka|kunywa)\b", re.IGNORECASE)


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
        score = self.scope_score(question)
        return score >= self.scope_threshold or (score >= DOMAIN_SCOPE_THRESHOLD and bool(DOMAIN.search(question)))

    def on_topic(self, question: str, answer: str) -> bool:
        return self.answer_score(question, answer) >= self.answer_threshold
