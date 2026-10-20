"""API configuration from environment variables, and the choice of answer model."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from ..inference.base import ChatModel, GenerationSettings
from ..inference.scripted import ScriptedChatModel

DEMO_ANSWER = {
    "en": ("(Demo mode: the NutriAssist model is not installed on this server, so this is not a real answer. "
           "See the README to download the model.) You asked: {question}"),
    "rw": ("(Uburyo bw'igerageza: porogaramu ya NutriAssist ntiyashyizwe kuri iyi seriveri, iki si igisubizo "
           "nyacyo. Reba README kugira ngo uyikure kuri interineti.) Wabajije: {question}"),
}


@dataclass(frozen=True)
class Settings:
    """Read once at start-up. Every value has a default, so the API starts with no configuration."""

    model_path: Path = Path("models/nutriassist-rw-q8_0.gguf")
    hf_repo: str | None = None              # download the model from this Hugging Face repo if it is missing
    hf_file: str = "nutriassist-rw-q8_0.gguf"
    backend: str = "auto"                   # "auto" (GGUF if available, else demo), "llamacpp" or "demo"
    max_new_tokens: int = 320
    threads: int | None = None
    context_tokens: int = 2048

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.environ.get
        return cls(
            model_path=Path(env("NUTRIASSIST_MODEL_PATH", str(cls.model_path))),
            hf_repo=env("NUTRIASSIST_HF_REPO") or None,
            hf_file=env("NUTRIASSIST_HF_FILE", cls.hf_file),
            backend=env("NUTRIASSIST_BACKEND", cls.backend).lower(),
            max_new_tokens=int(env("NUTRIASSIST_MAX_NEW_TOKENS", cls.max_new_tokens)),
            threads=int(env("NUTRIASSIST_THREADS")) if env("NUTRIASSIST_THREADS") else None,
            context_tokens=int(env("NUTRIASSIST_CONTEXT_TOKENS", cls.context_tokens)),
        )


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

    generation = GenerationSettings(max_new_tokens=settings.max_new_tokens, batch_size=1)
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
