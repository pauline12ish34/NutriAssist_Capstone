"""Choice of the GPU number format: Gemma must not compute in float16, where it overflows (e.g. on a Colab T4)."""

import json

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("transformers")

from nutriassist.inference.transformers_model import attention_implementation, compute_dtype, is_gemma  # noqa: E402

GEMMA = "unsloth/gemma-3-4b-it"
QWEN = "Qwen/Qwen2.5-1.5B-Instruct"


def use_gpu(monkeypatch, bf16: bool) -> None:
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "is_bf16_supported", lambda *args, **kwargs: bf16)


def test_gpu_with_bfloat16_uses_it_for_every_model(monkeypatch):
    use_gpu(monkeypatch, bf16=True)
    assert compute_dtype(GEMMA) == compute_dtype(QWEN) == compute_dtype() == torch.bfloat16


def test_gpu_without_bfloat16_computes_gemma_in_float32(monkeypatch):
    use_gpu(monkeypatch, bf16=False)
    assert compute_dtype(GEMMA) == torch.float32
    assert compute_dtype(QWEN) == torch.float16
    assert compute_dtype() == torch.float16


def test_local_model_folder_is_recognised_by_its_config(tmp_path, monkeypatch):
    (tmp_path / "config.json").write_text(json.dumps({"model_type": "gemma2"}), encoding="utf-8")
    assert is_gemma(tmp_path)
    assert attention_implementation(tmp_path) == "eager"
    use_gpu(monkeypatch, bf16=False)
    assert compute_dtype(tmp_path) == torch.float32


def test_other_models_keep_the_default_attention():
    assert not is_gemma(QWEN)
    assert attention_implementation(QWEN) is None
