"""How many tokens each candidate base model needs per word, in English and in Kinyarwanda.

    python scripts/tokenizer_fertility.py
    python scripts/tokenizer_fertility.py --models Qwen/Qwen2.5-1.5B-Instruct unsloth/gemma-3-1b-it

A tokenizer that splits a language's words into many small pieces saw little of that language
when it was built, and the model trained with it usually knows that language poorly too. This is
the evidence for why the fine-tuned Qwen model writes poor Kinyarwanda. Only the tokenizers are
downloaded (a few MB each). The ``unsloth/`` copies are used because they need no licence approval.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

DEFAULT_MODELS = [
    "Qwen/Qwen2.5-1.5B-Instruct",
    "unsloth/Llama-3.2-1B-Instruct",
    "unsloth/gemma-2-2b-it",
    "unsloth/gemma-3-1b-it",
]
QA_MASTER = Path("data/QA_data/processed/qa_master.jsonl")
OUTPUT = Path("outputs/tokenizer_fertility.csv")
_WORD = re.compile(r"\w+(?:'\w+)?", re.UNICODE)


def fertility(tokenizer, texts: list[str]) -> float:
    """Tokens per word over all ``texts``."""
    tokens = sum(len(tokenizer(text, add_special_tokens=False)["input_ids"]) for text in texts)
    words = sum(len(_WORD.findall(text)) for text in texts)
    return tokens / words


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    from transformers import AutoTokenizer

    pairs = pd.read_json(QA_MASTER, lines=True)
    texts = {lang: (group["question"] + " " + group["answer"]).tolist() for lang, group in pairs.groupby("lang")}
    rows = []
    for name in args.models:
        tokenizer = AutoTokenizer.from_pretrained(name)
        en, rw = fertility(tokenizer, texts["en"]), fertility(tokenizer, texts["rw"])
        rows.append({"model": name, "vocabulary": len(tokenizer), "tokens_per_word_en": round(en, 2),
                     "tokens_per_word_rw": round(rw, 2), "rw_vs_en": round(rw / en, 2)})
        print(f"{name:40s} en {en:.2f}  rw {rw:.2f}  ratio {rw / en:.2f}", file=sys.stderr)

    table = pd.DataFrame(rows).sort_values("tokens_per_word_rw")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(args.output, index=False)
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()
