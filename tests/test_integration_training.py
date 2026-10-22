"""End-to-end check of the training and inference code with a tiny random Qwen2 model on the CPU.

It runs the same code paths as the Colab notebook (tokenisation with the real Qwen
chat template, LoRA training with the Hugging Face Trainer, saving and reloading
the adapter, batched generation, perplexity, evaluation, the experiment runner),
just without 4-bit quantisation, which needs a GPU. Skipped when torch or
transformers are not installed or the Qwen tokenizer cannot be downloaded.
"""

import math

import pytest

torch = pytest.importorskip("torch")
transformers = pytest.importorskip("transformers")
pytest.importorskip("peft")

from conftest import make_example  # noqa: E402
from nutriassist.evaluation import Evaluator  # noqa: E402
from nutriassist.inference.base import GenerationSettings  # noqa: E402
from nutriassist.inference.transformers_model import TransformersChatModel  # noqa: E402
from nutriassist.training.config import TRAINING_SUMMARY_FILE, TrainingConfig  # noqa: E402
from nutriassist.training.dataset import QADataset  # noqa: E402
from nutriassist.training.experiments import ExperimentRunner  # noqa: E402
from nutriassist.training.finetune import QLoRAFineTuner  # noqa: E402

pytestmark = pytest.mark.integration
FAST = GenerationSettings(max_new_tokens=6, batch_size=2)


@pytest.fixture(scope="module")
def tiny_model_dir(tmp_path_factory):
    try:
        tokenizer = transformers.AutoTokenizer.from_pretrained("Qwen/Qwen2.5-1.5B-Instruct")
    except OSError as error:
        pytest.skip(f"Qwen tokenizer not available: {error}")
    config = transformers.Qwen2Config(vocab_size=len(tokenizer), hidden_size=32, intermediate_size=64,
                                      num_hidden_layers=2, num_attention_heads=4, num_key_value_heads=2,
                                      max_position_embeddings=1024, tie_word_embeddings=True)
    torch.manual_seed(0)
    path = tmp_path_factory.mktemp("tiny-qwen2")
    transformers.Qwen2ForCausalLM(config).save_pretrained(path)
    tokenizer.save_pretrained(path)
    return str(path)


@pytest.fixture(scope="module")
def tiny_dataset():
    train = [make_example(f"Question {i}?", f"Answer number {i}.", id=f"t-{i}") for i in range(8)]
    val = [make_example("What is safe?", "Go to the health centre.", category="safety_redirect", id="v-1"),
           make_example("Yarya iki?", "Muhe igikoma.", lang="rw", id="v-2")]
    return QADataset(train=train, val=val, test=val)


def tiny_config(model_dir, name="tiny", **changes):
    settings = dict(name=name, base_model=model_dir, epochs=1, batch_size=2, grad_accum=2,
                    learning_rate=1e-3, lora_rank=4, max_length=256)
    return TrainingConfig(**{**settings, **changes})


def test_train_save_reload_and_generate(tiny_model_dir, tiny_dataset, tmp_path):
    tuner = QLoRAFineTuner(tiny_config(tiny_model_dir), tmp_path / "adapters", tmp_path / "ckpt", require_gpu=False)
    model, run = tuner.train(tiny_dataset)

    assert (run.adapter_dir / "adapter_config.json").exists()
    assert (run.adapter_dir / "log_history.json").exists()
    assert math.isfinite(run.train_loss) and math.isfinite(run.val_loss)
    assert 0 < run.trainable_params < run.total_params
    assert run.summary()["lora_alpha"] == 8

    model.settings = FAST
    replies = model.generate_batch([ex.prompt_messages for ex in tiny_dataset.val])
    assert len(replies) == 2 and all(isinstance(r, str) for r in replies)

    reloaded = TransformersChatModel.from_pretrained(tiny_model_dir, run.adapter_dir, settings=FAST)
    assert "tiny" in reloaded.name
    assert reloaded.perplexity(tiny_dataset.val) > 1


def test_evaluator_reports_perplexity_for_transformers_models(tiny_model_dir, tiny_dataset):
    model = TransformersChatModel.from_pretrained(tiny_model_dir, settings=FAST)
    result = Evaluator().evaluate(model, tiny_dataset.val)
    assert result.scores["all"]["perplexity"] > 1
    assert set(result.scores) == {"all", "en", "rw"}


def test_generation_is_deterministic_and_order_preserving(tiny_model_dir, tiny_dataset):
    model = TransformersChatModel.from_pretrained(tiny_model_dir, settings=FAST)
    prompts = [ex.prompt_messages for ex in tiny_dataset.train[:5]]
    batched = model.generate_batch(prompts)
    one_by_one = [model.generate(p) for p in prompts]
    assert batched == one_by_one


def test_experiment_runner_with_real_fine_tuner(tiny_model_dir, tiny_dataset, tmp_path):
    runner = ExperimentRunner(
        tiny_dataset, tmp_path,
        fine_tuner_factory=lambda c: QLoRAFineTuner(c, tmp_path / "adapters", tmp_path / "ckpt", require_gpu=False),
    )
    results = runner.run([tiny_config(tiny_model_dir, "run_a")])
    row = results.iloc[0]
    assert row["experiment"] == "run_a" and row["gpu"] == "cpu"
    assert {"val_ROUGE-L", "val_perplexity", "train_minutes", "peak_gpu_reserved_GB"} <= set(results.columns)


class Disconnect(transformers.TrainerCallback):
    """Stops training like a lost Colab session, right after a given step."""

    def __init__(self, after_step):
        self.after_step = after_step

    def on_step_end(self, args, state, control, **kwargs):
        if state.global_step == self.after_step:
            raise ConnectionError("Colab disconnected")


def test_training_resumes_from_the_last_checkpoint(tiny_model_dir, tiny_dataset, tmp_path):
    # 8 examples, batch 2: 4 steps per epoch, 2 epochs = 8 steps; checkpoints every 2 steps.
    config = tiny_config(tiny_model_dir, "resume", epochs=2, grad_accum=1, save_steps=2)
    folders = (tmp_path / "adapters", tmp_path / "ckpt")

    first = QLoRAFineTuner(config, *folders, require_gpu=False, callbacks=(Disconnect(after_step=5),))
    with pytest.raises(ConnectionError):
        first.train(tiny_dataset)
    assert first.last_checkpoint().endswith("checkpoint-4")
    assert not (tmp_path / "adapters" / "resume" / TRAINING_SUMMARY_FILE).exists()

    second = QLoRAFineTuner(config, *folders, require_gpu=False)
    _, run = second.train(tiny_dataset)
    assert max(h["step"] for h in run.log_history) == 8
    assert run.sessions == 2
    assert run.train_minutes > 0
    assert (run.adapter_dir / TRAINING_SUMMARY_FILE).exists()
    assert not (tmp_path / "ckpt" / "resume").exists()       # checkpoints removed after success
