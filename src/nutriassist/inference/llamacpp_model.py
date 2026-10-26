"""CPU backend: a GGUF model run with llama.cpp. Works on ordinary laptops without a GPU.

Requires the ``serve`` extra (llama-cpp-python). The notebook exports the fine-tuned
model as ``nutriassist-rw-q4_k_m.gguf`` and ``nutriassist-rw-q8_0.gguf``; the chat template is stored inside the file.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

from ..prompts import Message
from .base import ChatModel, GenerationSettings


class LlamaCppChatModel(ChatModel):
    """Greedy generation with llama.cpp. Conversations are answered one after another."""

    def __init__(self, llama, settings: GenerationSettings | None = None, name: str = "llama.cpp") -> None:
        super().__init__(settings)
        self.llama = llama
        self.name = name

    @classmethod
    def from_file(cls, path: str | Path, context_tokens: int = 2048, threads: int | None = None,
                  settings: GenerationSettings | None = None) -> "LlamaCppChatModel":
        from llama_cpp import Llama  # imported here so the rest of the package works without it

        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Model file not found: {path}")
        llama = Llama(model_path=str(path), n_ctx=context_tokens, n_threads=threads or os.cpu_count(),
                      seed=0, verbose=False)
        return cls(llama, settings, name=path.name)

    def generate_batch(self, conversations: Sequence[Sequence[Message]]) -> list[str]:
        replies = []
        for conversation in conversations:
            # llama.cpp reuses the previous prompt's cache when prompts share a prefix (they all share the
            # system prompt), which makes the answer depend on the previous question. Start clean each time.
            self.llama.reset()
            result = self.llama.create_chat_completion(
                messages=list(conversation),
                max_tokens=self.settings.max_new_tokens,
                temperature=0.0,                    # greedy, as in evaluation
                repeat_penalty=self.settings.repetition_penalty,
            )
            replies.append(result["choices"][0]["message"]["content"].strip())
        return replies
