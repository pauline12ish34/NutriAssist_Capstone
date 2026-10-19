"""The chat pipeline: language detection, safety rules, the language model and output checks.

    question ─► language ─► danger signs? ── urgent ──► fixed referral message (model skipped)
                                 │
                                 └─ none / medical ──► model answer ─► dose check ─► referral check ─► reply
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum

from .inference.base import ChatModel
from .language import LanguageDetector
from .prompts import SYSTEM_PROMPT, build_messages
from .safety import messages
from .safety.detector import DangerSignDetector, SafetyAssessment
from .safety.referral import ReferralDetector
from .safety.rules import SafetyLevel

MAX_QUESTION_CHARS = 1000

# A number followed by a medicine unit, in either word order ("5 ml", "ml 5", "2 tablets", "ibinini 2").
_DOSE = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:mg|mcg|µg|ml|iu|tablets?|capsules?|drops?|ibinini|ibitonyanga)\b"
    r"|\b(?:mg|ml|ibinini)\s*\d+(?:[.,]\d+)?\b",
    re.IGNORECASE,
)


class ReplySource(str, Enum):
    MODEL = "model"                              # the model's answer, unchanged
    MODEL_WITH_REFERRAL = "model+referral_note"  # the model's answer, plus a referral it had left out
    SAFETY_RULE = "safety_rule"                  # urgent danger sign: fixed message, model not called
    DOSE_BLOCKED = "dose_blocked"                # the model gave a medicine dose: replaced


@dataclass(frozen=True)
class AssistantReply:
    answer: str
    language: str
    safety_level: str
    danger_signs: list[str] = field(default_factory=list)
    source: ReplySource = ReplySource.MODEL
    model_name: str = ""
    latency_ms: float = 0.0


class InvalidQuestion(ValueError):
    """The question is empty or too long."""


class NutritionAssistant:
    """Answers one caregiver question at a time, with safety checks before and after the model."""

    def __init__(self, model: ChatModel, detector: DangerSignDetector | None = None,
                 language: LanguageDetector | None = None, referrals: ReferralDetector | None = None,
                 system_prompt: str = SYSTEM_PROMPT) -> None:
        self.model = model
        self.detector = detector or DangerSignDetector()
        self.language = language or LanguageDetector()
        self.referrals = referrals or ReferralDetector()
        self.system_prompt = system_prompt

    def ask(self, question: str) -> AssistantReply:
        start = time.perf_counter()
        question = self.validate(question)
        lang = self.language(question)
        safety = self.detector.assess(question)
        signs = safety.labels(lang)

        if safety.is_urgent:
            urgent_signs = [s.label_rw if lang == "rw" else s.label_en for s in safety.signs if s.level is SafetyLevel.URGENT]
            answer = messages.URGENT[lang].format(signs=messages.join_signs(urgent_signs, lang))
            source = ReplySource.SAFETY_RULE
        else:
            answer = self.model.generate(build_messages(question, system_prompt=self.system_prompt)).strip()
            source = ReplySource.MODEL
            if safety.needs_health_worker:
                answer, source = self._check_medical_answer(answer, safety, lang)

        return AssistantReply(
            answer=answer,
            language=lang,
            safety_level=safety.level.name.lower(),
            danger_signs=signs,
            source=source,
            model_name=self.model.name if source is not ReplySource.SAFETY_RULE else "rules",
            latency_ms=round(1000 * (time.perf_counter() - start), 1),
        )

    @staticmethod
    def validate(question: str) -> str:
        question = (question or "").strip()
        if not question:
            raise InvalidQuestion("Please type a question.")
        if len(question) > MAX_QUESTION_CHARS:
            raise InvalidQuestion(f"Please keep the question under {MAX_QUESTION_CHARS} characters.")
        return question

    def _check_medical_answer(self, answer: str, safety: SafetyAssessment, lang: str) -> tuple[str, ReplySource]:
        asks_about_medicine = any(sign.key == "medicine" for sign in safety.signs)
        if asks_about_medicine and _DOSE.search(answer):
            return messages.DOSE_BLOCKED[lang], ReplySource.DOSE_BLOCKED
        if not self.referrals.refers(answer):
            return f"{answer}\n\n{messages.MEDICAL_NOTE[lang]}", ReplySource.MODEL_WITH_REFERRAL
        return answer, ReplySource.MODEL
