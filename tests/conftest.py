from pathlib import Path

import pytest

from nutriassist.prompts import build_messages
from nutriassist.training.dataset import ChatExample, QADataset

PROCESSED_QA = Path("data/QA_data/processed")


class CharTokenizer:
    """A tiny tokenizer stand-in: one token per character, with a simple chat template."""

    eos_token_id = 0
    pad_token_id = 0

    def __init__(self, supports_system_role: bool = True) -> None:
        self.supports_system_role = supports_system_role

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=False):
        if not self.supports_system_role and any(m["role"] == "system" for m in messages):
            raise ValueError("System role not supported")
        text = "".join(f"<{m['role']}>{m['content']}" for m in messages)
        return text + ("<assistant>" if add_generation_prompt else "")

    def __call__(self, text, add_special_tokens=True):
        return {"input_ids": [ord(c) for c in text]}


@pytest.fixture
def char_tokenizer():
    return CharTokenizer()


def make_example(question="How much?", answer="Two spoons.", lang="en", category="feeding_by_age", id="x-1"):
    return ChatExample(tuple(build_messages(question, answer)), id=id, lang=lang, category=category)


@pytest.fixture(scope="session")
def qa_dataset() -> QADataset:
    return QADataset.load(PROCESSED_QA)
