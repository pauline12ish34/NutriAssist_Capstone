"""ClaudeTranslator with a fake Anthropic client: no network, no API key, nothing billed."""

import json
from types import SimpleNamespace

import pytest

from nutriassist.api.settings import Settings, build_translator
from nutriassist.translation import (CLAUDE_FALLBACK_BETA, ClaudeTranslator, anthropic_api_key,
                                     translate_text, translation_prompt)


class FakeMessages:
    def __init__(self, text="Ha umwana amashereka.", stop_reason="end_turn", raw=None):
        self.text, self.stop_reason, self.raw, self.calls = text, stop_reason, raw, []

    def create(self, **request):
        self.calls.append(request)
        content = [SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=self.raw if self.raw is not None
                                                                         else json.dumps({"translation": f" {self.text} "}))]
        return SimpleNamespace(content=content, stop_reason=self.stop_reason, _request_id="req_test",
                               usage=SimpleNamespace(input_tokens=1000, output_tokens=200))


def fake_translator(**fake) -> tuple[ClaudeTranslator, FakeMessages]:
    translator = ClaudeTranslator.__new__(ClaudeTranslator)   # skips the real client
    messages = FakeMessages(**fake)
    translator.client = SimpleNamespace(beta=SimpleNamespace(messages=messages))
    translator.model = translator.name = "claude-sonnet-5-5"
    translator.glossary = "- iron = ubutare"
    translator.input_tokens = translator.output_tokens = 0
    return translator, messages


def test_translates_with_the_shared_prompt_and_low_effort():
    translator, messages = fake_translator()
    assert translator.translate(["Give the baby breast milk."], "en", "rw") == ["Ha umwana amashereka."]
    request = messages.calls[0]
    assert request["model"] == "claude-sonnet-5-5"
    assert request["output_config"]["effort"] == "low"
    assert request["output_config"]["format"]["schema"]["required"] == ["translation"]   # one translation, no drafts
    assert "no drafts" in request["system"]
    assert request["fallbacks"] == "default" and request["betas"] == [CLAUDE_FALLBACK_BETA]
    assert "temperature" not in request   # rejected by the current API version
    prompt = request["messages"][0]["content"]
    assert prompt == translation_prompt("Give the baby breast milk.", "en", "rw", "- iron = ubutare")
    assert "not Kirundi" in prompt and "ubutare" in prompt


def test_counts_tokens_and_cost():
    translator, _ = fake_translator()
    translator.translate(["One.", "Two."], "en", "rw")
    assert (translator.input_tokens, translator.output_tokens) == (2000, 400)
    assert translator.cost_usd() == pytest.approx((2000 * 2.0 + 400 * 10.0) / 1_000_000)


def test_glossary_still_fixes_known_mistakes():
    translator, _ = fake_translator(text="Icyuma ni ingenzi.")
    assert translate_text(translator, "Iron is important.", "en", "rw") == "Ubutare ni ingenzi."


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_refused_or_cut_off_translation_is_an_error(stop_reason):
    translator, _ = fake_translator(stop_reason=stop_reason)
    with pytest.raises(RuntimeError):
        translator.translate(["Hello."], "en", "rw")


def test_reply_that_is_not_the_schema_is_an_error():
    translator, _ = fake_translator(raw="Draft 1... Final: Ha umwana amashereka.")
    with pytest.raises(RuntimeError):
        translator.translate(["Hello."], "en", "rw")


def test_empty_translation_is_an_error():
    translator, _ = fake_translator(text="")
    with pytest.raises(RuntimeError):
        translator.translate(["Hello."], "en", "rw")


def test_api_key_comes_from_env_file(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text("GEMINI_API_KEY=g\nANTHROPIC_API_KEY='sk-ant-test'\n", encoding="utf-8")
    assert anthropic_api_key(env) == "sk-ant-test"
    with pytest.raises(RuntimeError):
        anthropic_api_key(tmp_path / "missing.env")


def test_claude_is_a_known_translator_and_falls_back_without_a_key(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)   # no .env here
    assert build_translator(Settings(translator="claude")) is None   # reviewed answers only, no crash


def test_claude_model_setting(monkeypatch):
    monkeypatch.setenv("NUTRIASSIST_TRANSLATOR", "claude")
    monkeypatch.setenv("NUTRIASSIST_CLAUDE_MODEL", "claude-haiku-5-5")
    settings = Settings.from_env()
    assert (settings.translator, settings.claude_model) == ("claude", "claude-haiku-5-5")
