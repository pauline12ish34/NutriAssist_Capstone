"""Score the usability test: SUS per tester, mean and grade, task success, devices and browsers.

    python scripts/sus_score.py data/usability/sus_responses.csv

The CSV is the Google Form export (Responses -> Download responses). See docs/usability_test.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nutriassist.evaluation.usability import grade, score_responses, task_success  # noqa: E402

DESCRIPTIVE = ("Device", "Operating system", "Browser", "Language you mostly used in the app")


def main() -> None:
    parser = argparse.ArgumentParser(description="System Usability Scale score of the usability test")
    parser.add_argument("responses", type=Path, nargs="?", default=Path("data/usability/sus_responses.csv"))
    args = parser.parse_args()
    if not args.responses.exists():
        sys.exit(f"{args.responses} not found: download the Google Form responses as CSV (docs/usability_test.md).")

    responses = pd.read_csv(args.responses)
    scored = score_responses(responses)
    mean, sd = scored["sus"].mean(), scored["sus"].std()
    print(f"SUS: {mean:.1f} ± {sd:.1f} from {len(scored)} testers ({grade(mean)}; 68 is average)")
    print("Per tester:", ", ".join(f"{s:.1f}" for s in scored["sus"]))
    print("\nTasks done without help:")
    print(task_success(responses).to_string(float_format=lambda v: f"{v:.0f}%"))
    for column in DESCRIPTIVE:
        if column in responses:
            print(f"\n{column}: " + ", ".join(f"{k} ({v})" for k, v in responses[column].value_counts().items()))


if __name__ == "__main__":
    main()
