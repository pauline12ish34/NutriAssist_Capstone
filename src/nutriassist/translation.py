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

import json
import logging
import os
import re
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Protocol, Sequence

from .terms import Terminology

log = logging.getLogger(__name__)

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
    # "groundnut paste" rendered by Gemini as a word that does not exist.
    "ikimonyo cy'ubunyobwa": "ubunyobwa biseye",
    "ikimonyo cy'ibishyimbo": "ubunyobwa biseye",
}

# Qwen sometimes slips a Chinese word into an English answer ("colds (感冒)"); NLLB would copy it.
_FOREIGN_SCRIPT = re.compile(r"\s*\(?[\u3000-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af\uff00-\uffef]+\)?")

# A sentence ends at . ! or ? followed by a space; a line break also separates sentences.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")


class Translator(Protocol):
    name: str

    def translate(self, texts: Sequence[str], source: str, target: str) -> list[str]:
        """Translate each text from ``source`` to ``target`` ("en" or "rw")."""


class CachingTranslator:
    """Remembers recent translations, so a repeated question costs no new Gemini or Claude call.

    The model writes the same English answer to the same question (it does not sample), so a repeated
    Kinyarwanda question reuses both translations: the question into English and the answer back. Only
    the translation is reused. The answer is still the model's, and the app still labels it as written by
    AI and machine-translated. Failed translations are not stored. The cache lives in memory only: nothing
    is written to disk, and it empties when the server restarts.
    """

    def __init__(self, translator: Translator, max_entries: int = 2000) -> None:
        self.translator = translator
        self.name = translator.name
        self.whole_text = getattr(translator, "whole_text", False)
        self.max_entries = max_entries
        self.hits = self.misses = 0
        self._cache: OrderedDict[tuple[str, str, str], str] = OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def _key(text: str, source: str, target: str) -> tuple[str, str, str]:
        return source, target, " ".join(text.split())   # extra spaces and line breaks do not make a new entry

    def translate(self, texts: Sequence[str], source: str, target: str) -> list[str]:
        keys = [self._key(text, source, target) for text in texts]
        results: dict[int, str] = {}
        with self._lock:
            for i, key in enumerate(keys):
                if key in self._cache:
                    self._cache.move_to_end(key)
                    results[i] = self._cache[key]
            self.hits += len(results)
        missing = [i for i in range(len(texts)) if i not in results]
        if missing:
            translated = self.translator.translate([texts[i] for i in missing], source, target)
            with self._lock:
                self.misses += len(missing)
                for i, text in zip(missing, translated):
                    results[i] = self._cache[keys[i]] = text
                    self._cache.move_to_end(keys[i])
                while len(self._cache) > self.max_entries:
                    self._cache.popitem(last=False)   # forget the least recently used
        return [results[i] for i in range(len(texts))]


class FallbackTranslator:
    """The main translator, and a second one when it fails (Claude down, slow or out of credit: Gemini).

    A failed translation would otherwise leave the caregiver with no answer, only the closest reviewed
    questions. Both translators get the same prompt and glossary, so the answer differs only in wording.
    If the backup fails too, its error goes to the caller, which then offers the reviewed questions.
    """

    def __init__(self, primary: Translator, backup: Translator) -> None:
        self.primary, self.backup = primary, backup
        self.name = primary.name
        self.whole_text = getattr(primary, "whole_text", False)
        self.fallbacks = 0

    def translate(self, texts: Sequence[str], source: str, target: str) -> list[str]:
        try:
            return self.primary.translate(texts, source, target)
        except Exception:
            self.fallbacks += 1
            log.warning("%s failed; translating with %s instead", self.primary.name, self.backup.name, exc_info=True)
            return self.backup.translate(texts, source, target)


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

    A translator with ``whole_text`` (Gemini, Claude) gets the text in one piece instead.
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
# A caregiver is waiting: give up on a slow request instead of waiting 20 s (most answer in 2-4 s).
GEMINI_TIMEOUT_MS = 15_000
# Tried in turn when the main model is busy. gemini-3.1-flash-lite was left out: it invented words.
GEMINI_FALLBACK_MODELS = ("gemini-3.6-flash", "gemini-3.5-flash-lite")
GEMINI_RETRIES = 2     # main model, then the next one; flash-lite (third) wrote poor Kinyarwanda
LANGUAGE_NAMES = {"en": "English", "rw": "Kinyarwanda"}


def translation_prompt(text: str, source: str, target: str, glossary: str) -> str:
    """The translation instructions. Gemini and Claude get the same prompt, so they can be compared fairly."""
    return f"""Translate this text from {LANGUAGE_NAMES[source]} to {LANGUAGE_NAMES[target]}.
It is from a child-nutrition assistant for parents and caregivers in Rwanda. Write natural, everyday
{LANGUAGE_NAMES[target]}{" as spoken in Rwanda (not Kirundi)" if target == "rw" else ""}. Keep every fact,
number, age and unit exactly, and keep the line breaks and list markers. Add nothing and leave nothing out.
Reply with the translation only.

Use these terms (English = Kinyarwanda):
{glossary}
- breast milk = amashereka
- porridge = igikoma (never umuhogo, which is cassava)
- to mash or grind food = gusya (never gusekura)

Text:
{text}"""


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
        return translation_prompt(text, source, target, self.glossary)

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


