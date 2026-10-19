"""Load the train / val / test / paraphrase splits written by ``nutriassist.qa_data``."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from ..prompts import Message

SPLIT_FILES = {
    "train": "train.jsonl",
    "val": "val.jsonl",
    "test": "test.jsonl",
    "paraphrases": "heldout_paraphrases.jsonl",
}


@dataclass(frozen=True)
class ChatExample:
    """One question-answer pair in chat format, with the metadata used for per-group scores."""

    messages: tuple[Message, ...]
    id: str = ""
    lang: str = ""
    category: str = ""

    @classmethod
    def from_dict(cls, row: dict) -> "ChatExample":
        roles = [m["role"] for m in row["messages"]]
        if roles != ["system", "user", "assistant"]:
            raise ValueError(f"Expected system/user/assistant messages, got {roles} in {row.get('id', '?')}")
        return cls(tuple(row["messages"]), row.get("id", ""), row.get("lang", ""), row.get("category", ""))

    @property
    def prompt_messages(self) -> list[Message]:
        """System and user turns: what the model sees at inference time."""
        return list(self.messages[:2])

    @property
    def question(self) -> str:
        return self.messages[1]["content"]

    @property
    def answer(self) -> str:
        return self.messages[2]["content"]


@dataclass
class QADataset:
    """The four splits. ``paraphrases`` are reworded val/test questions used only for evaluation."""

    train: list[ChatExample]
    val: list[ChatExample]
    test: list[ChatExample]
    paraphrases: list[ChatExample] = field(default_factory=list)

    @classmethod
    def load(cls, data_dir: str | Path) -> "QADataset":
        data_dir = Path(data_dir)
        missing = [name for name in SPLIT_FILES.values() if not (data_dir / name).exists()]
        if missing:
            raise FileNotFoundError(f"Missing {missing} in {data_dir}")
        return cls(**{split: _read_examples(data_dir / name) for split, name in SPLIT_FILES.items()})

    @property
    def system_prompt(self) -> str:
        return self.train[0].messages[0]["content"]

    def splits(self) -> dict[str, list[ChatExample]]:
        return {"train": self.train, "val": self.val, "test": self.test, "paraphrases": self.paraphrases}

    def to_frame(self) -> pd.DataFrame:
        """One row per example, with word counts, for plots and summaries."""
        return pd.DataFrame(
            {
                "split": split,
                "id": ex.id,
                "lang": ex.lang,
                "category": ex.category,
                "question": ex.question,
                "answer": ex.answer,
                "question_words": len(ex.question.split()),
                "answer_words": len(ex.answer.split()),
            }
            for split, examples in self.splits().items()
            for ex in examples
        )

    def summary(self) -> pd.DataFrame:
        """Example counts per split and language."""
        table = self.to_frame().pivot_table(index="split", columns="lang", values="id", aggfunc="count", fill_value=0)
        table = table.reindex(list(SPLIT_FILES))
        table["total"] = table.sum(axis=1)
        return table


def _read_examples(path: Path) -> list[ChatExample]:
    with path.open(encoding="utf-8") as handle:
        return [ChatExample.from_dict(json.loads(line)) for line in handle if line.strip()]
