"""Which translator writes better Kinyarwanda for the app: Gemini or Claude? A blind comparison.

    python scripts/compare_translators.py                  # 30 reviewed test answers (needs both API keys)
    python scripts/compare_translators.py --limit 60 --claude-model claude-haiku-5-5
    python scripts/compare_translators.py --score          # after rating: who won

The English answer of each reviewed pair is translated into Kinyarwanda by both, with the same prompt and
glossary the app uses. The native-speaker-reviewed Kinyarwanda answer is the reference.

Writes to ``outputs/translation_compare/``:

- ``translations.jsonl``: both translations, as they come (an interrupted run continues);
- ``rating_sheet.csv``: open in Excel. Each row shows translation **A** and **B** in random order, so you do
  not know which model wrote which. Fill ``better`` with A, B or same (and ``notes`` if useful). chrF
  against the reviewed answer is shown for each, but your judgement is the result that counts;
- ``key.csv``: which model is A and which is B. Do not open it until you have rated.

``--score`` reads the filled sheet and the key and prints the wins per model. Claude's token use and cost
are printed at the end of a run (Gemini's free tier costs nothing).
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nutriassist.knowledge import QA_MASTER  # noqa: E402
from nutriassist.translation import (CLAUDE_MODEL, GEMINI_MODEL, ClaudeTranslator,  # noqa: E402
                                     GeminiTranslator, translate_text)

OUT = Path("outputs/translation_compare")
SEED = 7


def reviewed_pairs(split: str, limit: int) -> list[dict]:
    rows = pd.read_json(QA_MASTER, lines=True)
    english = rows[rows["lang"] == "en"].set_index("group")
    kinyarwanda = rows[(rows["lang"] == "rw") & (rows["split"] == split)
                       & rows["review"].isin(["approved", "corrected"])]
    pairs = [{"id": r.id, "english": english.loc[r.group, "answer"], "reference": r.answer}
             for r in kinyarwanda.itertuples() if r.group in english.index]
    return pairs[:limit]


def chrf(text: str, reference: str) -> float | None:
    if not text or not reference:
        return None
    from sacrebleu.metrics import CHRF

    return round(CHRF().sentence_score(text, [reference]).score, 1)


def translate(translator, text: str) -> str:
    try:
        return translate_text(translator, text, "en", "rw")
    except Exception as error:   # one failure should not end the run; it shows in the sheet
        return f"[error: {type(error).__name__}: {error}]"


def run(args) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    done_path = OUT / "translations.jsonl"
    done = {}
    if done_path.exists():
        done = {r["id"]: r for r in map(json.loads, done_path.read_text(encoding="utf-8").splitlines())}
    pairs = reviewed_pairs(args.split, args.limit)
    todo = [p for p in pairs if p["id"] not in done]
    claude = ClaudeTranslator(model=args.claude_model) if todo else None
    gemini = GeminiTranslator(model=args.gemini_model) if todo else None
    with done_path.open("a", encoding="utf-8") as out:
        for i, pair in enumerate(todo, 1):
            row = {**pair, "gemini": translate(gemini, pair["english"]), "claude": translate(claude, pair["english"])}
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
            done[pair["id"]] = row
            print(f"{i}/{len(todo)} {pair['id']}")

    rng = random.Random(SEED)
    sheet, key = [], []
    for pair in pairs:
        row = done[pair["id"]]
        a, b = ("gemini", "claude") if rng.random() < 0.5 else ("claude", "gemini")
        sheet.append({"id": row["id"], "english": row["english"], "reviewed_kinyarwanda": row["reference"],
                      "translation_a": row[a], "translation_b": row[b],
                      "chrf_a": chrf(row[a], row["reference"]), "chrf_b": chrf(row[b], row["reference"]),
                      "better": "", "notes": ""})
        key.append({"id": row["id"], "a": a, "b": b})
    sheet_path = OUT / "rating_sheet.csv"
    if sheet_path.exists() and not args.overwrite:
        print(f"{sheet_path} exists (it may hold your ratings): not overwritten. Use --overwrite to rebuild it.")
    else:
        pd.DataFrame(sheet).to_csv(sheet_path, index=False, encoding="utf-8-sig")   # utf-8-sig: Excel reads it
        pd.DataFrame(key).to_csv(OUT / "key.csv", index=False)
        print(f"Rate {sheet_path} (better = A, B or same), then run with --score.")
    if claude is not None:
        cost = claude.cost_usd()
        print(f"Claude ({claude.model}): {claude.input_tokens} input + {claude.output_tokens} output tokens"
              + (f", about ${cost:.3f}" if cost is not None else ""))


def score() -> None:
    sheet = pd.read_csv(OUT / "rating_sheet.csv", encoding="utf-8-sig")
    key = pd.read_csv(OUT / "key.csv").set_index("id")
    wins = {"gemini": 0, "claude": 0, "same": 0}
    chrf_scores = {"gemini": [], "claude": []}
    rated = 0
    for row in sheet.itertuples():
        models = {"a": key.loc[row.id, "a"], "b": key.loc[row.id, "b"]}
        for side in ("a", "b"):
            value = getattr(row, f"chrf_{side}")
            if pd.notna(value):
                chrf_scores[models[side]].append(value)
        choice = str(row.better).strip().lower() if pd.notna(row.better) else ""
        if choice in models:
            wins[models[choice]] += 1
        elif choice == "same":
            wins["same"] += 1
        else:
            continue
        rated += 1
    print(f"Rated {rated} of {len(sheet)}: Claude better {wins['claude']}, Gemini better {wins['gemini']}, "
          f"same {wins['same']}")
    for model, values in chrf_scores.items():
        if values:
            print(f"Mean chrF vs reviewed answer, {model}: {sum(values) / len(values):.1f} ({len(values)} answers)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--limit", type=int, default=30, help="how many reviewed answers (default 30)")
    parser.add_argument("--split", default="test", choices=["train", "val", "test"])
    parser.add_argument("--claude-model", default=CLAUDE_MODEL)
    parser.add_argument("--gemini-model", default=GEMINI_MODEL)
    parser.add_argument("--overwrite", action="store_true", help="rebuild rating_sheet.csv even if it exists")
    parser.add_argument("--score", action="store_true", help="count the ratings in rating_sheet.csv")
    args = parser.parse_args()
    score() if args.score else run(args)


if __name__ == "__main__":
    main()
