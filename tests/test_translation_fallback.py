"""A failed Claude translation falls back to Gemini, slow requests give up sooner, and each step is timed."""

import logging

import pytest

from nutriassist import translation
from nutriassist.assistant import NutritionAssistant, ReplySource
from nutriassist.inference.scripted import ScriptedChatModel
from nutriassist.translation import FallbackTranslator


class FakeTranslator:
    whole_text = True

    def __init__(self, name, prefix="", error=None):
        self.name, self.prefix, self.error, self.calls = name, prefix, error, 0

    def translate(self, texts, source, target):
        self.calls += 1
        if self.error:
            raise self.error
        return [f"{self.prefix}{text}" for text in texts]


def test_the_main_translator_is_used_when_it_works():
    claude, gemini = FakeTranslator("claude", "C:"), FakeTranslator("gemini", "G:")
    fallback = FallbackTranslator(claude, gemini)
    assert fallback.translate(["Muraho"], "rw", "en") == ["C:Muraho"]
    assert (gemini.calls, fallback.fallbacks, fallback.name, fallback.whole_text) == (0, 0, "claude", True)


def test_a_failed_translation_is_done_by_the_backup():
    claude = FakeTranslator("claude", error=TimeoutError("Claude took longer than 15 s"))
    gemini = FakeTranslator("gemini", "G:")
    fallback = FallbackTranslator(claude, gemini)
    assert fallback.translate(["Muraho"], "rw", "en") == ["G:Muraho"]
    assert fallback.fallbacks == 1


def test_when_both_fail_the_error_reaches_the_caller():
    fallback = FallbackTranslator(FakeTranslator("claude", error=TimeoutError()),
                                  FakeTranslator("gemini", error=ConnectionError("no internet")))
    with pytest.raises(ConnectionError):
        fallback.translate(["Muraho"], "rw", "en")


def test_slow_requests_give_up_within_about_half_a_minute():
    # Before: Claude 30 s x 4 tries and Gemini 20 s x 4 tries, so one answer could wait minutes.
    assert translation.CLAUDE_TIMEOUT_S * (1 + translation.CLAUDE_RETRIES) <= 30
    assert translation.GEMINI_TIMEOUT_MS / 1000 * translation.GEMINI_RETRIES <= 30


def test_claude_translation_uses_gemini_as_backup_when_its_key_is_set(monkeypatch):
    from nutriassist.api import settings as settings_module

    monkeypatch.setattr(translation, "ClaudeTranslator", lambda model: FakeTranslator("claude"))
    monkeypatch.setattr(translation, "GeminiTranslator", lambda: FakeTranslator("gemini"))
    built = settings_module.build_translator(settings_module.Settings(kinyarwanda="translate", translator="claude"))
    assert isinstance(built.translator, FallbackTranslator)
    assert (built.translator.primary.name, built.translator.backup.name) == ("claude", "gemini")


def test_claude_translation_works_alone_without_a_gemini_key(monkeypatch):
    from nutriassist.api import settings as settings_module

    def no_key():
        raise RuntimeError("No Gemini API key")

    monkeypatch.setattr(translation, "ClaudeTranslator", lambda model: FakeTranslator("claude"))
    monkeypatch.setattr(translation, "GeminiTranslator", no_key)
    built = settings_module.build_translator(settings_module.Settings(kinyarwanda="translate", translator="claude"))
    assert built.translator.name == "claude" and not isinstance(built.translator, FallbackTranslator)


def test_each_step_of_a_kinyarwanda_answer_is_timed_in_the_log(caplog):
    assistant = NutritionAssistant(ScriptedChatModel(lambda q: "Give eggs from 6 months."),
                                   translator=FakeTranslator("claude"))
    with caplog.at_level(logging.INFO, logger="nutriassist.assistant"):
        reply = assistant.ask("Umwana wanjye w'amezi 9 ashobora kurya amagi buri munsi?")
    assert reply.source is ReplySource.MODEL and reply.translated
    line = next(r.getMessage() for r in caplog.records if "Kinyarwanda answer in" in r.getMessage())
    assert "question to English" in line and "model" in line and "answer to Kinyarwanda" in line
