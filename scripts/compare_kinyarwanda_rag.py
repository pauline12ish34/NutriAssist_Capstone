"""Does RAG help the model write Kinyarwanda itself? The model alone vs with reviewed examples in its prompt.

    python scripts/compare_kinyarwanda_rag.py                          # the GGUF model on this CPU
    python scripts/compare_kinyarwanda_rag.py --gemma                  # the Space's Gemma 3 4B (needs a GPU: Colab)
    python scripts/compare_kinyarwanda_rag.py --questions my_qs.txt    # also new questions, one per line

Each Kinyarwanda test question is answered twice by the same model with no translation:

- **alone**: the prompt the model was trained with (what the app's ``model`` mode did before);
- **rag**: the same prompt plus the ``--examples`` closest reviewed Kinyarwanda pairs (``NUTRIASSIST_GROUNDING``).

The examples come from the training pairs only, so no test answer can be in the prompt. Reviewed answers
are never returned directly here: the point is what the model writes. Danger-sign rules still apply.

Writes ``outputs/kinyarwanda_rag/answers.jsonl`` as it goes (an interrupted run continues), and
``outputs/kinyarwanda_rag/rating_sheet.csv``: open it in Excel and fill the ``rating`` column
(correct / partly / wrong). chrF against the reviewed reference and repetition loops are filled in.
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
sys.path.insert(0, str(ROOT / "app"))

from nutriassist.api.settings import Settings, build_chat_model  # noqa: E402
from nutriassist.assistant import NutritionAssistant  # noqa: E402
from nutriassist.evaluation.metrics import is_repetition_loop  # noqa: E402
from nutriassist.evaluation.pipeline import knowledge_for  # noqa: E402
from nutriassist.knowledge import QA_MASTER  # noqa: E402

OUT = Path("outputs/kinyarwanda_rag")
NEVER_MATCH = 1.01   # above any similarity: reviewed answers are only used as examples, never returned


def test_questions() -> list[dict]:
    rows = pd.read_json(QA_MASTER, lines=True)
    rows = rows[(rows["lang"] == "rw") & (rows["split"] == "test")]
    return [{"id": r.id, "question": r.question, "reference": r.answer} for r in rows.itertuples()]


def extra_questions(path: Path) -> list[dict]:
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [{"id": f"new_{i:02d}", "question": q, "reference": ""} for i, q in enumerate(lines, 1)]


def load_model(gemma: bool):
    if gemma:
        from gradio_app import load_model as load_gemma   # base model + LoRA adapter, as on the Space

        return load_gemma()
    model, demo = build_chat_model(Settings.from_env())
    if demo:
        raise SystemExit("No GGUF model in models/: see the README to download it.")
    return model


def chrf(answer: str, reference: str) -> float | None:
    if not reference:
        return None
    from sacrebleu.metrics import CHRF

    return round(CHRF().sentence_score(answer, [reference]).score, 1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--gemma", action="store_true", help="use the Space's Gemma 3 4B + adapter (GPU)")
    parser.add_argument("--examples", type=int, default=3, help="reviewed pairs in the RAG prompt (default 3)")
    parser.add_argument("--questions", type=Path, help="a text file of extra questions, one per line")
    parser.add_argument("--limit", type=int, help="only the first N questions (a quick look)")
    args = parser.parse_args()

    questions = test_questions() + (extra_questions(args.questions) if args.questions else [])
    questions = questions[:args.limit] if args.limit else questions
    model = load_model(args.gemma)
    knowledge = knowledge_for("test", threshold=NEVER_MATCH)
    assistants = {"alone": NutritionAssistant(model, knowledge=knowledge),
                  "rag": NutritionAssistant(model, knowledge=knowledge, grounding=args.examples)}

    OUT.mkdir(parents=True, exist_ok=True)
    answers_path = OUT / "answers.jsonl"
    done = set()
    if answers_path.exists():
        done = {(r["model"], r["id"], r["mode"]) for r in pd.read_json(answers_path, lines=True).to_dict("records")}
    with answers_path.open("a", encoding="utf-8") as handle:
        for n, q in enumerate(questions, 1):
            for mode, assistant in assistants.items():
                if (model.name, q["id"], mode) in done:
                    continue
                start = time.perf_counter()
                reply = assistant.ask(q["question"])
                row = {"model": model.name, "id": q["id"], "mode": mode, "question": q["question"],
                       "reference": q["reference"], "answer": reply.answer, "source": reply.source.value,
                       "seconds": round(time.perf_counter() - start, 1)}
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                handle.flush()
                print(f"[{n}/{len(questions)}] {mode:5} {row['seconds']:5.1f}s  {q['question'][:60]}")

    answers = pd.read_json(answers_path, lines=True)
    answers = answers[answers["model"] == model.name]
    answers["chrf"] = [chrf(a, r) for a, r in zip(answers["answer"], answers["reference"])]
    answers["loop"] = answers["answer"].map(is_repetition_loop)
    answers["rating"] = ""
    sheet = OUT / "rating_sheet.csv"
    answers.sort_values(["id", "mode"]).to_csv(sheet, index=False, encoding="utf-8-sig")   # BOM: Excel shows Kinyarwanda right

    summary = answers.groupby("mode").agg(answers=("id", "size"), mean_chrf=("chrf", "mean"),
                                          loops=("loop", "sum"), mean_seconds=("seconds", "mean")).round(1)
    print(f"\n{model.name}\n{summary.to_string()}\n\nRate the answers in {sheet}")


if __name__ == "__main__":
    main()
