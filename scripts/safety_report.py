"""How often the app sends caregivers to a health worker when they need it, on the test questions.

    python scripts/safety_report.py
    python scripts/safety_report.py --predictions outputs/qualitative_test.csv

Uses the test answers saved by the training notebook (section 7, ``qualitative_test.csv``), so the
model does not need to run. The app answers a question in two steps: the danger-sign rules first,
then the fine-tuned model. This scores each step alone and both together, which is what users get.
A question needs a referral when its reviewed reference answer refers the caregiver.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nutriassist.evaluation.metrics import classification_scores  # noqa: E402
from nutriassist.safety.detector import DangerSignDetector  # noqa: E402
from nutriassist.safety.referral import ReferralDetector  # noqa: E402
from nutriassist.safety.rules import SafetyLevel  # noqa: E402

DEFAULT_PREDICTIONS = Path("outputs/qualitative_test.csv")


def referral_decisions(answers: pd.DataFrame) -> pd.DataFrame:
    """For each question: does the reference refer, do the rules fire, does the model refer."""
    rules, referral = DangerSignDetector(), ReferralDetector()
    return pd.DataFrame({
        "needs_referral": answers["reference"].map(referral.refers),
        "base model": answers["base_answer"].map(referral.refers),
        "safety rules only": answers["question"].map(lambda q: rules.assess(q).level > SafetyLevel.NONE),
        "fine-tuned model only": answers["fine_tuned_answer"].map(referral.refers),
        "is_danger_question": answers["category"] == "safety_redirect",
    }).assign(**{"app (rules + model)": lambda d: d["safety rules only"] | d["fine-tuned model only"]})


def report(decisions: pd.DataFrame) -> pd.DataFrame:
    danger = decisions["is_danger_question"]
    rows = {}
    for system in ["base model", "safety rules only", "fine-tuned model only", "app (rules + model)"]:
        scores = classification_scores(decisions["needs_referral"].tolist(), decisions[system].tolist())
        rows[system] = {
            "danger questions referred": f"{decisions.loc[danger, system].sum()}/{danger.sum()}",
            "danger referral %": 100 * decisions.loc[danger, system].mean(),
            **{f"{name} %": value for name, value in scores.as_percentages().items()},
        }
    return pd.DataFrame(rows).T


def main() -> None:
    parser = argparse.ArgumentParser(description="Safety-referral scores of the rules, the model and the app")
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    args = parser.parse_args()
    if not args.predictions.exists():
        sys.exit(f"{args.predictions} not found: copy qualitative_test.csv from the notebook outputs into outputs/.")

    answers = pd.read_csv(args.predictions)
    table = report(referral_decisions(answers))
    print(f"Safety referrals on {len(answers)} test questions "
          f"({(answers['category'] == 'safety_redirect').sum()} danger-sign questions)\n")
    print(table.to_string(float_format=lambda v: f"{v:.1f}"))


if __name__ == "__main__":
    main()
