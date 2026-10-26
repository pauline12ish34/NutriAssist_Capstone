"""Plain Kinyarwanda text for continued pre-training: choosing passages and packing them into blocks.

The corpus (``CircuitNotion/kinyarwanda_corpus`` on Hugging Face, 3.5M rows of news and encyclopedia
text, MIT licence, sources not documented) has one paragraph per row, and neighbouring rows usually
come from the same article. So passages are taken as runs of consecutive rows from random places:
each run reads as connected text, and the runs together cover many sources rather than the first few.

Rows that contain a validation or test question or answer are dropped, so the scores measured on
those splits stay fair. No torch here, so this module is tested without a GPU.
"""

from __future__ import annotations

import random
from typing import Iterable, Iterator, Sequence

from ..language import KINYARWANDA, LanguageDetector

KINYARWANDA_CORPUS = "CircuitNotion/kinyarwanda_corpus"
MIN_HELD_OUT_CHARS = 20   # shorter held-out texts ("Yego.") would match ordinary sentences


def normalise(text: str) -> str:
    return " ".join(str(text).lower().split())


def sample_runs(num_rows: int, rows_wanted: int, run_length: int = 64, seed: int = 42) -> list[int]:
    """Row indices: ``rows_wanted`` rows in runs of ``run_length`` consecutive rows, from random places."""
    runs = max(1, num_rows // run_length)
    chosen = random.Random(seed).sample(range(runs), min(runs, -(-rows_wanted // run_length)))
    return [i for run in sorted(chosen) for i in range(run * run_length, min((run + 1) * run_length, num_rows))]


def clean_passages(rows: Iterable[str], held_out: Iterable[str] = (), min_words: int = 8,
                   language: LanguageDetector | None = None) -> Iterator[str]:
    """Kinyarwanda rows of at least ``min_words`` words, without duplicates or held-out text."""
    detect = language or LanguageDetector()
    held = [h for h in {normalise(text) for text in held_out} if len(h) >= MIN_HELD_OUT_CHARS]
    seen: set[str] = set()
    for row in rows:
        text = " ".join(str(row).split())
        key = normalise(text)
        if len(key.split()) < min_words or key in seen or detect(text) != KINYARWANDA:
            continue
        if any(h in key for h in held):
            continue
        seen.add(key)
        yield text


def pack_blocks(token_lists: Iterable[Sequence[int]], block_size: int, separator: int,
                max_blocks: int | None = None) -> list[list[int]]:
    """Joins passages (with ``separator`` between them) and cuts the stream into equal blocks.

    Every block is full, so no padding is needed; the incomplete last block is dropped.
    """
    blocks: list[list[int]] = []
    buffer: list[int] = []
    for tokens in token_lists:
        buffer.extend(tokens)
        buffer.append(separator)
        while len(buffer) >= block_size:
            blocks.append(buffer[:block_size])
            buffer = buffer[block_size:]
            if max_blocks is not None and len(blocks) >= max_blocks:
                return blocks
    return blocks
