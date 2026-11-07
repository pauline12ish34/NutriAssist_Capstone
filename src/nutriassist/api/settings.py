"""API configuration from environment variables, and the choice of answer model."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from ..inference.base import ChatModel, GenerationSettings
from ..inference.scripted import ScriptedChatModel
from ..knowledge import DEFAULT_THRESHOLD, QA_MASTER, KnowledgeBase
from ..translation import Translator

log = logging.getLogger("nutriassist.api")

DEMO_ANSWER = {
    "en": ("(Demo mode: the NutriAssist model is not installed on this server, so this is not a real answer. "
           "See the README to download the model.) You asked: {question}"),
    "rw": ("(Uburyo bw'igerageza: porogaramu ya NutriAssist ntiyashyizwe kuri iyi seriveri, iki si igisubizo "
           "nyacyo. Reba README kugira ngo uyikure kuri interineti.) Wabajije: {question}"),
}


# Model files the notebook exports, in order of preference when no path is configured.
DEFAULT_MODEL_FILES = (Path("models/nutriassist-rw-q4_k_m.gguf"), Path("models/nutriassist-rw-q8_0.gguf"))


def find_model_file(candidates: tuple[Path, ...] = DEFAULT_MODEL_FILES) -> Path:
    """The first exported model present on disk, else the preferred name (so a download goes there)."""
    return next((path for path in candidates if path.exists()), candidates[0])


@dataclass(frozen=True)
class Settings:
    """Read once at start-up. Every value has a default, so the API starts with no configuration."""

    model_path: Path = DEFAULT_MODEL_FILES[0]
    hf_repo: str | None = None              # download the model from this Hugging Face repo if it is missing
    hf_file: str = DEFAULT_MODEL_FILES[0].name
    backend: str = "auto"                   # "auto" (GGUF if available, else demo), "llamacpp" or "demo"
    max_new_tokens: int = 320
    repetition_penalty: float = GenerationSettings.repetition_penalty   # the notebook's section 5.3 chooses it
    threads: int | None = None
    context_tokens: int = 2048
    knowledge_path: Path | None = QA_MASTER   # reviewed answers; None turns them off
    match_threshold: float = DEFAULT_THRESHOLD
    embeddings: bool = False                 # LaBSE embeddings for matching: measured worse than characters alone, off
    # How a Kinyarwanda question with no reviewed answer is answered: "reviewed" (no answer, "Did you mean...?"
    # suggestions), "translate" (through English) or "model" (the model writes Kinyarwanda itself).
    kinyarwanda: str = "translate"
    translator: str = "gemini"              # for "translate": "gemini" or "claude" (online) or "nllb" (offline)
    claude_model: str = "claude-sonnet-5-5"   # for translator "claude"; claude-haiku-5-5 is ~20x cheaper
    grounding: int = 0                      # RAG: closest reviewed pairs put in the model's prompt (0: off)
    checks: bool = True                     # scope and answer-relevance checks, meaning-based topic rules (LaBSE)
    unanswered_log: Path | None = Path("logs/unanswered.jsonl")   # questions with no reviewed answer

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.environ.get
        return cls(
            model_path=Path(env("NUTRIASSIST_MODEL_PATH")) if env("NUTRIASSIST_MODEL_PATH") else find_model_file(),
            hf_repo=env("NUTRIASSIST_HF_REPO") or None,
            hf_file=env("NUTRIASSIST_HF_FILE", cls.hf_file),
            backend=env("NUTRIASSIST_BACKEND", cls.backend).lower(),
            max_new_tokens=int(env("NUTRIASSIST_MAX_NEW_TOKENS", cls.max_new_tokens)),
            repetition_penalty=float(env("NUTRIASSIST_REPETITION_PENALTY", cls.repetition_penalty)),
            threads=int(env("NUTRIASSIST_THREADS")) if env("NUTRIASSIST_THREADS") else None,
            context_tokens=int(env("NUTRIASSIST_CONTEXT_TOKENS", cls.context_tokens)),
            knowledge_path=_optional_path(env("NUTRIASSIST_KNOWLEDGE", str(QA_MASTER))),
            match_threshold=float(env("NUTRIASSIST_MATCH_THRESHOLD", cls.match_threshold)),
            embeddings=env("NUTRIASSIST_EMBEDDINGS", "off").lower() in {"on", "1", "true", "yes"},
            kinyarwanda=env("NUTRIASSIST_KINYARWANDA", cls.kinyarwanda).lower(),
            translator=env("NUTRIASSIST_TRANSLATOR", cls.translator).lower(),
            claude_model=env("NUTRIASSIST_CLAUDE_MODEL", cls.claude_model),
            grounding=int(env("NUTRIASSIST_GROUNDING", cls.grounding)),
            checks=env("NUTRIASSIST_CHECKS", "on").lower() in {"on", "1", "true", "yes"},
            unanswered_log=_optional_path(env("NUTRIASSIST_UNANSWERED_LOG", str(cls.unanswered_log))),
        )


def _optional_path(value: str) -> Path | None:
    return None if value.lower() in {"", "off", "none"} else Path(value)


def build_knowledge_base(settings: Settings) -> KnowledgeBase | None:
    """The reviewed answers, or ``None`` when turned off or the file is missing.

    Without ``sentence-transformers`` installed, matching falls back to character n-grams only.
    """
    if settings.knowledge_path is None or not settings.knowledge_path.exists():
        return None
    embedder = None
    if settings.embeddings:
        try:
            from ..knowledge import SentenceEmbedder

            embedder = SentenceEmbedder()
        except ImportError:
            log.warning("sentence-transformers is not installed: matching reviewed answers by characters only")
    return KnowledgeBase.load(settings.knowledge_path, embedder, settings.match_threshold)


def build_embedder(settings: Settings):
    """LaBSE, loaded once for the grounding examples and the checks; ``None`` if neither is on or the
    package is missing (both then fall back: examples by characters, no scope or relevance check)."""
    if not (settings.grounding or settings.checks):
        return None
    try:
        from ..knowledge import SentenceEmbedder

        return SentenceEmbedder()
    except ImportError:
        log.warning("sentence-transformers is not installed: no meaning-based examples or answer checks")
        return None


def build_example_index(settings: Settings, embedder=None) -> KnowledgeBase | None:
    """For grounding (RAG): the reviewed pairs searched by meaning in both languages (LaBSE).

    ``None`` (examples then come from the character index) when grounding is off, the file is missing
    or there is no embedder.
    """
    if not settings.grounding or embedder is None or settings.knowledge_path is None \
            or not settings.knowledge_path.exists():
        return None
    return KnowledgeBase.load(settings.knowledge_path, embedder, settings.match_threshold, letters_weight=0.0)


def build_checks(settings: Settings, embedder=None):
    """The topic rules (meaning matching with an embedder) and the scope and answer-relevance checker."""
    from ..knowledge import load_pairs
    from ..safety.relevance import RelevanceChecker
    from ..safety.topics import TopicRules

    if not settings.checks or embedder is None:
        return TopicRules(), None
    path = settings.knowledge_path
    questions = [w for _, wordings in load_pairs(path) for w in wordings] if path and path.exists() else []
    return TopicRules(embedder=embedder), (RelevanceChecker(embedder, questions) if questions else None)


KINYARWANDA_MODES = ("reviewed", "translate", "model")
TRANSLATORS = ("gemini", "claude", "nllb")


def reviewed_only_languages(settings: Settings, knowledge: KnowledgeBase | None,
                            translator: Translator | None = None) -> frozenset[str]:
    """Languages the model must not write: Kinyarwanda in ``reviewed`` mode, or in ``translate`` mode with no
    translator, when reviewed answers exist."""
    if settings.kinyarwanda not in KINYARWANDA_MODES:
        raise ValueError(f"NUTRIASSIST_KINYARWANDA must be one of {', '.join(KINYARWANDA_MODES)}, "
                         f"not {settings.kinyarwanda!r}")
    if settings.kinyarwanda == "model" or (settings.kinyarwanda == "translate" and translator is not None):
        return frozenset()
    if knowledge is None:
        log.warning("No reviewed answers loaded: Kinyarwanda questions go to the model")
        return frozenset()
    return frozenset({"rw"})


def build_translator(settings: Settings) -> Translator | None:
    if settings.kinyarwanda != "translate":
        return None
    if settings.translator not in TRANSLATORS:
        raise ValueError(f"NUTRIASSIST_TRANSLATOR must be one of {', '.join(TRANSLATORS)}, not {settings.translator!r}")
    try:
        from ..translation import CachingTranslator   # repeated questions reuse earlier translations

        if settings.translator == "gemini":
            from ..translation import GeminiTranslator

            return CachingTranslator(GeminiTranslator())
        if settings.translator == "claude":
            from ..translation import ClaudeTranslator

            return CachingTranslator(ClaudeTranslator(model=settings.claude_model))
        from ..translation import NllbTranslator, TermAwareTranslator

        return CachingTranslator(TermAwareTranslator(NllbTranslator()))
    except (ImportError, RuntimeError) as error:   # RuntimeError: no Gemini or Anthropic API key
        log.warning("No %s translator (%s): Kinyarwanda questions get reviewed answers only", settings.translator, error)
        return None


def build_chat_model(settings: Settings) -> tuple[ChatModel, bool]:
    """The model to serve, and whether it is the demo stand-in."""
    if settings.backend not in {"auto", "llamacpp", "demo"}:
        raise ValueError(f"NUTRIASSIST_BACKEND must be auto, llamacpp or demo, not {settings.backend!r}")
    if settings.backend == "demo":
        return _demo_model(), True

    path = settings.model_path
    if not path.exists() and settings.hf_repo:
        path = _download(settings)
    if not path.exists():
        if settings.backend == "llamacpp":
            raise FileNotFoundError(f"Model file not found: {path}. Set NUTRIASSIST_MODEL_PATH or NUTRIASSIST_HF_REPO.")
        return _demo_model(), True

    from ..inference.llamacpp_model import LlamaCppChatModel

    generation = GenerationSettings(max_new_tokens=settings.max_new_tokens,
                                    repetition_penalty=settings.repetition_penalty, batch_size=1)
    return LlamaCppChatModel.from_file(path, settings.context_tokens, settings.threads, generation), False


def _download(settings: Settings) -> Path:
    from huggingface_hub import hf_hub_download

    settings.model_path.parent.mkdir(parents=True, exist_ok=True)
    return Path(hf_hub_download(settings.hf_repo, settings.hf_file, local_dir=settings.model_path.parent))


def _demo_model() -> ScriptedChatModel:
    from ..language import LanguageDetector

    detect = LanguageDetector()
    model = ScriptedChatModel(lambda question: DEMO_ANSWER[detect(question)].format(question=question))
    model.name = "demo (no model installed)"
    return model
