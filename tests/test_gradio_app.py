"""The Gradio app for the ZeroGPU Space, with a scripted model: reply formatting, meal plans and the page."""

import sys
from pathlib import Path

import pytest

gr = pytest.importorskip("gradio")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import gradio_app  # noqa: E402
from nutriassist.inference.scripted import ScriptedChatModel  # noqa: E402
from nutriassist.planner import PlanRequest  # noqa: E402
from texts import EXAMPLES  # noqa: E402


@pytest.fixture(scope="module")
def services():
    return gradio_app.Services.create(ScriptedChatModel(lambda q: "Give mashed beans with avocado."))


def test_urgent_reply_shows_the_banner_and_who_answered(services):
    text = gradio_app.format_reply(services.assistant.ask("My child is having a seizure"))
    assert text.startswith("🚨 **Danger sign detected**")
    assert "912" in text and "Answered by the safety rules" in text


def test_honey_question_is_answered_by_the_rules(services):
    reply = services.assistant.ask("Can I give honey to my 5 month old?")
    assert "12 months" in gradio_app.format_reply(reply) and "safety rules" in gradio_app.format_reply(reply)


def test_model_reply_names_the_model(services):
    text = gradio_app.format_reply(services.assistant.ask("What can a 9-month-old eat for supper?"))
    assert text.startswith("Give mashed beans") and services.assistant.model.name in text


def test_unanswered_kinyarwanda_question_lists_suggestions(services):
    reply = services.assistant.ask("Umwana wanjye w'amezi 9 yarya iki ngo agire imbaraga?")
    assert reply.suggestions
    assert all(f"- {s}" in gradio_app.format_reply(reply) for s in reply.suggestions)


def test_question_buttons_hide_the_unused_ones():
    updates = gradio_app.question_buttons(["only one"])
    assert updates[0]["value"] == "only one" and updates[0]["visible"]
    assert [u["visible"] for u in updates[1:]] == [False] * (gradio_app.N_QUESTION_BUTTONS - 1)


@pytest.mark.parametrize("lang, heading", [("en", "Feeding tips"), ("rw", "Inama zo kugaburira")])
def test_meal_plan_markdown_in_both_languages(services, lang, heading):
    plan = services.planner.plan(PlanRequest(age_months=12, days=7, breastfed=True)).to_dict(lang)
    text = gradio_app.plan_markdown(plan, lang)
    assert heading in text
    assert sum(line.startswith("## ") for line in text.splitlines()) == 7   # one heading per day


@pytest.mark.integration
def test_load_model_merges_the_adapter_and_answers(tmp_path, monkeypatch):
    """The Space's model path, with a tiny random Qwen2 model and adapter instead of Gemma from the Hub."""
    torch = pytest.importorskip("torch")
    transformers = pytest.importorskip("transformers")
    peft = pytest.importorskip("peft")
    import huggingface_hub

    try:
        tokenizer = transformers.AutoTokenizer.from_pretrained("Qwen/Qwen2.5-1.5B-Instruct")
    except OSError as error:
        pytest.skip(f"Qwen tokenizer not available: {error}")
    config = transformers.Qwen2Config(vocab_size=len(tokenizer), hidden_size=32, intermediate_size=64,
                                      num_hidden_layers=2, num_attention_heads=4, num_key_value_heads=2,
                                      max_position_embeddings=1024, tie_word_embeddings=True)
    torch.manual_seed(0)
    base = tmp_path / "base"
    transformers.Qwen2ForCausalLM(config).save_pretrained(base)
    tokenizer.save_pretrained(base)
    repo = tmp_path / "repo"
    lora = peft.LoraConfig(r=4, lora_alpha=8, target_modules=["q_proj", "v_proj"], task_type="CAUSAL_LM")
    peft.get_peft_model(transformers.AutoModelForCausalLM.from_pretrained(base), lora).save_pretrained(repo / "adapter")
    tokenizer.save_pretrained(repo / "adapter")

    monkeypatch.setattr(huggingface_hub, "snapshot_download", lambda repo_id, allow_patterns: str(repo))
    monkeypatch.setenv("NUTRIASSIST_BASE_MODEL", str(base))
    monkeypatch.setenv("NUTRIASSIST_ADAPTER_REPO", "someone/adapter-repo")
    monkeypatch.setenv("NUTRIASSIST_MAX_NEW_TOKENS", "8")
    model = gradio_app.load_model()

    assert isinstance(model, gradio_app.ZeroGPUChatModel)
    assert not isinstance(gradio_app._GPU_MODEL.model, peft.PeftModel)   # merged into the base weights
    reply = gradio_app.Services.create(model).assistant.ask("What can a 9-month-old eat for supper?")
    assert reply.source.value == "model" and reply.model_name.endswith("someone/adapter-repo")


def test_page_builds_with_every_example_question(services):
    demo = gradio_app.build_demo(services)
    assert isinstance(demo, gr.Blocks)
    assert len(EXAMPLES["en"]) >= gradio_app.N_QUESTION_BUTTONS
