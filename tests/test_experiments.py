from dataclasses import dataclass
from pathlib import Path

import pytest

from conftest import make_example
from nutriassist.inference.scripted import ScriptedChatModel
from nutriassist.training.config import TRAINING_SUMMARY_FILE, TrainingConfig
from nutriassist.training.dataset import QADataset
from nutriassist.training.experiments import ExperimentRunner


@dataclass
class FakeRun:
    config: TrainingConfig
    adapter_dir: Path

    def summary(self):
        return {"experiment": self.config.name, "learning_rate": self.config.learning_rate,
                "val_loss": 1.0 / self.config.lora_rank, "train_minutes": 0.1}


class FakeFineTuner:
    """Trains nothing; answers well only when the rank is high, so experiments differ."""

    trained: list[str] = []

    def __init__(self, config, adapters_dir):
        self.config = config
        self.adapter_dir = Path(adapters_dir) / config.name

    def train(self, dataset):
        FakeFineTuner.trained.append(self.config.name)
        self.adapter_dir.mkdir(parents=True)
        good = self.config.lora_rank >= 16
        answers = {ex.question: ex.answer for ex in dataset.val}
        model = ScriptedChatModel(lambda q: answers[q] if good else "Something else entirely.")
        return model, FakeRun(self.config, self.adapter_dir)


@pytest.fixture
def runner(tmp_path):
    FakeFineTuner.trained = []
    dataset = QADataset(train=[make_example()], val=[make_example("Q1?", "Give beans."), make_example("Q2?", "Give milk.")],
                        test=[])
    return ExperimentRunner(dataset, tmp_path, fine_tuner_factory=lambda c: FakeFineTuner(c, tmp_path / "adapters"))


def test_runs_each_config_and_records_validation_scores(runner):
    base = TrainingConfig(name="rank_16")
    results = runner.run([base, base.variant("rank_4", lora_rank=4)])

    assert results["experiment"].tolist() == ["rank_16", "rank_4"]
    assert results.set_index("experiment").loc["rank_16", "val_ROUGE-L"] == pytest.approx(100)
    assert runner.best() == "rank_16"
    assert (runner.predictions_dir / "rank_4_val_predictions.jsonl").exists()


def test_finished_experiments_are_skipped_on_rerun(runner):
    config = TrainingConfig(name="rank_16")
    runner.run([config])
    runner.run([config, config.variant("rank_32", lora_rank=32)])
    assert FakeFineTuner.trained == ["rank_16", "rank_32"]
    assert len(runner.results()) == 2


def test_duplicate_names_are_rejected(runner):
    with pytest.raises(ValueError, match="unique"):
        runner.run([TrainingConfig(name="a"), TrainingConfig(name="a")])


def test_best_needs_results(runner):
    with pytest.raises(ValueError):
        runner.best()


def test_finished_training_is_scored_without_retraining(tmp_path):
    """Training finished but the session died before the validation scores were saved."""
    FakeFineTuner.trained = []
    dataset = QADataset(train=[make_example()], val=[make_example("Q1?", "Give beans.")], test=[])
    adapter_dir = tmp_path / "adapters" / "rank_16"
    adapter_dir.mkdir(parents=True)
    (adapter_dir / TRAINING_SUMMARY_FILE).write_text('{"experiment": "rank_16", "train_minutes": 7.5}')
    loaded = []

    def load_adapter(config, path):
        loaded.append(path)
        return ScriptedChatModel(lambda q: "Give beans.")

    runner = ExperimentRunner(dataset, tmp_path, fine_tuner_factory=lambda c: FakeFineTuner(c, tmp_path / "adapters"),
                              adapter_loader=load_adapter)
    row = runner.run([TrainingConfig(name="rank_16")]).iloc[0]
    assert FakeFineTuner.trained == []
    assert loaded == [adapter_dir]
    assert row["train_minutes"] == 7.5 and row["val_ROUGE-L"] == pytest.approx(100)
