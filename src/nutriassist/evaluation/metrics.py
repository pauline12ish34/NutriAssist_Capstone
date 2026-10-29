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
- Numeric accuracy (the proposal's main metric): the share of the numbers in the
  reference answer (ages in months, amounts, times a day, MUAC cut-offs...) that
  the answer gives within ±10%. Its precision counterpart, the share of the
  answer's numbers found in the reference, catches invented numbers. Only
  answers whose reference contains a number are scored.
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


# A number not glued to letters ("11.5", "1,5", "6"); "1,000" is a thousand, other commas are decimals.
_NUMBER = re.compile(r"(?<![\w.,])(\d+(?:,\d{3})+|\d+(?:[.,]\d+)?)(?![\w])")
_LIST_MARKER = re.compile(r"^\s*\d+[.)]\s", re.MULTILINE)   # "1. Give porridge" numbers a list item, not a fact
_NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
                 "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "half": 0.5}
_NUMBER_WORD = re.compile(r"\b(" + "|".join(_NUMBER_WORDS) + r")\b", re.IGNORECASE)


def numbers(text: str) -> list[float]:
    """The numbers stated in a text, in digits or as English words up to twelve."""
    text = _LIST_MARKER.sub("", str(text))
    text = re.sub(r"(\d)½", r"\1.5", text).replace("½", "0.5")   # "ibiyiko 2½"
    found = []
    for match in _NUMBER.findall(text):
        found.append(float(match.replace(",", "") if re.fullmatch(r"\d+(?:,\d{3})+", match)
                           else match.replace(",", ".")))
    found += [float(_NUMBER_WORDS[word.lower()]) for word in _NUMBER_WORD.findall(text)]
    return found


def _close(value: float, candidates: Sequence[float], tolerance: float) -> bool:
    return any(abs(value - c) <= tolerance * abs(c) for c in candidates)


@dataclass(frozen=True)
class NumericScores:
    accuracy: float      # reference numbers the answer gives within the tolerance
    precision: float     # answer numbers that appear in the reference
    answers_scored: int  # answers whose reference contains a number

    def as_percentages(self) -> dict[str, float]:
        return {"numeric_accuracy_%": 100 * self.accuracy, "numeric_precision_%": 100 * self.precision}


def numeric_scores(references: Sequence[str], predictions: Sequence[str], tolerance: float = 0.10) -> NumericScores:
    """Pooled over all scored answers, so an answer with many numbers counts for more."""
    if len(references) != len(predictions):
        raise ValueError(f"{len(references)} references but {len(predictions)} predictions")
    matched = expected = correct = given = scored = 0
    for reference, prediction in zip(references, predictions):
        wanted = numbers(reference)
        if not wanted:
            continue
        stated = numbers(prediction)
        scored += 1
        expected += len(wanted)
        matched += sum(_close(n, stated, tolerance) for n in wanted)
        given += len(stated)
        correct += sum(_close(n, wanted, tolerance) for n in stated)
    return NumericScores(matched / expected if expected else 0.0, correct / given if given else 0.0, scored)


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
