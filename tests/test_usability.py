import pandas as pd
import pytest

from nutriassist.evaluation.usability import grade, score_responses, sus_score, task_success


@pytest.mark.parametrize("answers, expected", [
    ([5, 1] * 5, 100.0),   # agrees with every positive item, disagrees with every negative one
    ([1, 5] * 5, 0.0),
    ([3] * 10, 50.0),
    ([4, 2, 4, 1, 4, 2, 5, 1, 4, 2], 82.5),
])
def test_sus_score(answers, expected):
    assert sus_score(answers) == expected


@pytest.mark.parametrize("answers", [[3] * 9, [0] + [3] * 9, [6] + [3] * 9])
def test_invalid_answers(answers):
    with pytest.raises(ValueError):
        sus_score(answers)


@pytest.mark.parametrize("score, label", [(85, "excellent"), (75, "good"), (68, "above average"), (40, "poor")])
def test_grade(score, label):
    assert grade(score) == label


def google_form_export():
    """Columns as Google Forms exports them: timestamp, then the question titles."""
    sus = {f"SUS {n}. Statement number {n}.": [5 if n % 2 else 1, 3, None] for n in range(1, 11)}
    tasks = {"Task 1. Open the app": ["Yes, without help", "Yes, with some help", "Yes, without help"],
             "Task 2. Ask a question": ["Yes, without help", "No", "Yes, without help"]}
    return pd.DataFrame({"Timestamp": ["t1", "t2", "t3"], **tasks, **sus})


def test_responses_are_scored_by_title_and_incomplete_ones_skipped():
    scored = score_responses(google_form_export())
    assert scored["sus"].tolist() == [100.0, 50.0]


def test_task_success():
    success = task_success(google_form_export())
    assert success["Task 1"] == pytest.approx(200 / 3) and success["Task 2"] == pytest.approx(200 / 3)


def test_missing_sus_columns_are_reported():
    with pytest.raises(ValueError, match="SUS 1"):
        score_responses(pd.DataFrame({"SUS 1. Only one": [3]}))
