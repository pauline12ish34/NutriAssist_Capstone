"""Run a list of training configurations and collect one results row per run.

Results are written after every run and finished runs are skipped, so a Colab
disconnect costs at most the run that was in progress.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Protocol, Sequence

import pandas as pd

from ..evaluation.evaluator import Evaluator
from ..inference.base import ChatModel
from .config import TrainingConfig
from .dataset import QADataset


class FineTuner(Protocol):
    def train(self, dataset: QADataset) -> tuple[ChatModel, "TrainingRunLike"]: ...


class TrainingRunLike(Protocol):
    adapter_dir: Path

    def summary(self) -> dict: ...


FineTunerFactory = Callable[[TrainingConfig], FineTuner]


class ExperimentRunner:
    """Trains each configuration, scores it on the validation split and appends a row to ``experiments.csv``.

    Model selection uses validation scores only; the test split stays untouched until
    the final evaluation of the chosen experiment.
    """

    def __init__(self, dataset: QADataset, output_dir: str | Path, evaluator: Evaluator | None = None,
                 fine_tuner_factory: FineTunerFactory | None = None, checkpoints_dir: str | Path | None = None) -> None:
        self.dataset = dataset
        self.output_dir = Path(output_dir)
        self.adapters_dir = self.output_dir / "adapters"
        self.predictions_dir = self.output_dir / "predictions"
        self.results_path = self.output_dir / "experiments.csv"
        self.checkpoints_dir = Path(checkpoints_dir) if checkpoints_dir else self.output_dir / "checkpoints"
        self.evaluator = evaluator or Evaluator()
        self.fine_tuner_factory = fine_tuner_factory or self._qlora_fine_tuner

    def results(self) -> pd.DataFrame:
        return pd.read_csv(self.results_path) if self.results_path.exists() else pd.DataFrame()

    def is_finished(self, config: TrainingConfig) -> bool:
        results = self.results()
        return (not results.empty and config.name in set(results["experiment"])
                and (self.adapters_dir / config.name).exists())

    def run(self, configs: Sequence[TrainingConfig]) -> pd.DataFrame:
        names = [c.name for c in configs]
        if len(set(names)) != len(names):
            raise ValueError(f"Experiment names must be unique: {names}")
        for config in configs:
            if self.is_finished(config):
                print(f"Skipping {config.name}: already in {self.results_path.name}")
                continue
            self._save_row(self.run_one(config))
        return self.results()

    def run_one(self, config: TrainingConfig) -> dict:
        model, run = self.fine_tuner_factory(config).train(self.dataset)
        validation = self.evaluator.evaluate(model, self.dataset.val)
        validation.save(self.predictions_dir, f"{config.name}_val")
        del model
        self._release_memory()
        return {**run.summary(), **{f"val_{k}": round(v, 3) for k, v in validation.scores["all"].items()}}

    def best(self, metric: str = "val_ROUGE-L", tie_breaker: str = "val_loss") -> str:
        """Name of the experiment with the highest ``metric``; the lowest ``tie_breaker`` breaks ties."""
        results = self.results()
        if results.empty:
            raise ValueError("No finished experiments yet")
        return results.sort_values([metric, tie_breaker], ascending=[False, True]).iloc[0]["experiment"]

    def _save_row(self, row: dict) -> None:
        results = self.results()
        if not results.empty:
            results = results[results["experiment"] != row["experiment"]]
        self.output_dir.mkdir(parents=True, exist_ok=True)
        pd.concat([results, pd.DataFrame([row])], ignore_index=True).to_csv(self.results_path, index=False)

    def _qlora_fine_tuner(self, config: TrainingConfig) -> FineTuner:
        from .finetune import QLoRAFineTuner  # imported lazily: needs torch and a GPU

        return QLoRAFineTuner(config, self.adapters_dir, self.checkpoints_dir)

    @staticmethod
    def _release_memory() -> None:
        try:
            from .finetune import free_gpu_memory
        except ImportError:  # no torch installed (tests)
            return
        free_gpu_memory()
