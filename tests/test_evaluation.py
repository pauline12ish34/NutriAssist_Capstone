from types import SimpleNamespace

import pytest

from conftest import make_example
from nutriassist.evaluation.evaluator import EvaluationResult, Evaluator, compare
from nutriassist.evaluation.metrics import ReferralDetector, TextMetrics, classification_scores, is_repetition_loop
from nutriassist.inference.scripted import ScriptedChatModel
from nutriassist.training.architecture import architecture_summary, lora_target_modules


class TestRepetitionLoop:
    def test_phrase_repeated_three_times_is_a_loop(self):
        assert is_repetition_loop("amazi meza n'ibishyimbo, " * 4)

    def test_phrase_repeated_twice_is_not(self):
        assert not is_repetition_loop("Go to the health centre. If it gets worse, go to the health centre.")
        assert not is_repetition_loop("")


class TestClassificationScores:
    def test_known_confusion_matrix(self):
        # 3 positives (2 found), 3 negatives (1 false alarm)
        scores = classification_scores([True, True, True, False, False, False], [True, True, False, True, False, False])
        assert (scores.true_positives, scores.false_positives, scores.false_negatives, scores.true_negatives) == (2, 1, 1, 2)
        assert scores.precision == pytest.approx(2 / 3)
        assert scores.recall == pytest.approx(2 / 3)
        assert scores.f1 == pytest.approx(2 / 3)
        assert scores.accuracy == pytest.approx(4 / 6)

    def test_no_positive_predictions_gives_zero_not_an_error(self):
        scores = classification_scores([True, False], [False, False])
        assert scores.precision == 0.0 and scores.f1 == 0.0

    def test_length_mismatch(self):
        with pytest.raises(ValueError):
            classification_scores([True], [True, False])


class TestReferralDetector:
    @pytest.mark.parametrize("text", [
        "Take the child to the health centre today.",
        "Go to the nearest Health Center.",
        "Mujyane ku kigo nderabuzima vuba.",
        "Jya kwa muganga.",
        "Baza umujyanama w'ubuzima.",
        "Healthcare providers typically prescribe vitamin A.",
        "Abaganga bakunze kwandika antibiyotike.",
    ])
    def test_finds_referrals_in_both_languages(self, text):
        assert ReferralDetector().refers(text)

    def test_ignores_plain_feeding_advice(self):
        assert not ReferralDetector().refers("Give mashed beans and avocado twice a day.")


class TestTextMetrics:
    def test_identical_answers_score_100(self):
        scores = TextMetrics().score(["Give porridge with milk."], ["Give porridge with milk."])
        assert scores["BLEU"] == pytest.approx(100) and scores["ROUGE-L"] == pytest.approx(100)

    def test_unrelated_answers_score_low(self):
        scores = TextMetrics().score(["Give porridge with milk."], ["The sky is blue today."])
        assert scores["ROUGE-L"] < 20 and scores["chrF"] < 30


class PerplexityModel(ScriptedChatModel):
    def __init__(self, value, responder=None):
        super().__init__(responder)
        self.value = value

    def perplexity(self, examples):
        return self.value


