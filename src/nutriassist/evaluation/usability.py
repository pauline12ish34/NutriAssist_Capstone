"""System Usability Scale (SUS) scoring of the usability test's Google Form responses (``docs/usability_test.md``).

The form's questions are titled ``SUS 1.`` to ``SUS 10.`` and ``Task 1.`` to ``Task 5.``, so the
columns of the exported CSV are found by those prefixes, whatever the rest of the wording.
"""

from __future__ import annotations

import re
from typing import Sequence

import pandas as pd

N_ITEMS = 10
SUCCESS = "yes, without help"
# Bangor, Kortum & Miller (2009): mean SUS score -> adjective.
GRADES = ((80.3, "excellent"), (71.0, "good"), (68.0, "above average"), (51.0, "OK"), (0.0, "poor"))


def sus_score(answers: Sequence[int]) -> float:
    """0-100 score of one tester: odd items count answer - 1, even items 5 - answer, total x 2.5."""
    if len(answers) != N_ITEMS:
        raise ValueError(f"SUS needs {N_ITEMS} answers, got {len(answers)}")
    if any(not 1 <= a <= 5 for a in answers):
        raise ValueError(f"SUS answers must be 1-5, got {list(answers)}")
    return 2.5 * sum(a - 1 if i % 2 == 0 else 5 - a for i, a in enumerate(answers))


def grade(score: float) -> str:
    return next(label for threshold, label in GRADES if score >= threshold)


def _columns(responses: pd.DataFrame, prefix: str) -> list[str]:
    """Columns titled '<prefix> 1.', '<prefix> 2.', ... in number order."""
    found = {}
    for column in responses.columns:
        if match := re.match(rf"\s*{prefix}\s*(\d+)\b", str(column), re.IGNORECASE):
            found[int(match.group(1))] = column
    return [found[n] for n in sorted(found)]


def score_responses(responses: pd.DataFrame) -> pd.DataFrame:
    """One row per tester with their SUS score; testers who skipped a SUS question are left out."""
    items = _columns(responses, "SUS")
    if len(items) != N_ITEMS:
        raise ValueError(f"Expected columns 'SUS 1.' to 'SUS {N_ITEMS}.', found {len(items)}")
    complete = responses.dropna(subset=items)
    return complete.assign(sus=[sus_score([int(a) for a in row]) for row in complete[items].itertuples(index=False)])


def task_success(responses: pd.DataFrame) -> pd.Series:
    """Share of testers (%) who did each task without help."""
    tasks = _columns(responses, "Task")
    return pd.Series({column.split(".")[0]: 100 * float(responses[column].str.strip().str.lower().eq(SUCCESS).mean())
                      for column in tasks}, name="done_without_help_%")
