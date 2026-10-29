"""Numeric accuracy of the base and fine-tuned models on the test questions (the proposal's RQ1 / H1).

    python scripts/numeric_accuracy.py
    python scripts/numeric_accuracy.py --predictions outputs/qualitative_test.csv --tolerance 0.10

Uses the test answers saved by the training notebook (section 7, ``qualitative_test.csv``), so the
model does not need to run. Numeric accuracy is the share of the reference answer's numbers (ages,
amounts, meals a day, MUAC cut-offs...) that the answer gives within the tolerance; numeric precision
is the share of the answer's numbers that are in the reference, so invented numbers lower it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nutriassist.evaluation.metrics import numeric_scores  # noqa: E402

DEFAULT_PREDICTIONS = Path("outputs/qualitative_test.csv")
MODELS = {"base model": "base_answer", "fine-tuned model": "fine_tuned_answer"}


def report(answers: pd.DataFrame, tolerance: float) -> pd.DataFrame:
    rows = []
    for language, group in [("all", answers), *answers.groupby("lang")]:
        for model, column in MODELS.items():
            scores = numeric_scores(group["reference"].tolist(), group[column].tolist(), tolerance)
            rows.append({"language": language, "model": model, "answers scored": scores.answers_scored,
                         **scores.as_percentages()})
    return pd.DataFrame(rows).set_index(["language", "model"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Numeric accuracy of the base and fine-tuned models")
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--tolerance", type=float, default=0.10, help="relative tolerance (0.10 = ±10%%)")
    args = parser.parse_args()
    if not args.predictions.exists():
        sys.exit(f"{args.predictions} not found: copy qualitative_test.csv from the notebook outputs into outputs/.")

    answers = pd.read_csv(args.predictions)
    table = report(answers, args.tolerance)
    print(f"Numeric accuracy on {len(answers)} test questions, tolerance ±{100 * args.tolerance:.0f}%\n")
    print(table.to_string(float_format=lambda v: f"{v:.1f}"))
    for language in table.index.get_level_values("language").unique():
        base, tuned = (table.loc[(language, m), "numeric_accuracy_%"] for m in MODELS)
        print(f"\n{language}: {tuned - base:+.1f} percentage points (proposal target: +20)", end="")
    print()


if __name__ == "__main__":
    main()
