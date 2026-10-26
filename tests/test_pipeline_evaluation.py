"""The matching study, threshold choice and whole-pipeline scoring."""

import pandas as pd
import pytest

pytest.importorskip("sklearn")
pytest.importorskip("sacrebleu")

from conftest import make_example  # noqa: E402
from nutriassist.assistant import NutritionAssistant  # noqa: E402
from nutriassist.evaluation import Evaluator  # noqa: E402
from nutriassist.evaluation.pipeline import (PipelineChatModel, choose_threshold, knowledge_for,  # noqa: E402
                                             matching_study, threshold_table)
from nutriassist.inference.scripted import ScriptedChatModel  # noqa: E402


def study_rows(rows):
    return pd.DataFrame(rows, columns=["kind", "lang", "score", "right"])


def test_threshold_table_counts_right_and_wrong_matches():
    study = study_rows([
        ("reworded", "rw", 0.9, True), ("reworded", "rw", 0.5, True), ("new", "rw", 0.7, False),
        ("reworded", "en", 0.8, True), ("new", "en", 0.3, False),
    ])
    table = threshold_table(study, [0.6]).set_index("lang")
    assert table.loc["rw", "reworded_answered_right_%"] == 50
    assert table.loc["rw", "new_wrongly_matched_%"] == 100
    assert table.loc["rw", "precision_%"] == 50
    assert table.loc["en", "precision_%"] == 100


def test_chosen_threshold_is_the_lowest_precise_one_in_every_language():
    study = study_rows([
        ("reworded", "rw", 0.9, True), ("new", "rw", 0.7, False), ("reworded", "en", 0.65, True),
    ])
    table = threshold_table(study, [0.6, 0.75, 0.95])
    assert choose_threshold(table, min_precision=95) == 0.75


def test_evaluation_index_holds_training_pairs_only(qa_dataset):
    master = pd.read_json("data/QA_data/processed/qa_master.jsonl", lines=True)
    kb = knowledge_for("test")
    assert len(kb) == (master["split"] == "train").sum()
    test_answers = {ex.answer for ex in qa_dataset.test}
    assert all(kb.best(ex.question, ex.lang) is None or kb.best(ex.question, ex.lang).pair.answer not in test_answers
               for ex in qa_dataset.test[:10])


def test_matching_study_has_reworded_and_new_questions(qa_dataset):
    study = matching_study("val", qa_dataset.paraphrases)
    assert set(study["kind"]) == {"reworded", "new"} and set(study["lang"]) == {"en", "rw"}
    assert not study.loc[study["kind"] == "new", "right"].any()


def test_pipeline_model_is_scored_like_any_model():
    assistant = NutritionAssistant(ScriptedChatModel(lambda q: "Give beans."))
    pipeline = PipelineChatModel(assistant)
    result = Evaluator().evaluate(pipeline, [make_example("What can she eat?", "Give beans.")])
    assert result.scores["all"]["chrF"] == pytest.approx(100)
    assert pipeline.sources()["source"].tolist() == ["model"]
