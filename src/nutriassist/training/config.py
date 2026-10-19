"""Hyperparameters for one QLoRA fine-tuning run."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace

DEFAULT_BASE_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"


@dataclass(frozen=True)
class TrainingConfig:
    name: str = "baseline"
    base_model: str = DEFAULT_BASE_MODEL
    learning_rate: float = 2e-4
    lora_rank: int = 16
    lora_alpha_ratio: float = 2.0      # lora_alpha = ratio * rank keeps the update scale fixed across ranks
    lora_dropout: float = 0.05
    epochs: int = 3
    batch_size: int = 4
    grad_accum: int = 4
    warmup_ratio: float = 0.05
    max_length: int = 768
    seed: int = 42

    def __post_init__(self) -> None:
        if self.learning_rate <= 0 or self.lora_rank <= 0 or self.epochs <= 0:
            raise ValueError(f"learning_rate, lora_rank and epochs must be positive in {self.name}")
        if not 0 <= self.lora_dropout < 1 or not 0 <= self.warmup_ratio < 1:
            raise ValueError(f"lora_dropout and warmup_ratio must be in [0, 1) in {self.name}")

    @property
    def lora_alpha(self) -> int:
        return int(self.lora_alpha_ratio * self.lora_rank)

    @property
    def effective_batch_size(self) -> int:
        return self.batch_size * self.grad_accum

    def total_steps(self, num_examples: int) -> int:
        steps_per_epoch = -(-num_examples // self.effective_batch_size)  # ceiling division
        return steps_per_epoch * self.epochs

    def warmup_steps(self, num_examples: int) -> int:
        return max(1, round(self.warmup_ratio * self.total_steps(num_examples)))

    def variant(self, name: str, **changes) -> "TrainingConfig":
        """A copy with some settings changed, e.g. ``base.variant("lr_1e-4", learning_rate=1e-4)``."""
        return replace(self, name=name, **changes)

    def to_dict(self) -> dict:
        return {**asdict(self), "lora_alpha": self.lora_alpha, "effective_batch_size": self.effective_batch_size}
