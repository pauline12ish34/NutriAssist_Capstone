"""QLoRA fine-tuning: a frozen 4-bit base model plus small trainable LoRA adapters.

Training saves a checkpoint every ``save_steps`` steps and resumes from the latest one, so a Colab
disconnect loses at most a few minutes. Training time and peak GPU memory are added up across
sessions. Requires a CUDA GPU and the ``train`` extra (torch, transformers, peft, bitsandbytes).
"""

from __future__ import annotations

import gc
import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

import torch
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import DataCollatorForSeq2Seq, Trainer, TrainerCallback, TrainingArguments, set_seed
from transformers.trainer_utils import get_last_checkpoint

from ..inference.transformers_model import TransformersChatModel, compute_dtype, load_causal_lm, load_tokenizer
from .config import TRAINING_SUMMARY_FILE, TrainingConfig
from .dataset import QADataset
from .encoding import IGNORE_INDEX, ChatEncoder

GIB = 1024**3
PROGRESS_FILE = "progress.json"   # in the checkpoint folder: time and memory used so far


@dataclass
class TrainingRun:
    """What one training run cost and how its loss evolved."""

    config: TrainingConfig
    adapter_dir: Path
    train_minutes: float
    peak_gpu_allocated_gb: float
    peak_gpu_reserved_gb: float
    train_loss: float
    val_loss: float
    trainable_params: int
    total_params: int
    gpu_name: str
    log_history: list[dict] = field(default_factory=list)
    sessions: int = 1                      # Colab sessions the training was spread over

    def summary(self) -> dict:
        return {
            "experiment": self.config.name,
            "base_model": self.config.base_model,
            "learning_rate": self.config.learning_rate,
            "lora_rank": self.config.lora_rank,
            "lora_alpha": self.config.lora_alpha,
            "epochs": self.config.epochs,
            "effective_batch_size": self.config.effective_batch_size,
            "trainable_params_M": round(self.trainable_params / 1e6, 2),
            "trainable_%": round(100 * self.trainable_params / self.total_params, 3),
            "train_minutes": round(self.train_minutes, 1),
            "peak_gpu_allocated_GB": round(self.peak_gpu_allocated_gb, 2),
            "peak_gpu_reserved_GB": round(self.peak_gpu_reserved_gb, 2),
            "train_loss": round(self.train_loss, 4),
            "val_loss": round(self.val_loss, 4),
            "gpu": self.gpu_name,
            "sessions": self.sessions,
        }


class _ProgressCallback(TrainerCallback):
    """Saves the time and peak GPU memory used so far next to every checkpoint."""

    def __init__(self, path: Path, previous: dict, on_gpu: bool) -> None:
        self.path = path
        self.previous = previous
        self.on_gpu = on_gpu
        self.start = time.perf_counter()

    def totals(self) -> dict:
        allocated = torch.cuda.max_memory_allocated() / GIB if self.on_gpu else 0.0
        reserved = torch.cuda.max_memory_reserved() / GIB if self.on_gpu else 0.0
        return {
            "seconds": self.previous.get("seconds", 0.0) + time.perf_counter() - self.start,
            "peak_allocated_gb": max(self.previous.get("peak_allocated_gb", 0.0), allocated),
            "peak_reserved_gb": max(self.previous.get("peak_reserved_gb", 0.0), reserved),
            "sessions": self.previous.get("sessions", 0) + 1,
        }

    def on_save(self, args, state, control, **kwargs):
        self.path.write_text(json.dumps(self.totals()))


def free_gpu_memory() -> None:
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


