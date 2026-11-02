"""Topic rules: questions where a small model is likely to give dangerous advice get a fixed answer.

A rule fires on the **question** when it names the topic (a keyword, or, with LaBSE, a question close in
meaning to one of the rule's example questions) and, for child-only rules, the question is about a child.
It also fires on the **answer**: if the model's answer talks about the topic for a child, the answer is
replaced by the fixed one. That catches wordings the question check misses (on the Space, Gemma answered
"Yego" to tea for a 10-month-old asked as "umwana wamezi 10 yanywa icyayi").

Keywords alone catch few rewordings ("icyai", "chai", "akana", "ku bana" all slipped past the first tea
rule), so the keyword lists include spellings and words parents use, and the meaning check catches more.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Sequence

import numpy as np

from . import messages

Embedder = Callable[[Sequence[str]], np.ndarray]

# A question about a child (not about the mother). Kinyarwanda nouns with and without their prefixes.
CHILD = re.compile(
    r"\b(?:bab(?:y|ies)|child(?:ren)?|kids?|infants?|toddlers?|newborns?|son|daughter|little ones?|"
    r"\d+[- ]?(?:months?|mo)\b|months?[- ]old|year[- ]old|"
    r"u?mwana|a?bana|akana|utwana|uruhinja|ruhinja|impinja|amezi|umukobwa wanjye|umuhungu wanjye)\b",
    re.IGNORECASE,
)
# LaBSE similarity to a rule's example question. Calibrated (scripts/calibrate_checks.py) as the lowest with no
# false trigger on the other reviewed questions: 0.93 (honey), 0.96 (tea). That high, it adds little; keywords do the work.
MEANING_THRESHOLD = 0.96


@dataclass(frozen=True)
class TopicRule:
    key: str
    keywords: re.Pattern
    message: dict[str, str]
    child_only: bool = True
    examples: tuple[str, ...] = ()           # questions the rule must catch, both languages, for meaning matching
    # For the answer check: an answer that already says what the fixed message says is left alone.
    answer_ok: re.Pattern | None = None
    # What happens to a model answer on the topic: "append" the fixed message, or "replace" the answer.
    on_answer: str = "replace"


HONEY = TopicRule(
    "honey",
    re.compile(r"\bhoney\b|\bu?buki\b", re.IGNORECASE),
    messages.HONEY,
    child_only=False,      # honey is dangerous under 12 months whoever asks
    examples=(
        "Can I give honey to my baby?", "Is honey good for a baby with a cough?", "Can I sweeten porridge with honey?",
        "Nshobora guha umwana wanjye ubuki?", "Ubuki bwavura inkorora y'uruhinja?",
        "Nshyira ubuki mu gikoma cy'umwana?",   # NEEDS REVIEW: drafted by Claude
    ),
    answer_ok=re.compile(r"\b12 months\b|\b(?:1|one) year\b|\bfirst year\b|\bmezi 12\b", re.IGNORECASE),
    on_answer="append",    # honey in a recipe ("sweeten with honey or banana") keeps the rest of the advice
)

TEA = TopicRule(
    "tea",
    re.compile(r"\btea\b|\bchai\b|\bi?cyayi\b|\bi?cyai\b|\bicyay\b", re.IGNORECASE),
    messages.TEA,
    examples=(
        "Can I give tea to my young child?", "Is tea ok for a 9 month old?", "Can my toddler drink tea with milk?",
        "Nshobora guha icyayi umwana wanjye muto?", "Umwana w'amezi 10 yanywa icyayi?",
        "Ese icyayi ni kibi ku bana?", "Uruhinja rwanywa icyayi?",   # NEEDS REVIEW: drafted by Claude
    ),
)

RULES = (HONEY, TEA)


@dataclass
class TopicRules:
    rules: Sequence[TopicRule] = RULES
    embedder: Embedder | None = None
    threshold: float = MEANING_THRESHOLD
    _examples: list[np.ndarray] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.embedder is not None:
            self._examples = [self.embedder(list(rule.examples)) for rule in self.rules]

    def for_question(self, question: str) -> TopicRule | None:
        """The rule whose fixed answer replaces the model for this question, if any."""
        about_child = bool(CHILD.search(question))
        meaning = self._meaning(question)
        for rule, score in zip(self.rules, meaning):
            if rule.child_only and not about_child:
                continue
            if rule.keywords.search(question) or score >= self.threshold:
                return rule
        return None

    def for_answer(self, question: str, answer: str) -> TopicRule | None:
        """The rule to apply to the model's answer: it talks about the topic and does not already say it safely."""
        about_child = bool(CHILD.search(question))
        for rule in self.rules:
            if rule.child_only and not about_child:
                continue
            if rule.keywords.search(answer) and not (rule.answer_ok and rule.answer_ok.search(answer)):
                return rule
        return None

    def _meaning(self, question: str) -> list[float]:
        if self.embedder is None:
            return [0.0] * len(self.rules)
        q = self.embedder([question])[0]
        return [float(np.max(examples @ q)) for examples in self._examples]
