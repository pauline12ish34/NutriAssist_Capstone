"""Ask the whole app unseen questions, as a parent would, and write a sheet to rate the replies.

    python scripts/unseen_test.py                      # data/QA_data/review/unseen_test_questions.csv
    python scripts/unseen_test.py --questions my.csv   # columns: question, expected, note

Uses the same settings as the API (``NUTRIASSIST_*`` variables: set ``NUTRIASSIST_GROUNDING=3`` to test
RAG). Every Kinyarwanda question the model answers costs two Gemini requests, and the free tier allows
about 20 per model per day, so run it when the quota is fresh. Replies are saved as they come
(``outputs/unseen_test/replies.jsonl``): a run stopped by the quota continues where it stopped.

Fill the ``rating`` column of ``outputs/unseen_test/rating_sheet.csv``:
correct / related_with_error / off_topic / unsafe / declined_ok / declined_wrongly.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nutriassist.api.settings import (Settings, build_chat_model, build_checks, build_embedder,  # noqa: E402
                                      build_example_index, build_knowledge_base, build_translator,
                                      reviewed_only_languages)
from nutriassist.assistant import NutritionAssistant  # noqa: E402

QUESTIONS = Path("data/QA_data/review/unseen_test_questions.csv")
OUT = Path("outputs/unseen_test")


def build_assistant(settings: Settings) -> NutritionAssistant:
    """The assistant exactly as the API builds it."""
    model, demo = build_chat_model(settings)
    if demo:
        raise SystemExit("No model in models/: the test needs the real model (see the README).")
    knowledge, translator = build_knowledge_base(settings), build_translator(settings)
    embedder = build_embedder(settings)
    topics, checker = build_checks(settings, embedder)
    return NutritionAssistant(model, knowledge=knowledge, translator=translator,
                              reviewed_only=reviewed_only_languages(settings, knowledge, translator),
                              grounding=settings.grounding, examples=build_example_index(settings, embedder),
                              topics=topics, checker=checker)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--questions", type=Path, default=QUESTIONS)
    args = parser.parse_args()

    questions = pd.read_csv(args.questions)
    assistant = build_assistant(Settings.from_env())
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "replies.jsonl"
    done = set(pd.read_json(path, lines=True)["question"]) if path.exists() else set()
    with path.open("a", encoding="utf-8") as handle:
        for n, row in enumerate(questions.itertuples(), 1):
            if row.question in done:
                continue
            start = time.perf_counter()
            reply = assistant.ask(row.question)
            record = {"question": row.question, "expected": row.expected, "note": row.note,
                      "language": reply.language, "source": reply.source.value, "translated": reply.translated,
                      "answer": reply.answer, "suggestions": reply.suggestions,
                      "seconds": round(time.perf_counter() - start, 1)}
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            handle.flush()
            print(f"[{n}/{len(questions)}] {reply.source.value:22} {record['seconds']:5.1f}s  {row.question[:60]}")

    replies = pd.read_json(path, lines=True)
    replies["rating"] = ""
    sheet = OUT / "rating_sheet.csv"
    replies.to_csv(sheet, index=False, encoding="utf-8-sig")   # BOM: Excel shows Kinyarwanda right
    print(f"\n{replies['source'].value_counts().to_string()}\n\nRate the replies in {sheet}")


if __name__ == "__main__":
    main()
