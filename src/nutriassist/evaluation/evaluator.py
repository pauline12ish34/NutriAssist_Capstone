"""Generate answers for a split and score them overall and per language."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence, runtime_checkable

import pandas as pd

from ..inference.base import ChatModel
from ..language import LanguageDetector
from ..training.dataset import ChatExample
from .metrics import ReferralDetector, TextMetrics, classification_scores, is_repetition_loop, numeric_scores

SAFETY_CATEGORY = "safety_redirect"
GROUPS = ("all", "en", "rw")
LOWER_IS_BETTER = frozenset({"perplexity"})


@runtime_checkable
class SupportsPerplexity(Protocol):
    def perplexity(self, examples: Sequence[ChatExample]) -> float: ...


@dataclass
class EvaluationResult:
    """Per-example predictions plus scores for ``all``, ``en`` and ``rw``."""

    predictions: pd.DataFrame
    scores: dict[str, dict[str, float]]

    def scores_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.scores).T.rename_axis("group")

    def save(self, directory: str | Path, tag: str) -> None:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        self.predictions.to_json(directory / f"{tag}_predictions.jsonl", orient="records", lines=True, force_ascii=False)
        (directory / f"{tag}_scores.json").write_text(json.dumps(self.scores, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, directory: str | Path, tag: str) -> "EvaluationResult":
        directory = Path(directory)
        predictions = pd.read_json(directory / f"{tag}_predictions.jsonl", orient="records", lines=True)
        scores = json.loads((directory / f"{tag}_scores.json").read_text(encoding="utf-8"))
        return cls(predictions, scores)

    @staticmethod
    def exists(directory: str | Path, tag: str) -> bool:
        return (Path(directory) / f"{tag}_scores.json").exists()


class Evaluator:
    """Scores a :class:`ChatModel` on a list of examples.

    Metrics per group: BLEU, chrF, ROUGE-L, perplexity (when the model can compute it),
    language-match accuracy (does the answer use the question's language?), referral
    classification scores against the reference answers, and the referral rate on
    danger-sign (``safety_redirect``) questions.
    """

    def __init__(self, text_metrics: TextMetrics | None = None, referrals: ReferralDetector | None = None,
                 language: LanguageDetector | None = None) -> None:
        self.text_metrics = text_metrics or TextMetrics()
        self.referrals = referrals or ReferralDetector()
        self.language = language or LanguageDetector()

    def evaluate(self, model: ChatModel, examples: Sequence[ChatExample], cache_path: str | Path | None = None,
                 chunk_size: int = 16) -> EvaluationResult:
        """Generate an answer per example and score them.

        With ``cache_path``, answers are appended to that file every ``chunk_size`` examples and
        reused on the next call, so an interrupted evaluation continues where it stopped.
        """
        answers = self._generate(model, examples, Path(cache_path) if cache_path else None, chunk_size)
        predictions = self.predictions_frame(examples, answers)
        scores = {}
        for group in GROUPS:
            subset = [i for i, ex in enumerate(examples) if group == "all" or ex.lang == group]
            if subset:
                scores[group] = self.score(model, [examples[i] for i in subset], predictions.iloc[subset])
        return EvaluationResult(predictions, scores)

    @staticmethod
    def _generate(model: ChatModel, examples: Sequence[ChatExample], cache_path: Path | None,
                  chunk_size: int) -> list[str]:
        if cache_path is None:
            return model.generate_batch([example.prompt_messages for example in examples])
        cached = _read_answer_cache(cache_path)
        missing = [ex for ex in examples if _cache_key(ex) not in cached]
        if cached and missing:
            print(f"Reusing {len(examples) - len(missing)} saved answers; generating {len(missing)}")
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        for start in range(0, len(missing), chunk_size):
            chunk = missing[start:start + chunk_size]
            answers = model.generate_batch([example.prompt_messages for example in chunk])
            with cache_path.open("a", encoding="utf-8") as handle:
                for example, answer in zip(chunk, answers):
                    cached[_cache_key(example)] = answer
                    handle.write(json.dumps({"key": _cache_key(example), "answer": answer}, ensure_ascii=False) + "\n")
        return [cached[_cache_key(example)] for example in examples]

    def predictions_frame(self, examples: Sequence[ChatExample], answers: Sequence[str]) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "id": ex.id, "lang": ex.lang, "category": ex.category,
                "question": ex.question, "reference": ex.answer, "prediction": answer,
                "answer_lang": self.language(answer),
                "is_safety_question": ex.category == SAFETY_CATEGORY,
                "reference_refers": self.referrals.refers(ex.answer),
                "prediction_refers": self.referrals.refers(answer),
            }
            for ex, answer in zip(examples, answers)
        )

    def score(self, model: ChatModel, examples: Sequence[ChatExample], predictions: pd.DataFrame) -> dict[str, float]:
        scores = self.text_metrics.score(predictions["reference"].tolist(), predictions["prediction"].tolist())
        if isinstance(model, SupportsPerplexity):
            scores["perplexity"] = model.perplexity(examples)
        scores["language_match_%"] = 100 * float((predictions["answer_lang"] == predictions["lang"]).mean())
        scores["repetition_loop_%"] = 100 * float(predictions["prediction"].map(is_repetition_loop).mean())
        referral = classification_scores(predictions["reference_refers"].tolist(),
                                         predictions["prediction_refers"].tolist())
        scores.update({f"referral_{name}_%": value for name, value in referral.as_percentages().items()})
        numeric = numeric_scores(predictions["reference"].tolist(), predictions["prediction"].tolist())
        if numeric.answers_scored:
            scores.update(numeric.as_percentages())
        danger = predictions[predictions["is_safety_question"]]
        if not danger.empty:
            scores["danger_referral_rate_%"] = 100 * float(danger["prediction_refers"].mean())
        return scores


def _cache_key(example: ChatExample) -> str:
    return f"{example.id}|{example.question}"


def _read_answer_cache(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    answers = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:  # a line cut off by a disconnect
                continue
            answers[row["key"]] = row["answer"]
    return answers


def compare(baseline: EvaluationResult, tuned: EvaluationResult) -> pd.DataFrame:
    """Base vs fine-tuned per group and metric, with the relative improvement in percent.

    Improvement is positive when the fine-tuned model is better, so for perplexity
    (lower is better) it is ``(base - tuned) / base``.
    """
    rows = []
    for group, base_scores in baseline.scores.items():
        for metric, base in base_scores.items():
            tuned_value = tuned.scores.get(group, {}).get(metric)
            if tuned_value is None:
                continue
            delta = base - tuned_value if metric in LOWER_IS_BETTER else tuned_value - base
            rows.append({
                "group": group, "metric": metric, "base": base, "fine_tuned": tuned_value,
                "improvement_%": 100 * delta / abs(base) if base else float("nan"),
            })
    return pd.DataFrame(rows)
