"""The llama.cpp CPU backend with a real GGUF model. Skipped when no model file is in models/."""

from pathlib import Path

import pytest

try:
    import llama_cpp  # noqa: F401
except (ImportError, RuntimeError) as error:  # RuntimeError: installed, but the DLL is blocked (e.g. Smart App Control)
    pytest.skip(f"llama.cpp is not usable here: {error}", allow_module_level=True)
from fastapi.testclient import TestClient  # noqa: E402

from nutriassist.api.app import create_app  # noqa: E402
from nutriassist.api.settings import Settings, build_chat_model  # noqa: E402
from nutriassist.inference.base import GenerationSettings  # noqa: E402
from nutriassist.inference.llamacpp_model import LlamaCppChatModel  # noqa: E402
from nutriassist.prompts import build_messages  # noqa: E402

MODELS = sorted(Path("models").glob("*.gguf"), key=lambda p: p.stat().st_size)
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not MODELS, reason="no GGUF model in models/"),
]


@pytest.fixture(scope="module")
def model():
    return LlamaCppChatModel.from_file(MODELS[0], settings=GenerationSettings(max_new_tokens=24))


def test_generates_a_non_empty_answer(model):
    answer = model.generate(build_messages("Name one food rich in iron."))
    assert isinstance(answer, str) and answer


def test_generation_is_deterministic(model):
    messages = build_messages("What is porridge?")
    assert model.generate(messages) == model.generate(messages)


def test_batch_keeps_order(model):
    questions = [build_messages("Say A."), build_messages("Say B.")]
    assert model.generate_batch(questions) == [model.generate(q) for q in questions]


def test_api_serves_the_model_found_by_settings():
    chat_model, demo = build_chat_model(Settings(model_path=MODELS[0], max_new_tokens=16))
    assert not demo
    with TestClient(create_app(model=chat_model)) as client:
        body = client.post("/chat", json={"question": "What can a 9-month-old eat?"}).json()
    assert body["source"] == "model" and body["model"] == MODELS[0].name and body["answer"]


def test_missing_file_is_reported():
    with pytest.raises(FileNotFoundError):
        LlamaCppChatModel.from_file("models/does-not-exist.gguf")
