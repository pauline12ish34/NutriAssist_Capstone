"""Kinyarwanda <-> English machine translation, for Kinyarwanda questions with no reviewed answer.

The fine-tuned model answers well in English but poorly in Kinyarwanda, so an unmatched Kinyarwanda
question is translated to English, answered in English, and the answer translated back. NLLB-200
(distilled, 600M parameters) covers Kinyarwanda (``kin_Latn``) and runs on a CPU. Answers are
translated sentence by sentence: NLLB was trained on single sentences and drops content from long
inputs. The app labels these answers as machine-translated.

NLLB gets local food words badly wrong (*ikivuguto* became "spanking", "fermented milk" became *ubuki*,
honey), so :class:`TermAwareTranslator` first writes every known food, nutrient and health term in the
target language (``nutriassist.terms``). A glossary then fixes the mistakes that remain.
"""

from __future__ import annotations

import re
from typing import Protocol, Sequence

from .terms import Terminology

NLLB_MODEL = "facebook/nllb-200-distilled-600M"
NLLB_CODES = {"en": "eng_Latn", "rw": "kin_Latn"}

# NLLB's general-purpose Kinyarwanda gets some nutrition terms wrong, always in the same way. Each
# wrong rendering is replaced by the term used in the reviewed answers. Add to this list as reviewers
# find more (wrong rendering -> correct term).
KINYARWANDA_GLOSSARY = {
    "icyuma": "ubutare",                 # "iron" the nutrient, rendered as iron the metal
    "amata y'umubyeyi": "amashereka",    # "breast milk"
    "amata y'ibere": "amashereka",
    # "breast milk" rendered with ubuki (honey), which is dangerous for babies under 12 months.
    "ubuki bw'umubyeyi": "amashereka",
    "ubuki bwa mama": "amashereka",
    "ubuki bw'amabere": "amashereka",
    "ubuki bw'ibere": "amashereka",
}

# Qwen sometimes slips a Chinese word into an English answer ("colds (感冒)"); NLLB would copy it.
_FOREIGN_SCRIPT = re.compile(r"\s*\(?[\u3000-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af\uff00-\uffef]+\)?")

# A sentence ends at . ! or ? followed by a space; a line break also separates sentences.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")


class Translator(Protocol):
    name: str

    def translate(self, texts: Sequence[str], source: str, target: str) -> list[str]:
        """Translate each text from ``source`` to ``target`` ("en" or "rw")."""


def split_sentences(text: str) -> list[str]:
    return [sentence for sentence in (s.strip() for s in _SENTENCE_END.split(text)) if sentence]


def apply_glossary(text: str, glossary: dict[str, str] = KINYARWANDA_GLOSSARY) -> str:
    """Replace known mistranslations (whole words only, keeping a leading capital)."""
    for wrong, right in glossary.items():
        pattern = re.compile(rf"(?<![\w']){re.escape(wrong)}(?!\w)", re.IGNORECASE)
        text = pattern.sub(lambda m: right[0].upper() + right[1:] if m.group(0)[0].isupper() else right, text)
    return text


def strip_foreign_script(text: str) -> str:
    """Remove Chinese, Japanese and Korean characters (and brackets around them)."""
    return _FOREIGN_SCRIPT.sub("", text)


def translate_text(translator: Translator, text: str, source: str, target: str) -> str:
    """Translate a multi-sentence text one sentence at a time (in one batch) and rejoin it."""
    sentences = split_sentences(strip_foreign_script(text))
    if not sentences:
        return ""
    translated = " ".join(translator.translate(sentences, source, target))
    return apply_glossary(translated) if target == "rw" else translated


class NllbTranslator:
    """NLLB-200 through Hugging Face Transformers (needs ``torch``, ``transformers`` and ``sentencepiece``)."""

    def __init__(self, model_name: str = NLLB_MODEL, device: str = "cpu", max_new_tokens: int = 256,
                 batch_size: int = 8) -> None:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name).to(device).eval()
        self.device = device
        self.max_new_tokens = max_new_tokens
        self.batch_size = batch_size
        self.name = model_name.split("/")[-1]

    def translate(self, texts: Sequence[str], source: str, target: str) -> list[str]:
        self.tokenizer.src_lang = NLLB_CODES[source]
        target_id = self.tokenizer.convert_tokens_to_ids(NLLB_CODES[target])
        results: list[str] = []
        with self.torch.no_grad():
            for start in range(0, len(texts), self.batch_size):
                batch = self.tokenizer(list(texts[start:start + self.batch_size]), return_tensors="pt",
                                       padding=True, truncation=True, max_length=256).to(self.device)
                output = self.model.generate(**batch, forced_bos_token_id=target_id, num_beams=4,
                                             max_new_tokens=self.max_new_tokens, max_length=None)
                results.extend(self.tokenizer.batch_decode(output, skip_special_tokens=True))
        return results


class TermAwareTranslator:
    """Wraps a translator: known terms are written in the target language before translating."""

    def __init__(self, translator: Translator, terminology: Terminology | None = None) -> None:
        self.translator = translator
        self.terminology = terminology or Terminology.load()
        self.name = translator.name

    def translate(self, texts: Sequence[str], source: str, target: str) -> list[str]:
        prepared = [self.terminology.prepare(text, source, target) for text in texts]
        return self.translator.translate(prepared, source, target)
