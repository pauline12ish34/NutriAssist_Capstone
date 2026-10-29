"""The chat pipeline: language detection, safety rules, reviewed answers, the language model and output checks.

    question ─► language ─► danger signs? ── urgent ──► fixed referral message (model skipped)
                                 │
                                 ├─ about honey ──► fixed honey message (model skipped)
                                 │
                                 └─ none / medical ─► matches a reviewed question? ── yes ──► reviewed answer
                                                                  │
                                                                  no
                                                                  │
            reviewed-only language (``NUTRIASSIST_KINYARWANDA=reviewed``)? ── yes ──► "Did you mean...?"
                                                  │                                        ▲
                                                  no                          translator failed
                                                  │                                        │
                         Kinyarwanda and a translator? ── yes ──► translate to English ─► model ─► translate back
                                                  │                                                   │
                                                  no ──► model answer ────────────────────────────────┤
                                                                                                      ▼
                                                                         dose check ─► referral check ─► reply

The fine-tuned model writes reliable English but not reliable Kinyarwanda (``docs/kinyarwanda.md``).
So a Kinyarwanda question with no reviewed answer is translated to English (by Gemini in the app),
answered by the model in English and translated back; the app labels these answers machine-translated.
NLLB, the offline translator, was judged not good enough by a native speaker.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

from .inference.base import ChatModel
from .knowledge import KnowledgeBase, Match
from .language import ENGLISH, KINYARWANDA, LanguageDetector
from .prompts import SYSTEM_PROMPT, build_grounded_messages, build_messages
from .safety import messages
from .safety.detector import DangerSignDetector, SafetyAssessment
from .safety.referral import ReferralDetector
from .safety.rules import SafetyLevel
from .translation import Translator, strip_foreign_script, translate_text

log = logging.getLogger("nutriassist.assistant")

MAX_QUESTION_CHARS = 1000

# A number followed by a medicine unit, in either word order ("5 ml", "ml 5", "2 tablets", "ibinini 2").
_DOSE = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:mg|mcg|µg|ml|iu|tablets?|capsules?|drops?|ibinini|ibitonyanga)\b"
    r"|\b(?:mg|ml|ibinini)\s*\d+(?:[.,]\d+)?\b",
    re.IGNORECASE,
)
_HONEY = re.compile(r"\bhoney\b|\bubuki\b", re.IGNORECASE)
# An answer that mentions honey must also give the age limit, or the fixed honey message is added.
_HONEY_AGE_LIMIT = re.compile(r"\b12 months\b|\b(?:1|one) year\b|\bfirst year\b|\bmezi 12\b", re.IGNORECASE)


class ReplySource(str, Enum):
    REVIEWED = "reviewed_answer"                 # a stored answer reviewed by a person: the model not called
    NO_MATCH = "no_reviewed_answer"              # reviewed-only language, no match: fixed message and suggestions
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
    translated: bool = False                     # the model answered in English and the answer was machine-translated
    matched_question: str | None = None          # for a reviewed answer: the stored question it matched
    suggestions: list[str] = field(default_factory=list)  # "Did you mean...?" reviewed questions


class InvalidQuestion(ValueError):
    """The question is empty or too long."""


class NutritionAssistant:
    """Answers one caregiver question at a time, with safety checks before and after the model."""

    def __init__(self, model: ChatModel, detector: DangerSignDetector | None = None,
                 language: LanguageDetector | None = None, referrals: ReferralDetector | None = None,
                 system_prompt: str = SYSTEM_PROMPT, knowledge: KnowledgeBase | None = None,
                 translator: Translator | None = None, reviewed_only: Iterable[str] = (),
                 grounding: int = 0, examples: KnowledgeBase | None = None) -> None:
        self.model = model
        self.detector = detector or DangerSignDetector()
        self.language = language or LanguageDetector()
        self.referrals = referrals or ReferralDetector()
        self.system_prompt = system_prompt
        self.knowledge = knowledge
        self.translator = translator
        # RAG: this many closest reviewed pairs go into the model's prompt (0: the prompt it was trained with).
        self.grounding = grounding
        # Where the examples come from: a meaning-based index finds on-topic examples twice as often as
        # character matching (docs/kinyarwanda.md), but matching for direct answers stays on characters.
        self.examples = examples
        # Languages answered only from reviewed answers: the model never writes them.
        self.reviewed_only = frozenset(reviewed_only)
        if self.reviewed_only and knowledge is None:
            raise ValueError("reviewed_only needs a knowledge base of reviewed answers")

    def ask(self, question: str) -> AssistantReply:
        start = time.perf_counter()
        question = self.validate(question)
        lang = self.language(question)
        safety = self.detector.assess(question)
        signs = safety.labels(lang)

        match: Match | None = None
        translated = False
        suggestions: list[str] = []
        if safety.is_urgent:
            urgent_signs = [s.label_rw if lang == "rw" else s.label_en for s in safety.signs if s.level is SafetyLevel.URGENT]
            answer = messages.URGENT[lang].format(signs=messages.join_signs(urgent_signs, lang))
            source = ReplySource.SAFETY_RULE
        elif _HONEY.search(question):
            answer, source = messages.HONEY[lang], ReplySource.SAFETY_RULE
        elif self.knowledge is not None and (match := self.knowledge.find(question, lang)) is not None:
            answer, source = match.pair.answer, ReplySource.REVIEWED
        elif lang in self.reviewed_only or (answer := self._generated_answer(question, lang)) is None:
            suggestions = [m.pair.question for m in self.knowledge.suggest(question, lang)]
            answer = (messages.NO_MATCH if suggestions else messages.NO_MATCH_NO_SUGGESTIONS)[lang]
            source = ReplySource.NO_MATCH
        else:
            translated = lang == KINYARWANDA and self.translator is not None
            source = ReplySource.MODEL
            if _HONEY.search(answer) and not _HONEY_AGE_LIMIT.search(answer):
                answer = f"{answer}\n\n{messages.HONEY[lang]}"
            if safety.needs_health_worker:
                answer, source = self._check_medical_answer(answer, safety, lang)

        return AssistantReply(
            answer=answer,
            language=lang,
            safety_level=safety.level.name.lower(),
            danger_signs=signs,
            source=source,
            model_name=self._answered_by(source, translated),
            latency_ms=round(1000 * (time.perf_counter() - start), 1),
            translated=translated,
            matched_question=match.matched_question if match is not None else None,
            suggestions=suggestions,
        )

    def _generated_answer(self, question: str, lang: str) -> str | None:
        """The model's answer, through translation for Kinyarwanda when a translator is set.

        ``None`` when the translator fails (Gemini is online and can be busy or unreachable) and reviewed
        answers exist: the caller then offers the closest reviewed questions instead of an error.
        """
        if lang != KINYARWANDA or self.translator is None:
            return self._model_answer(question, lang)
        try:
            return self._translated_answer(question)
        except Exception:
            if self.knowledge is None:
                raise
            log.warning("Translation failed; offering reviewed questions instead", exc_info=True)
            return None

    def _model_answer(self, question: str, lang: str) -> str:
        # Qwen occasionally slips in a Chinese word ("colds (感冒)"); caregivers cannot read it.
        answer = self.model.generate(self._messages(question, lang))
        return strip_foreign_script(answer).strip()

    def _messages(self, question: str, lang: str):
        """The prompt, with the closest reviewed pairs in ``lang`` when grounding is on (RAG)."""
        index = self.examples or self.knowledge
        if not self.grounding or index is None:
            return build_messages(question, system_prompt=self.system_prompt)
        examples = index.suggest(question, lang, k=self.grounding, min_score=0.0)
        return build_grounded_messages(question, [(m.pair.question, m.pair.answer) for m in examples],
                                       system_prompt=self.system_prompt)

    def _translated_answer(self, question: str) -> str:
        english_question = translate_text(self.translator, question, KINYARWANDA, ENGLISH)
        english_answer = self._model_answer(english_question, ENGLISH)
        return translate_text(self.translator, english_answer, ENGLISH, KINYARWANDA)

    def _answered_by(self, source: ReplySource, translated: bool) -> str:
        if source is ReplySource.SAFETY_RULE:
            return "rules"
        if source in (ReplySource.REVIEWED, ReplySource.NO_MATCH):
            return "reviewed answers"
        return f"{self.model.name} + {self.translator.name}" if translated else self.model.name

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
