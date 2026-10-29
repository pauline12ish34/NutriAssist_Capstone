"""Evaluate the whole app pipeline (rules, reviewed answers, translation, model), not only the model.

Two parts:

1. **Matching study**: how often a reviewed answer is returned, and how often it is the right one,
   at each similarity threshold. Two kinds of questions are asked for a split (val or test):

   - *reworded*: the held-out paraphrases of the split's questions. Their original question is in
     the index, the paraphrase wording is not. The right answer is that question's answer.
   - *new*: the split's own questions, against an index of the training pairs only. No stored
     answer is right, so any match is a mistake (the pipeline should leave them to the model).

   The threshold is chosen on val (lowest threshold whose matches are at least 95% right) and then
   reported on test. Below the threshold the app offers three "Did you mean...?" suggestions, so the
   study also counts how often the right answer is among them (``in_suggestions``).

2. :class:`PipelineChatModel` lets :class:`~nutriassist.evaluation.Evaluator` score the pipeline
   with the same metrics as the model. When scoring the test split the index holds the training
   pairs only, so test answers cannot leak into the replies.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd

from ..assistant import AssistantReply, NutritionAssistant
from ..inference.base import ChatModel
from ..knowledge import EXTRA_WORDINGS, QA_MASTER, Embedder, KnowledgeBase
from ..prompts import Message
from ..training.dataset import ChatExample

THRESHOLDS = tuple(round(t, 2) for t in np.arange(0.40, 0.96, 0.05))
MIN_PRECISION = 95.0


def knowledge_for(split: str, path: str | Path = QA_MASTER, embedder: Embedder | None = None,
                  threshold: float = 0.0, extra_wordings: str | Path | None = EXTRA_WORDINGS,
                  letters_weight: float = 0.5) -> KnowledgeBase:
    """The index used when evaluating ``split``: training pairs only, with their paraphrases."""
    return KnowledgeBase.load(path, embedder, threshold, splits={"train"}, paraphrase_splits={"train"},
                              extra_wordings=extra_wordings, letters_weight=letters_weight)


def matching_study(split: str, paraphrases: Sequence[ChatExample], path: str | Path = QA_MASTER,
                   embedder: Embedder | None = None,
                   extra_wordings: str | Path | None = EXTRA_WORDINGS, letters_weight: float = 0.5) -> pd.DataFrame:
    """One row per question: its best match's score, whether that match's answer is right, and whether
    the right answer is among the "Did you mean...?" suggestions."""
    master = pd.read_json(path, lines=True)
    rows = []

    # Reworded questions: everything indexed except the held-out paraphrase wordings themselves.
    deployed = KnowledgeBase.load(path, embedder, 0.0, paraphrase_splits={"train"}, extra_wordings=extra_wordings,
                                  letters_weight=letters_weight)
    for example in (p for p in paraphrases if _split_of(p, master) == split):
        match = deployed.best(example.question, example.lang)
        suggested = [m.pair.answer for m in deployed.suggest(example.question, example.lang)]
        rows.append(_row("reworded", example.lang, example.question, match,
                         right=match is not None and match.pair.answer == example.answer,
                         in_suggestions=example.answer in suggested))

    # New questions: only training pairs indexed, so no match can be right.
    train_only = knowledge_for(split, path, embedder, extra_wordings=extra_wordings, letters_weight=letters_weight)
    for record in master[master["split"] == split].itertuples():
        match = train_only.best(record.question, record.lang)
        rows.append(_row("new", record.lang, record.question, match, right=False))
    return pd.DataFrame(rows)


def threshold_table(study: pd.DataFrame, thresholds: Iterable[float] = THRESHOLDS) -> pd.DataFrame:
    """Per language and threshold: % of reworded questions answered right, % of new questions wrongly
    matched, and precision (% of all returned reviewed answers that are right)."""
    rows = []
    for lang, group in [("all", study), *study.groupby("lang")]:
        reworded, new = group[group["kind"] == "reworded"], group[group["kind"] == "new"]
        for threshold in thresholds:
            accepted = group["score"] >= threshold
            right = int((accepted & group["right"]).sum())
            rows.append({
                "lang": lang, "threshold": threshold,
                "reworded_answered_right_%": 100 * right / max(len(reworded), 1),
                "new_wrongly_matched_%": 100 * float((new["score"] >= threshold).mean()) if len(new) else 0.0,
                "returned": int(accepted.sum()),
                "precision_%": 100 * right / accepted.sum() if accepted.any() else 100.0,
                # What the caregiver gets: the right answer directly, or among the three suggestions.
                "reworded_answered_or_suggested_%": _answered_or_suggested(reworded, threshold),
            })
    return pd.DataFrame(rows)


def choose_threshold(table: pd.DataFrame, min_precision: float = MIN_PRECISION) -> float:
    """The lowest threshold whose returned answers are at least ``min_precision`` % right in both languages."""
    per_language = table[table["lang"] != "all"]
    good = per_language.groupby("threshold")["precision_%"].min()
    passing = good[good >= min_precision]
    return float(passing.index.min()) if not passing.empty else float(table["threshold"].max())


class PipelineChatModel(ChatModel):
    """Answers like the app: ``NutritionAssistant.ask`` on the last user message.

    The replies are kept in ``replies`` (same order as the questions) to count which step answered.
    """

    def __init__(self, assistant: NutritionAssistant, name: str = "pipeline") -> None:
        super().__init__(assistant.model.settings)
        self.assistant = assistant
        self.name = name
        self.replies: list[AssistantReply] = []

    def generate_batch(self, conversations: Sequence[Sequence[Message]]) -> list[str]:
        replies = [self.assistant.ask(conversation[-1]["content"]) for conversation in conversations]
        self.replies.extend(replies)
        return [reply.answer for reply in replies]

    def sources(self) -> pd.DataFrame:
        return pd.DataFrame({"language": r.language, "source": r.source.value, "translated": r.translated}
                            for r in self.replies)


def _split_of(example: ChatExample, master: pd.DataFrame) -> str:
    """The split of the pair a paraphrase belongs to (paraphrase rows carry it in their id)."""
    return master.set_index("id").at[example.id, "split"] if example.id in set(master["id"]) else ""


def _answered_or_suggested(reworded: pd.DataFrame, threshold: float) -> float:
    if reworded.empty:
        return 0.0
    answered = reworded["score"] >= threshold
    suggested = reworded["in_suggestions"] if "in_suggestions" in reworded else False
    return 100 * float((answered & reworded["right"] | ~answered & suggested).mean())


def _row(kind: str, lang: str, question: str, match, right: bool, in_suggestions: bool = False) -> dict:
    return {"kind": kind, "lang": lang, "question": question,
            "matched_question": match.matched_question if match else None,
            "score": match.score if match else 0.0, "right": right, "in_suggestions": in_suggestions}
