"""The chat pipeline: language detection, safety rules, reviewed answers, the language model and output checks.

    question ─► language ─► danger signs? ── urgent ──► fixed referral message (model skipped)
                                 │
                                 ├─ about honey ──► fixed honey message (model skipped)
                                 │
                                 ├─ tea for a child ──► reviewed tea answer (model skipped)
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
from .safety.relevance import RelevanceChecker
from .safety.subject import outside_target_group
from .safety.rules import SafetyLevel
from .safety.topics import TopicRules
from .translation import Translator, strip_foreign_script, translate_text

log = logging.getLogger("nutriassist.assistant")

MAX_QUESTION_CHARS = 1000

# A number followed by a medicine unit, in either word order ("5 ml", "ml 5", "2 tablets", "ibinini 2").
_DOSE = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:mg|mcg|µg|ml|iu|tablets?|capsules?|drops?|ibinini|ibitonyanga)\b"
    r"|\b(?:mg|ml|ibinini)\s*\d+(?:[.,]\d+)?\b",
    re.IGNORECASE,
)


class ReplySource(str, Enum):
    REVIEWED = "reviewed_answer"                 # a stored answer reviewed by a person: the model not called
    NO_MATCH = "no_reviewed_answer"              # reviewed-only language, no match: fixed message and suggestions
    MODEL = "model"                              # the model's answer, unchanged
    MODEL_WITH_REFERRAL = "model+referral_note"  # the model's answer, plus a referral it had left out
    SAFETY_RULE = "safety_rule"                  # urgent danger sign or topic rule: fixed message, model not called
    DOSE_BLOCKED = "dose_blocked"                # the model gave a medicine dose: replaced
    TOPIC_REPLACED = "topic_rule_on_answer"      # the model's answer was on a rule's topic (tea): replaced
    OUT_OF_SCOPE = "out_of_scope"                # not close to any reviewed question: the model not called
    OFF_TOPIC = "off_topic_blocked"              # the model's answer was not about the question: not shown


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
                 grounding: int = 0, examples: KnowledgeBase | None = None,
                 topics: TopicRules | None = None, checker: RelevanceChecker | None = None) -> None:
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
        self.topics = topics or TopicRules()   # honey, tea: keywords always; meaning too with an embedder
        # Scope and answer-relevance checks (LaBSE); without one, every in-language question goes to the model.
        self.checker = checker
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
        elif outside_target_group(question):   # an adult or a child over 5: not the app's topic (no model needed)
            answer, source = messages.OUT_OF_SCOPE[lang], ReplySource.OUT_OF_SCOPE
        elif (rule := self.topics.for_question(question)) is not None:
            answer, source = rule.message[lang], ReplySource.SAFETY_RULE
        elif self.knowledge is not None and (match := self.knowledge.find(question, lang)) is not None:
            answer, source = match.pair.answer, ReplySource.REVIEWED
        # A Kinyarwanda question that will be translated is checked for scope in English instead (in
        # _translated_answer): everyday spelling ("amakaroni nimeza kumwana wimyaka 2") scores too low in LaBSE.
        elif self.checker is not None and not self._translates(lang) and not self._in_scope(question):
            answer, source = messages.OUT_OF_SCOPE[lang], ReplySource.OUT_OF_SCOPE
        else:
            result = ReplySource.NO_MATCH if lang in self.reviewed_only else self._generated_answer(question, lang)
            if result is ReplySource.OUT_OF_SCOPE:
                answer, source = messages.OUT_OF_SCOPE[lang], result
            elif isinstance(result, ReplySource):   # reviewed-only, translator down, or the answer was off topic
                answer, suggestions = self._no_answer(question, lang)
                source = result
            else:
                answer, source = result, ReplySource.MODEL
                translated = lang == KINYARWANDA and self.translator is not None
                answer, source = self._check_topic_rules(question, answer, lang)
                if safety.needs_health_worker and source is ReplySource.MODEL:
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

    def _generated_answer(self, question: str, lang: str) -> str | ReplySource:
        """The model's answer, through translation for Kinyarwanda when a translator is set.

        Instead of an answer, the reason there is none: ``NO_MATCH`` when the translator fails (Gemini is
        online and can be busy or unreachable) and reviewed answers exist, ``OFF_TOPIC`` when the answer
        is not about the question. The caller then offers the closest reviewed questions.
        """
        if lang != KINYARWANDA or self.translator is None:
            answer = self._model_answer(question, lang)
            if not answer:   # the model gave nothing: a blank reply under the AI label is worse than declining
                log.info("Empty model answer, declined as out of scope (%d characters)", len(question))
                return ReplySource.OUT_OF_SCOPE
            return answer if self._on_topic(question, answer) else ReplySource.OFF_TOPIC
        try:
            return self._translated_answer(question)
        except Exception:
            if self.knowledge is None:
                raise
            log.warning("Translation failed; offering reviewed questions instead", exc_info=True)
            return ReplySource.NO_MATCH

    def _in_scope(self, question: str) -> bool:
        """Close in meaning to a reviewed question, or names a food or illness from the food table: short
        questions ("I give the child pasta and cabbage") score too low in LaBSE but are plainly on topic."""
        return self._names_known_topic(question) or self.checker.in_scope(question)

    def _names_known_topic(self, question: str) -> bool:
        key_terms = getattr(self.knowledge, "key_terms", None)
        return key_terms is not None and bool(key_terms(question).topics)

    def _translates(self, lang: str) -> bool:
        """Kinyarwanda questions go through English when a translator is set and the model may answer."""
        return lang == KINYARWANDA and self.translator is not None and lang not in self.reviewed_only

    def _on_topic(self, question: str, answer: str) -> bool:
        if self.checker is None or self.checker.on_topic(question, answer):
            return True
        log.info("Answer blocked as off topic (%d characters)", len(question))
        return False

    def _no_answer(self, question: str, lang: str) -> tuple[str, list[str]]:
        """The "no checked answer" message and the closest reviewed questions as suggestions."""
        suggestions = [m.pair.question for m in self.knowledge.suggest(question, lang)] if self.knowledge else []
        return (messages.NO_MATCH if suggestions else messages.NO_MATCH_NO_SUGGESTIONS)[lang], suggestions

    def _check_topic_rules(self, question: str, answer: str, lang: str) -> tuple[str, ReplySource]:
        """A model answer on a rule's topic (honey, tea for a child) gets the fixed message."""
        rule = self.topics.for_answer(question, answer)
        if rule is None:
            return answer, ReplySource.MODEL
        if rule.on_answer == "append":
            return f"{answer}\n\n{rule.message[lang]}", ReplySource.MODEL
        return rule.message[lang], ReplySource.TOPIC_REPLACED

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

    def _translated_answer(self, question: str) -> str | ReplySource:
        # Each step is timed in the log, so a slow Kinyarwanda answer shows where the time went.
        start = time.perf_counter()
        english_question = translate_text(self.translator, question, KINYARWANDA, ENGLISH)
        translated_in = time.perf_counter()
        if self.checker is not None and not self._in_scope(english_question):
            return ReplySource.OUT_OF_SCOPE
        english_answer = self._model_answer(english_question, ENGLISH)
        answered = time.perf_counter()
        if not english_answer:   # nothing to translate: decline instead of showing a blank answer
            log.info("Empty model answer, declined as out of scope (%d characters)", len(english_question))
            return ReplySource.OUT_OF_SCOPE
        # Checked in English, which LaBSE knows best, and before translating back: no Gemini call is wasted.
        if not self._on_topic(english_question, english_answer):
            return ReplySource.OFF_TOPIC
        answer = translate_text(self.translator, english_answer, ENGLISH, KINYARWANDA)
        log.info("Kinyarwanda answer in %.1f s: question to English %.1f s, model %.1f s, answer to Kinyarwanda "
                 "%.1f s (%s)", time.perf_counter() - start, translated_in - start, answered - translated_in,
                 time.perf_counter() - answered, getattr(self.translator, "name", "translator"))
        return answer

    def _answered_by(self, source: ReplySource, translated: bool) -> str:
        if source in (ReplySource.SAFETY_RULE, ReplySource.TOPIC_REPLACED):
            return "rules"
        if source is ReplySource.OUT_OF_SCOPE:
            return "checks"
        if source in (ReplySource.REVIEWED, ReplySource.NO_MATCH, ReplySource.OFF_TOPIC):
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
