import pytest

try:
    import llama_cpp  # noqa: F401
except (ImportError, RuntimeError) as error:  # RuntimeError: installed, but the DLL is blocked (e.g. Smart App Control)
    pytest.skip(f"llama.cpp is not usable here: {error}", allow_module_level=True)
from nutriassist.inference.quantize import quantize_gguf  # noqa: E402


def test_unknown_format_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="q4_k_m"):
        quantize_gguf(tmp_path / "in.gguf", tmp_path / "out.gguf", kind="q2")


def test_missing_source_is_reported(tmp_path):
    with pytest.raises(FileNotFoundError):
        quantize_gguf(tmp_path / "missing.gguf", tmp_path / "out.gguf")
