import pytest

from conftest import CharTokenizer, make_example
from nutriassist.prompts import SYSTEM_PROMPT
from nutriassist.training.config import TrainingConfig
from nutriassist.training.dataset import ChatExample, QADataset
from nutriassist.training.encoding import IGNORE_INDEX, ChatEncoder


class TestQADataset:
    def test_loads_all_splits_with_metadata(self, qa_dataset):
        assert {name: len(rows) for name, rows in qa_dataset.splits().items()} == {
            "train": 626, "val": 49, "test": 78, "paraphrases": 61}
        assert all(ex.lang in {"en", "rw"} and ex.category and ex.id for ex in qa_dataset.test)

    def test_uses_the_shared_system_prompt(self, qa_dataset):
        assert qa_dataset.system_prompt == SYSTEM_PROMPT

    def test_summary_counts_per_language(self, qa_dataset):
        summary = qa_dataset.summary()
        assert summary.loc["test", "total"] == 78
        assert summary.loc["test", "en"] + summary.loc["test", "rw"] == 78

    def test_missing_files_are_reported(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="train.jsonl"):
            QADataset.load(tmp_path)

    def test_rejects_rows_with_wrong_roles(self):
        with pytest.raises(ValueError, match="system/user/assistant"):
            ChatExample.from_dict({"messages": [{"role": "user", "content": "hi"}]})


class TestChatEncoder:
    def test_only_answer_tokens_are_trained(self, char_tokenizer):
        example = make_example(answer="Ok")
        encoded = ChatEncoder(char_tokenizer).encode(example)
        prompt = char_tokenizer.apply_chat_template(example.prompt_messages, add_generation_prompt=True)

        assert encoded["input_ids"] == [ord(c) for c in prompt + "Ok"] + [CharTokenizer.eos_token_id]
        assert encoded["labels"] == [IGNORE_INDEX] * len(prompt) + [ord("O"), ord("k"), CharTokenizer.eos_token_id]
        assert encoded["attention_mask"] == [1] * len(encoded["input_ids"])

    def test_long_examples_are_truncated_and_counted(self, char_tokenizer):
        prompt_tokens = len(ChatEncoder(char_tokenizer).encode(make_example(answer=""))["input_ids"]) - 1
        limit = prompt_tokens + 20
        encoder = ChatEncoder(char_tokenizer, max_length=limit)
        encoded, stats = encoder.encode_many([make_example(answer="x" * 500), make_example(answer="short")])
        assert len(encoded[0]["input_ids"]) == len(encoded[0]["labels"]) == limit
        assert stats.truncated == 1 and stats.max_tokens == limit

    def test_templates_without_system_role_get_it_in_the_user_turn(self):
        encoder = ChatEncoder(CharTokenizer(supports_system_role=False))
        prompt = encoder.render_prompt(make_example(question="Q?").prompt_messages)
        assert prompt.startswith(f"<user>{SYSTEM_PROMPT}\n\nQ?")
        assert "<system>" not in prompt


class TestTrainingConfig:
    def test_derived_values(self):
        config = TrainingConfig(lora_rank=8, batch_size=4, grad_accum=4, epochs=3, warmup_ratio=0.1)
        assert config.lora_alpha == 16
        assert config.effective_batch_size == 16
        assert config.total_steps(626) == 40 * 3   # ceil(626 / 16) = 40 steps per epoch
        assert config.warmup_steps(626) == 12

    def test_variant_changes_only_named_settings(self):
        base = TrainingConfig()
        variant = base.variant("lr_1e-4", learning_rate=1e-4)
        assert (variant.name, variant.learning_rate, variant.lora_rank) == ("lr_1e-4", 1e-4, base.lora_rank)

    @pytest.mark.parametrize("changes", [{"learning_rate": 0}, {"lora_rank": -1}, {"lora_dropout": 1.0}])
    def test_rejects_invalid_settings(self, changes):
        with pytest.raises(ValueError):
            TrainingConfig(**changes)
