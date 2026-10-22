"""Make a smaller GGUF file by quantising its weights with llama.cpp.

``q4_k_m`` stores most weights in about 4.5 bits instead of 8 (``q8_0``): the file is ~40% smaller
and generation on a CPU is faster, for a small loss in quality. Requires llama-cpp-python.

    python -m nutriassist.inference.quantize models/nutriassist-rw-q8_0.gguf models/nutriassist-rw-q4_k_m.gguf
"""

from __future__ import annotations

import argparse
import ctypes
import os
from pathlib import Path

FORMATS = {"q4_k_m": "LLAMA_FTYPE_MOSTLY_Q4_K_M", "q5_k_m": "LLAMA_FTYPE_MOSTLY_Q5_K_M", "q8_0": "LLAMA_FTYPE_MOSTLY_Q8_0"}


def quantize_gguf(source: str | Path, target: str | Path, kind: str = "q4_k_m") -> Path:
    import llama_cpp

    if kind not in FORMATS:
        raise ValueError(f"kind must be one of {sorted(FORMATS)}, not {kind!r}")
    source, target = Path(source), Path(target)
    if not source.exists():
        raise FileNotFoundError(source)
    params = llama_cpp.llama_model_quantize_default_params()
    params.ftype = getattr(llama_cpp, FORMATS[kind])
    params.nthread = os.cpu_count() or 1
    params.allow_requantize = True      # the source may already be quantised (q8_0)
    status = llama_cpp.llama_model_quantize(str(source).encode(), str(target).encode(), ctypes.byref(params))
    if status != 0 or not target.exists():
        raise RuntimeError(f"Quantising {source.name} to {kind} failed (llama.cpp status {status})")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Quantise a GGUF model with llama.cpp")
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--kind", default="q4_k_m", choices=sorted(FORMATS))
    args = parser.parse_args()
    target = quantize_gguf(args.source, args.target, args.kind)
    print(f"{target}: {target.stat().st_size / 2**30:.2f} GB (from {args.source.stat().st_size / 2**30:.2f} GB)")


if __name__ == "__main__":
    main()