class TestEvaluator:
    examples = [
        make_example("What should I do?", "Go to the health centre now.", "en", "safety_redirect", "s-1"),
        make_example("What can she eat?", "Give mashed beans and avocado.", "en", "feeding_by_age", "f-1"),
        make_example("Yarya iki?", "Muhe ibishyimbo biseye na avoka.", "rw", "feeding_by_age", "f-2"),
    ]

    def test_perfect_model_scores(self):
        answers = {ex.question: ex.answer for ex in self.examples}
        result = Evaluator().evaluate(PerplexityModel(1.5, answers.get), self.examples)

        overall = result.scores["all"]
        assert overall["ROUGE-L"] == pytest.approx(100)
        assert overall["perplexity"] == 1.5
        assert overall["language_match_%"] == 100
        assert overall["referral_recall_%"] == 100 and overall["referral_precision_%"] == 100
        assert overall["danger_referral_rate_%"] == 100
        assert set(result.scores) == {"all", "en", "rw"}
        assert result.predictions["prediction_refers"].tolist() == [True, False, False]

    def test_wrong_language_and_missed_referral_are_counted(self):
        result = Evaluator().evaluate(ScriptedChatModel(lambda q: "Give the child porridge."), self.examples)
        assert result.scores["all"]["referral_recall_%"] == 0
        assert result.scores["all"]["danger_referral_rate_%"] == 0
        assert result.scores["rw"]["language_match_%"] == 0
        assert "perplexity" not in result.scores["all"]   # the scripted model cannot compute it

    def test_repetition_loops_are_counted_per_language(self):
        loop = "amazi meza n'ibishyimbo, " * 4
        result = Evaluator().evaluate(ScriptedChatModel(lambda q: loop if q == "Yarya iki?" else "Give beans."),
                                      self.examples)
        assert result.scores["rw"]["repetition_loop_%"] == 100
        assert result.scores["en"]["repetition_loop_%"] == 0

    def test_save_and_load_round_trip(self, tmp_path):
        result = Evaluator().evaluate(ScriptedChatModel(), self.examples)
        result.save(tmp_path, "base_val")
        loaded = EvaluationResult.load(tmp_path, "base_val")
        assert EvaluationResult.exists(tmp_path, "base_val")
        assert loaded.scores == result.scores
        assert loaded.predictions["prediction"].tolist() == result.predictions["prediction"].tolist()

    def test_compare_treats_lower_perplexity_as_improvement(self):
        base = EvaluationResult(None, {"all": {"perplexity": 10.0, "ROUGE-L": 20.0}})
        tuned = EvaluationResult(None, {"all": {"perplexity": 5.0, "ROUGE-L": 30.0}})
        table = compare(base, tuned).set_index("metric")
        assert table.loc["perplexity", "improvement_%"] == pytest.approx(50)
        assert table.loc["ROUGE-L", "improvement_%"] == pytest.approx(50)


def test_architecture_summary_reads_config_fields():
    config = SimpleNamespace(model_type="qwen2", num_hidden_layers=28, hidden_size=1536, num_attention_heads=12,
                             hidden_act="silu")
    summary = architecture_summary(config)
    assert summary["Decoder layers (transformer blocks)"] == 28
    assert summary["MLP activation function"] == "silu"
    assert summary["Head dimension"] == 128


def test_lora_target_modules_from_module_names():
    names = ["model.layers.0.self_attn.q_proj", "model.layers.0.self_attn.q_proj.lora_A",
             "model.layers.0.self_attn.q_proj.lora_A.default", "model.layers.0.mlp.down_proj.lora_A",
             "model.layers.1.mlp.down_proj.lora_A"]
    assert lora_target_modules(names) == ["down_proj", "q_proj"]


class FlakyModel(ScriptedChatModel):
    """Answers ``fail_after`` questions, then fails like a Colab disconnect."""

    def __init__(self, fail_after=None):
        super().__init__(lambda q: f"answer to {q}")
        self.fail_after = fail_after

    def generate_batch(self, conversations):
        if self.fail_after is not None and len(self.calls) + len(conversations) > self.fail_after:
            raise RuntimeError("disconnected")
        return super().generate_batch(conversations)


class TestResumableEvaluation:
    examples = [make_example(f"Question {i}?", f"Answer {i}.", id=f"q-{i}") for i in range(7)]

    def test_interrupted_evaluation_reuses_saved_answers(self, tmp_path):
        cache = tmp_path / "val_answers.jsonl"
        with pytest.raises(RuntimeError):
            Evaluator().evaluate(FlakyModel(fail_after=4), self.examples, cache_path=cache, chunk_size=2)
        assert len(cache.read_text(encoding="utf-8").splitlines()) == 4   # two chunks were saved

        resumed = FlakyModel()
        result = Evaluator().evaluate(resumed, self.examples, cache_path=cache, chunk_size=2)
        assert resumed.calls == [ex.question for ex in self.examples[4:]]   # only the missing ones
        assert result.predictions["prediction"].tolist() == [f"answer to {ex.question}" for ex in self.examples]

    def test_a_line_cut_off_by_a_disconnect_is_ignored(self, tmp_path):
        cache = tmp_path / "answers.jsonl"
        cache.write_text('{"key": "q-0|Question 0?", "answer": "saved"}\n{"key": "q-1|Quest', encoding="utf-8")
        model = FlakyModel()
        result = Evaluator().evaluate(model, self.examples[:2], cache_path=cache)
        assert result.predictions["prediction"].tolist() == ["saved", "answer to Question 1?"]
        assert model.calls == ["Question 1?"]
