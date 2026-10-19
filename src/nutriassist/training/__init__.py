"""Data loading, tokenisation and QLoRA fine-tuning.

``finetune`` needs torch and a GPU, so it is not imported here; import it explicitly.
"""

from .config import DEFAULT_BASE_MODEL, TrainingConfig
from .dataset import ChatExample, QADataset
from .encoding import ChatEncoder

__all__ = ["DEFAULT_BASE_MODEL", "ChatEncoder", "ChatExample", "QADataset", "TrainingConfig"]
