"""Describe a transformer's architecture from its Hugging Face config, for the notebook and report."""

from __future__ import annotations

from typing import Any, Iterable

# (config attribute, label) pairs, in the order a reader follows a decoder-only transformer.
_CONFIG_FIELDS = (
    ("model_type", "Model family"),
    ("num_hidden_layers", "Decoder layers (transformer blocks)"),
    ("hidden_size", "Hidden size (width of each token vector)"),
    ("num_attention_heads", "Attention heads (queries)"),
    ("num_key_value_heads", "Key/value heads (grouped-query attention)"),
    ("intermediate_size", "MLP inner size"),
    ("hidden_act", "MLP activation function"),
    ("rms_norm_eps", "RMSNorm epsilon (normalisation before attention and MLP)"),
    ("rope_theta", "RoPE base (rotary position encoding)"),
    ("max_position_embeddings", "Maximum context length (tokens)"),
    ("vocab_size", "Vocabulary size (tokens)"),
    ("tie_word_embeddings", "Input and output embeddings shared"),
)


def architecture_summary(config: Any) -> dict[str, Any]:
    """Readable architecture facts. Attributes a model family does not have are skipped."""
    summary = {label: getattr(config, attr) for attr, label in _CONFIG_FIELDS if getattr(config, attr, None) is not None}
    heads = getattr(config, "num_attention_heads", None)
    if heads and getattr(config, "hidden_size", None):
        summary["Head dimension"] = config.hidden_size // heads
    return summary


def lora_target_modules(module_names: Iterable[str]) -> list[str]:
    """Distinct layer types that received LoRA adapters, e.g. ``['down_proj', 'q_proj', ...]``.

    ``module_names`` is ``(name for name, _ in model.named_modules())`` of a PEFT model.
    """
    targets = {name.rsplit(".lora_A", 1)[0].rsplit(".", 1)[-1] for name in module_names if name.endswith(".lora_A")}
    return sorted(targets)
