"""Find danger signs and medical requests in a caregiver's message."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from .rules import RULES, DangerRule, SafetyLevel

# An English negation shortly before a match cancels it: "she is not vomiting everything".
_NEGATION = re.compile(r"\b(?:not|no|never|without|isn't|doesn't|hasn't|didn't|wasn't|don't)\b")
_NEGATION_WINDOW = 20  # characters before the match, about three words
_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "`": "'"})


@dataclass(frozen=True)
class SafetyAssessment:
    level: SafetyLevel
    signs: tuple[DangerRule, ...] = ()

    @property
    def is_urgent(self) -> bool:
        return self.level is SafetyLevel.URGENT

    @property
    def needs_health_worker(self) -> bool:
        return self.level is not SafetyLevel.NONE

    def labels(self, language: str = "en") -> list[str]:
        return [rule.label_rw if language == "rw" else rule.label_en for rule in self.signs]


class _CompiledRule:
    def __init__(self, rule: DangerRule) -> None:
        self.rule = rule
        self.groups = [re.compile(pattern) for pattern in rule.all_of]

    def matches(self, text: str) -> bool:
        return all(any(not _negated(text, m.start()) for m in group.finditer(text)) for group in self.groups)


def _negated(text: str, start: int) -> bool:
    return bool(_NEGATION.search(text[max(0, start - _NEGATION_WINDOW):start]))


def normalise(text: str) -> str:
    return " ".join(text.translate(_APOSTROPHES).lower().split())


class DangerSignDetector:
    """Rule-based and transparent: every decision names the rules that fired.

    Runs in time linear in the message length for each rule, needs no model, and
    cannot be talked out of a referral, which is why it sits in front of the LLM.
    """

    def __init__(self, rules: Sequence[DangerRule] = RULES) -> None:
        self._rules = [_CompiledRule(rule) for rule in rules]

    def assess(self, text: str) -> SafetyAssessment:
        text = normalise(text)
        signs = tuple(compiled.rule for compiled in self._rules if compiled.matches(text))
        level = max((sign.level for sign in signs), default=SafetyLevel.NONE)
        # Report the signs that decided the level first, so messages lead with the most serious one.
        signs = tuple(sorted(signs, key=lambda sign: -sign.level))
        return SafetyAssessment(level, signs)
