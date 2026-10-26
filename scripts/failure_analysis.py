"""Sort the fine-tuned model's test answers into failure types, for the report's error analysis.

    python scripts/failure_analysis.py                    # writes the review sheet and the summary
    python scripts/failure_analysis.py --summary-only     # after review: recount from the sheet

Reads ``outputs/qualitative_test.csv`` (saved by the notebook, section 7). Two failure types are
found automatically:

- ``repetition_loop``: the answer repeats the same phrase (a 4-word sequence appears 3+ times);
- ``echoes_question``: the answer starts by restating the question.

The rest needs someone who reads the language, so the sheet
``data/QA_data/review/failure_review.xlsx`` has a ``label`` column (drop-down) for a native speaker:
``acceptable``, ``off_topic``, ``generic_food_list``, ``unsafe``, ``wrong_language``, ``other``.
The automatic flags are pre-filled as suggestions. Re-running keeps labels already given.
The summary (counts per language and failure type) goes to ``outputs/failure_summary.csv``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nutriassist.evaluation.metrics import is_repetition_loop, words  # noqa: E402
from nutriassist.language import LanguageDetector  # noqa: E402

PREDICTIONS = Path("outputs/qualitative_test.csv")
SHEET = Path("data/QA_data/review/failure_review.xlsx")
SUMMARY = Path("outputs/failure_summary.csv")
LABELS = ("acceptable", "repetition_loop", "echoes_question", "off_topic", "generic_food_list", "unsafe",
          "wrong_language", "other")
COLUMNS = [("id", 14), ("lang", 6), ("category", 16), ("question", 40), ("reference", 55), ("answer", 55),
           ("suggested", 18), ("label", 18), ("notes", 30)]


def echoes_question(question: str, answer: str, share: float = 0.7) -> bool:
    """Most of the question's words reappear, in order, at the start of the answer."""
    q, a = words(question), words(answer)[: len(words(question)) + 3]
    return len(q) >= 3 and sum(word in a for word in q) / len(q) >= share and a[:2] == q[:2]


def suggest(row: pd.Series, detect: LanguageDetector) -> str:
    if is_repetition_loop(row["answer"]):
        return "repetition_loop"
    if echoes_question(row["question"], row["answer"]):
        return "echoes_question"
    if detect(row["answer"]) != row["lang"]:
        return "wrong_language"
    return ""


def existing_labels(path: Path) -> dict[str, tuple[str, str]]:
    if not path.exists():
        return {}
    rows = load_workbook(path, read_only=True).active.iter_rows(values_only=True)
    header = list(next(rows))
    labels = {}
    for row in rows:
        entry = dict(zip(header, row))
        if entry.get("id"):
            labels[str(entry["id"])] = (str(entry.get("label") or ""), str(entry.get("notes") or ""))
    return labels


def write_sheet(answers: pd.DataFrame, path: Path) -> None:
    kept = existing_labels(path)
    book = Workbook()
    sheet = book.active
    sheet.title = "failures"
    sheet.append([name for name, _ in COLUMNS])
    for row in answers.itertuples():
        label, notes = kept.get(row.id, ("", ""))
        sheet.append([row.id, row.lang, row.category, row.question, row.reference, row.answer, row.suggested,
                      label, notes])
    for column, (name, width) in enumerate(COLUMNS, start=1):
        letter = sheet.cell(1, column).column_letter
        sheet.column_dimensions[letter].width = width
        sheet.cell(1, column).font = Font(bold=True)
        if name in ("label", "notes"):
            sheet.cell(1, column).fill = PatternFill("solid", fgColor="FFF2CC")
    for cells in sheet.iter_rows(min_row=2):
        for cell in cells:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    label_column = sheet.cell(1, [name for name, _ in COLUMNS].index("label") + 1).column_letter
    choices = DataValidation(type="list", formula1=f'"{",".join(LABELS)}"', allow_blank=True)
    choices.add(f"{label_column}2:{label_column}{sheet.max_row}")
    sheet.add_data_validation(choices)
    sheet.freeze_panes = "D2"
    path.parent.mkdir(parents=True, exist_ok=True)
    book.save(path)


def summary(answers: pd.DataFrame, labels: dict[str, tuple[str, str]]) -> pd.DataFrame:
    """Counts per language: the reviewer's label where given, else the automatic suggestion, else 'not reviewed'."""
    final = [labels.get(row.id, ("", ""))[0] or row.suggested or "not reviewed" for row in answers.itertuples()]
    counts = pd.crosstab(pd.Series(final, name="failure_type"), answers["lang"].rename("lang"), margins=True,
                         margins_name="total")
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--predictions", type=Path, default=PREDICTIONS)
    parser.add_argument("--column", default="fine_tuned_answer", help="answer column to analyse")
    parser.add_argument("--sheet", type=Path, default=SHEET)
    parser.add_argument("--summary-only", action="store_true", help="do not rewrite the sheet")
    args = parser.parse_args()

    answers = pd.read_csv(args.predictions).rename(columns={args.column: "answer"})
    detect = LanguageDetector()
    answers["suggested"] = answers.apply(suggest, axis=1, detect=detect)
    if not args.summary_only:
        write_sheet(answers, args.sheet)
        print(f"Review sheet: {args.sheet}")
    table = summary(answers, existing_labels(args.sheet))
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(SUMMARY)
    print(table.to_string())


if __name__ == "__main__":
    main()