class QLoRAFineTuner:
    """Trains LoRA adapters on every linear layer of a 4-bit (NF4) base model."""

    def __init__(self, config: TrainingConfig, adapters_dir: str | Path, checkpoints_dir: str | Path,
                 require_gpu: bool = True, callbacks: tuple[TrainerCallback, ...] = ()) -> None:
        # require_gpu=False lets the integration test train a tiny model on a CPU (no 4-bit quantisation there).
        self.on_gpu = torch.cuda.is_available()
        if require_gpu and not self.on_gpu:
            raise RuntimeError("QLoRA training needs a CUDA GPU. In Colab: Runtime > Change runtime type > T4 GPU.")
        self.config = config
        self.adapter_dir = Path(adapters_dir) / config.name
        self.checkpoint_dir = Path(checkpoints_dir) / config.name
        self.callbacks = callbacks

    def train(self, dataset: QADataset) -> tuple[TransformersChatModel, TrainingRun]:
        cfg = self.config
        set_seed(cfg.seed)
        tokenizer = load_tokenizer(cfg.base_model)
        tokenizer.padding_side = "right"
        encoder = ChatEncoder(tokenizer, cfg.max_length)
        train_data, train_stats = encoder.encode_many(dataset.train)
        val_data, _ = encoder.encode_many(dataset.val)
        print(f"[{cfg.name}] train: {train_stats}")

        free_gpu_memory()
        if self.on_gpu:
            torch.cuda.reset_peak_memory_stats()
        model = self._build_model()
        trainable, total = model.get_nb_trainable_parameters()

        resume_from = self.last_checkpoint()
        progress_path = self.checkpoint_dir / PROGRESS_FILE
        previous = json.loads(progress_path.read_text()) if resume_from and progress_path.exists() else {}
        if resume_from:
            print(f"[{cfg.name}] resuming from {Path(resume_from).name}")
        progress = _ProgressCallback(progress_path, previous, self.on_gpu)

        trainer = Trainer(
            model=model,
            args=self._training_arguments(len(train_data)),
            train_dataset=train_data,
            eval_dataset=val_data,
            data_collator=DataCollatorForSeq2Seq(tokenizer, padding=True, label_pad_token_id=IGNORE_INDEX),
            callbacks=[progress, *self.callbacks],
        )
        trainer.train(resume_from_checkpoint=resume_from)
        totals = progress.totals()

        self.adapter_dir.mkdir(parents=True, exist_ok=True)
        model.save_pretrained(self.adapter_dir)
        tokenizer.save_pretrained(self.adapter_dir)
        history = trainer.state.log_history
        (self.adapter_dir / "log_history.json").write_text(json.dumps(history, indent=2))
        (self.adapter_dir / "training_config.json").write_text(json.dumps(cfg.to_dict(), indent=2))

        # Losses logged every few steps, else (a very short run) the trainer's final average.
        train_losses = [h["loss"] for h in history if "loss" in h] or [h["train_loss"] for h in history if "train_loss" in h][-1:]
        run = TrainingRun(
            config=cfg,
            adapter_dir=self.adapter_dir,
            train_minutes=totals["seconds"] / 60,
            peak_gpu_allocated_gb=totals["peak_allocated_gb"],
            peak_gpu_reserved_gb=totals["peak_reserved_gb"],
            # Mean of the logged losses: unlike Trainer's training_loss it also covers resumed sessions.
            train_loss=sum(train_losses) / len(train_losses) if train_losses else float("nan"),
            val_loss=[h["eval_loss"] for h in history if "eval_loss" in h][-1],
            trainable_params=trainable,
            total_params=total,
            gpu_name=torch.cuda.get_device_name(0) if self.on_gpu else "cpu",
            log_history=history,
            sessions=totals["sessions"],
        )
        # Written last: its presence means the adapter is complete and never needs training again.
        (self.adapter_dir / TRAINING_SUMMARY_FILE).write_text(json.dumps(run.summary(), indent=2))
        shutil.rmtree(self.checkpoint_dir, ignore_errors=True)
        return TransformersChatModel(model, tokenizer, name=f"{cfg.base_model} + {cfg.name}"), run

    def last_checkpoint(self) -> str | None:
        return get_last_checkpoint(str(self.checkpoint_dir)) if self.checkpoint_dir.is_dir() else None

    def _build_model(self):
        cfg = self.config
        model = load_causal_lm(cfg.base_model, quantize_4bit=True)
        # Casts norms to float32 and enables input gradients so checkpointing works on a 4-bit model.
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
        lora = LoraConfig(
            r=cfg.lora_rank,
            lora_alpha=cfg.lora_alpha,
            lora_dropout=cfg.lora_dropout,
            target_modules="all-linear",   # attention (q, k, v, o) and MLP (gate, up, down) projections
            task_type="CAUSAL_LM",
        )
        model = get_peft_model(model, lora)
        model.config.use_cache = False  # the KV cache is useless during training and conflicts with checkpointing
        return model

    def _training_arguments(self, num_examples: int) -> TrainingArguments:
        cfg = self.config
        dtype = compute_dtype() if self.on_gpu else torch.float32
        return TrainingArguments(
            output_dir=str(self.checkpoint_dir),
            per_device_train_batch_size=cfg.batch_size,
            per_device_eval_batch_size=cfg.batch_size,
            gradient_accumulation_steps=cfg.grad_accum,
            learning_rate=cfg.learning_rate,
            num_train_epochs=cfg.epochs,
            lr_scheduler_type="cosine",
            warmup_steps=cfg.warmup_steps(num_examples),
            optim="paged_adamw_8bit" if self.on_gpu else "adamw_torch",  # 8-bit states save GPU memory
            fp16=dtype == torch.float16,
            bf16=dtype == torch.bfloat16,
            gradient_checkpointing=True,
            gradient_checkpointing_kwargs={"use_reentrant": False},
            logging_steps=5,
            eval_strategy="epoch",
            save_strategy="steps",
            save_steps=cfg.save_steps,
            save_total_limit=1,             # only the latest checkpoint is kept (about 120 MB on Drive)
            report_to="none",
            seed=cfg.seed,
        )
