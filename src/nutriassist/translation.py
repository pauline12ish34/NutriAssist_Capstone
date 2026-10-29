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
import time
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
    """Translate a multi-sentence text one sentence at a time (in one batch) and rejoin it.

    A translator with ``whole_text`` (Gemini) gets the text in one piece instead.
    """
    text = strip_foreign_script(text).strip()
    if getattr(translator, "whole_text", False):
        translated = translator.translate([text], source, target)[0] if text else ""
        return apply_glossary(translated) if target == "rw" else translated
    sentences = split_sentences(text)
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


GEMINI_MODEL = "gemini-3.5-flash"
GEMINI_TIMEOUT_MS = 20_000
# Tried in turn when the main model is busy. gemini-3.1-flash-lite was left out: it invented words.
GEMINI_FALLBACK_MODELS = ("gemini-3.6-flash", "gemini-3.5-flash-lite")
GEMINI_RETRIES = 4
LANGUAGE_NAMES = {"en": "English", "rw": "Kinyarwanda"}


class GeminiTranslator:
    """Google Gemini through the ``google-genai`` package (key in ``.env``, as for ``gemini_drafts``).

    Gemini writes much better Kinyarwanda than NLLB and knows the local food words, but it needs the
    internet and sends the question and answer to Google. Each text is translated whole (``whole_text``),
    so lists keep their layout, with the project's glossary of food and health terms in the prompt.
    """

    whole_text = True

    def __init__(self, model: str = GEMINI_MODEL, api_key: str | None = None) -> None:
        from google import genai

        from .qa_data.gemini_drafts import _glossary, api_key as read_api_key

        self.client = genai.Client(api_key=api_key or read_api_key(),
                                   http_options=genai.types.HttpOptions(timeout=GEMINI_TIMEOUT_MS))
        self.model = model
        self.glossary = _glossary()
        self.name = model
        self._no_thinking_setting: set[str] = set()

    def prompt(self, text: str, source: str, target: str) -> str:
        return f"""Translate this text from {LANGUAGE_NAMES[source]} to {LANGUAGE_NAMES[target]}.
It is from a child-nutrition assistant for parents and caregivers in Rwanda. Write natural, everyday
{LANGUAGE_NAMES[target]}{" as spoken in Rwanda (not Kirundi)" if target == "rw" else ""}. Keep every fact,
number, age and unit exactly, and keep the line breaks and list markers. Add nothing and leave nothing out.
Reply with the translation only.

Use these terms (English = Kinyarwanda):
{self.glossary}
- breast milk = amashereka
- to mash or grind food = gusya (never gusekura)

Text:
{text}"""

    def translate(self, texts: Sequence[str], source: str, target: str) -> list[str]:
        return [self._generate(self.prompt(text, source, target)) for text in texts]

    def _generate(self, prompt: str) -> str:
        import httpx
        from google.genai import errors, types

        # Translation needs no reasoning, and "thinking" added 10-30 s per request.
        fast = types.GenerateContentConfig(temperature=0.2, thinking_config=types.ThinkingConfig(thinking_level="minimal"))
        plain = types.GenerateContentConfig(temperature=0.2)
        models = [self.model, *(m for m in GEMINI_FALLBACK_MODELS if m != self.model)]
        for attempt in range(GEMINI_RETRIES):
            # One model is often busy while another is not, so each retry tries the next.
            model = models[attempt % len(models)]
            config = fast if model not in self._no_thinking_setting else plain
            try:
                return self.client.models.generate_content(model=model, contents=prompt, config=config).text.strip()
            except (errors.APIError, httpx.TransportError) as error:
                code = getattr(error, "code", None)
                if code == 400 and config is fast:   # this model does not take the thinking setting
                    self._no_thinking_setting.add(model)
                    return self.client.models.generate_content(model=model, contents=prompt, config=plain).text.strip()
                # 429 (rate limit) and 5xx (busy) usually pass within seconds; a caller is waiting.
                if (code is not None and code != 429 and code < 500) or attempt == GEMINI_RETRIES - 1:
                    raise
                time.sleep(attempt)
        raise AssertionError("unreachable")


class TermAwareTranslator:
    """Wraps a translator: known terms are written in the target language before translating."""

    def __init__(self, translator: Translator, terminology: Terminology | None = None) -> None:
        self.translator = translator
        self.terminology = terminology or Terminology.load()
        self.name = translator.name

    def translate(self, texts: Sequence[str], source: str, target: str) -> list[str]:
        prepared = [self.terminology.prepare(text, source, target) for text in texts]
        return self.translator.translate(prepared, source, target)