CLAUDE_MODEL = "claude-sonnet-5-5"
# Sonnet translates an answer in about 7 s and a question in about 2.5 s (2026-11-08). A request that takes
# more than 15 s is stuck; with one retry a caregiver waits at most about 30 s before the fallback (Gemini).
CLAUDE_TIMEOUT_S = 15.0
CLAUDE_RETRIES = 1
CLAUDE_MAX_TOKENS = 4096   # a long Kinyarwanda answer is under 1,500 tokens; the rest leaves room for thinking
# On a refusal the API re-runs the request on a suitable other Claude model in the same call.
CLAUDE_FALLBACK_BETA = "server-side-fallback-2026-07-01"
ANTHROPIC_KEY_NAME = "ANTHROPIC_API_KEY"
CLAUDE_SYSTEM = ("You translate for a child-nutrition assistant. Caregivers read your translation directly, so "
                 "give one finished translation only: no drafts, corrections, notes or headings. Revise in your "
                 "head before answering, never in the reply.")
CLAUDE_SCHEMA = {"type": "object", "properties": {"translation": {"type": "string"}},
                 "required": ["translation"], "additionalProperties": False}
# Dollars per million tokens (input, output), to report what a run cost. Check anthropic.com/pricing.
CLAUDE_PRICES = {"claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50), "claude-opus-5-5": (4.0, 20.0)}


def anthropic_api_key(env_path: str | Path = ".env") -> str:
    """The Anthropic API key from the environment, else from ``.env``.

    This is a key from console.anthropic.com (pay as you go). A Claude Pro subscription does not include one.
    """
    if os.environ.get(ANTHROPIC_KEY_NAME):
        return os.environ[ANTHROPIC_KEY_NAME]
    env_path = Path(env_path)
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            name, _, value = line.partition("=")
            if name.strip().upper() == ANTHROPIC_KEY_NAME and value.strip():
                return value.strip().strip("'\"")
    raise RuntimeError(f"No Anthropic API key: add {ANTHROPIC_KEY_NAME}=... to {env_path} or the environment")


class ClaudeTranslator:
    """Anthropic Claude through the ``anthropic`` package (key ``ANTHROPIC_API_KEY`` in ``.env``).

    Same prompt and glossary as :class:`GeminiTranslator`, and each text is translated whole. Like Gemini it
    needs the internet and sends the question and answer to Anthropic. Effort is low: translation needs
    little reasoning, and more thinking only makes the caregiver wait. Token use is counted so a run can
    report what it cost.
    """

    whole_text = True

    def __init__(self, model: str = CLAUDE_MODEL, api_key: str | None = None) -> None:
        import anthropic

        from .qa_data.gemini_drafts import _glossary

        # The SDK retries rate limits (429), busy servers (5xx) and dropped connections itself.
        self.client = anthropic.Anthropic(api_key=api_key or anthropic_api_key(), timeout=CLAUDE_TIMEOUT_S,
                                          max_retries=CLAUDE_RETRIES)
        self.model = model
        self.glossary = _glossary()
        self.name = model
        self.input_tokens = self.output_tokens = 0

    def prompt(self, text: str, source: str, target: str) -> str:
        return translation_prompt(text, source, target, self.glossary)

    def translate(self, texts: Sequence[str], source: str, target: str) -> list[str]:
        return [self._generate(self.prompt(text, source, target)) for text in texts]

    def cost_usd(self) -> float | None:
        """What the translations so far cost, if the model's price is known."""
        prices = CLAUDE_PRICES.get(self.model)
        if prices is None:
            return None
        return (self.input_tokens * prices[0] + self.output_tokens * prices[1]) / 1_000_000

    def _generate(self, prompt: str) -> str:
        # Without the schema, Claude sometimes wrote several drafts into the reply ("Nkosoye...", "Final:"),
        # and the caregiver saw them all. One "translation" field leaves room for exactly one.
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=CLAUDE_MAX_TOKENS,
            system=CLAUDE_SYSTEM,
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": CLAUDE_SCHEMA}},
            betas=[CLAUDE_FALLBACK_BETA],
            fallbacks="default",
            messages=[{"role": "user", "content": prompt}],
        )
        self.input_tokens += response.usage.input_tokens
        self.output_tokens += response.usage.output_tokens
        # A refused or cut-off translation must not reach a caregiver: the caller then offers reviewed questions.
        if response.stop_reason == "refusal":
            raise RuntimeError(f"Claude declined to translate (request {response._request_id})")
        if response.stop_reason == "max_tokens":
            raise RuntimeError(f"Claude's translation was cut off (request {response._request_id})")
        reply = "".join(block.text for block in response.content if block.type == "text")
        try:
            # A stray "}" from the JSON sometimes ends up inside the text; the answers never contain braces.
            text = json.loads(reply)["translation"].replace("{", "").replace("}", "").strip()
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            raise RuntimeError(f"Claude's reply was not a translation (request {response._request_id})") from error
        if not text:
            raise RuntimeError(f"Claude returned no translation (request {response._request_id})")
        return text


class TermAwareTranslator:
    """Wraps a translator: known terms are written in the target language before translating."""

    def __init__(self, translator: Translator, terminology: Terminology | None = None) -> None:
        self.translator = translator
        self.terminology = terminology or Terminology.load()
        self.name = translator.name

    def translate(self, texts: Sequence[str], source: str, target: str) -> list[str]:
        prepared = [self.terminology.prepare(text, source, target) for text in texts]
        return self.translator.translate(prepared, source, target)
