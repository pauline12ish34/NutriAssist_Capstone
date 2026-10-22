import pytest

pytest.importorskip("llama_cpp")
from nutriassist.inference.quantize import quantize_gguf  # noqa: E402


def test_unknown_format_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="q4_k_m"):
        quantize_gguf(tmp_path / "in.gguf", tmp_path / "out.gguf", kind="q2")


def test_missing_source_is_reported(tmp_path):
    with pytest.raises(FileNotFoundError):
        quantize_gguf(tmp_path / "missing.gguf", tmp_path / "out.gguf")
