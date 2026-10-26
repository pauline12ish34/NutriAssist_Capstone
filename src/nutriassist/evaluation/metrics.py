"""Scores for generated answers.

- Text overlap with the reference answer: BLEU, chrF and ROUGE-L. chrF compares
  character n-grams, which suits Kinyarwanda: one word carries many prefixes
  and suffixes, so whole-word metrics like BLEU under-credit near misses.
- Referral as a binary classification: does the answer send the caregiver to
  a health centre or health worker? The reference answer gives the true label
  and the generated answer the prediction, which yields accuracy, precision,
  recall and F1. The label comes from the reference rather than the question
  category because good everyday advice also refers ("weigh your child at the
  health centre every month").
- Repetition loops: the answer repeats one phrase (a 4-word sequence appears 3+
  times). Overlap metrics can rise while answers loop, so loops are counted apart.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Sequence

from rouge_score import rouge_scorer
from sacrebleu.metrics import BLEU, CHRF

from ..safety.referral import ReferralDetector  # noqa: F401  (re-exported for evaluation users)

_WORD = re.compile(r"\w+(?:'\w+)?", re.UNICODE)


def words(text: str) -> list[str]:
    return _WORD.findall(str(text).lower())


def is_repetition_loop(answer: str, n: int = 4, times: int = 3) -> bool:
    tokens = words(answer)
    counts = Counter(tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1))
    return bool(counts) and max(counts.values()) >= times


@dataclass(frozen=True)
class ClassificationScores:
    accuracy: float
    precision: float
    recall: float
    f1: float
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int

    def as_percentages(self) -> dict[str, float]:
        return {k: 100 * v for k, v in asdict(self).items() if isinstance(v, float)}


def classification_scores(actual: Sequence[bool], predicted: Sequence[bool]) -> ClassificationScores:
    """Binary accuracy, precision, recall and F1. Undefined ratios (0/0) are reported as 0."""
    if len(actual) != len(predicted):
        raise ValueError(f"{len(actual)} labels but {len(predicted)} predictions")
    tp = sum(a and p for a, p in zip(actual, predicted))
    fp = sum(p and not a for a, p in zip(actual, predicted))
    fn = sum(a and not p for a, p in zip(actual, predicted))
    tn = len(actual) - tp - fp - fn
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    accuracy = (tp + tn) / len(actual) if actual else 0.0
    return ClassificationScores(accuracy, precision, recall, f1, tp, fp, fn, tn)


class TextMetrics:
    """Corpus BLEU and chrF (sacrebleu) and mean ROUGE-L F1, all on a 0-100 scale."""

    def __init__(self) -> None:
        self._bleu = BLEU()
        self._chrf = CHRF()
        self._rouge = rouge_scorer.RougeScorer(["rougeL"])

    def score(self, references: Sequence[str], predictions: Sequence[str]) -> dict[str, float]:
        if len(references) != len(predictions):
            raise ValueError(f"{len(references)} references but {len(predictions)} predictions")
        if not references:
            return {"BLEU": 0.0, "chrF": 0.0, "ROUGE-L": 0.0}
        rouge = [self._rouge.score(ref, pred)["rougeL"].fmeasure for ref, pred in zip(references, predictions)]
        return {
            "BLEU": self._bleu.corpus_score(list(predictions), [list(references)]).score,
            "chrF": self._chrf.corpus_score(list(predictions), [list(references)]).score,
            "ROUGE-L": 100 * sum(rouge) / len(rouge),
        }
