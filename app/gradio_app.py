"""NutriAssist-RW web app for a Hugging Face ZeroGPU Space (Gradio): chat, meal planner and how-to page.

Run locally:  python app/gradio_app.py   (NUTRIASSIST_BASE_MODEL=demo for placeholder answers, no download)

Unlike the Streamlit app, this one has no separate API: the assistant runs in the same process, because
ZeroGPU lends a GPU only to Gradio apps. The safety rules, reviewed answers and meal planner are the same
code as in the Docker app; only the model is loaded differently (Transformers on a GPU, not llama.cpp).
A GPU is requested only while the model writes an answer, so safety rules and reviewed answers never
wait for one.

Configuration (environment variables, or the Space's Settings > Variables):
    NUTRIASSIST_BASE_MODEL       base model (default unsloth/gemma-3-4b-it), or "demo"
    NUTRIASSIST_ADAPTER_REPO     Hugging Face repo with the LoRA adapter, or "none" (default pauline-ish/NutritionAssistant_RW)
    NUTRIASSIST_ADAPTER_FOLDER   folder of the adapter inside that repo (default adapter)
    NUTRIASSIST_MAX_NEW_TOKENS   longest answer in tokens (default 320)
"""

from __future__ import annotations

import logging
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).parent))  # lets this file import texts

import gradio as gr  # noqa: E402

from nutriassist.api.settings import (Settings, build_chat_model, build_example_index, build_knowledge_base,  # noqa: E402
                                      build_translator, reviewed_only_languages)
from nutriassist.assistant import AssistantReply, InvalidQuestion, NutritionAssistant, ReplySource  # noqa: E402
from nutriassist.inference.base import ChatModel, GenerationSettings  # noqa: E402
from nutriassist.planner import FoodCatalogue, MealPlanner, PlanRequest  # noqa: E402
from nutriassist.prompts import Message  # noqa: E402
from texts import ABOUT, EXAMPLES, TEXT  # noqa: E402

try:
    import spaces  # only on Hugging Face Spaces
except ImportError:
    spaces = None

log = logging.getLogger("nutriassist.gradio")

DEFAULT_BASE_MODEL = "unsloth/gemma-3-4b-it"
DEFAULT_ADAPTER_REPO = "pauline-ish/NutritionAssistant_RW"
LANGUAGES = [("English", "en"), ("Kinyarwanda", "rw")]
NUTRIENTS = ("energy_kcal", "protein_g", "iron_mg", "calcium_mg")
N_QUESTION_BUTTONS = 4
AI_WRITTEN = (ReplySource.MODEL, ReplySource.MODEL_WITH_REFERRAL)   # answers that get the AI warning
MODEL_ERROR = {
    "en": "The assistant is not available right now. Please try again in a minute.",
    "rw": "Porogaramu ntiri gukora ubu. Ongera ugerageze nyuma y'umunota umwe.",
}


def t(key: str, lang: str) -> str:
    return TEXT[key][lang]


# ---------------------------------------------------------------- model

def _on_gpu(function):
    """``spaces.GPU`` on a ZeroGPU Space; elsewhere the function runs as it is."""
    return spaces.GPU(duration=60)(function) if spaces is not None else function


_GPU_MODEL: ChatModel | None = None   # module level: ZeroGPU runs GPU functions in a worker that sees globals


@_on_gpu
def _generate_on_gpu(conversations: list[list[Message]]) -> list[str]:
    return _GPU_MODEL.generate_batch(conversations)


class ZeroGPUChatModel(ChatModel):
    """Borrows a ZeroGPU GPU only for the time it takes to write an answer."""

    def __init__(self, model: ChatModel) -> None:
        super().__init__(model.settings)
        global _GPU_MODEL
        _GPU_MODEL = model
        self.name = model.name

    def generate_batch(self, conversations: Sequence[Sequence[Message]]) -> list[str]:
        return _generate_on_gpu([list(conversation) for conversation in conversations])


def load_model() -> ChatModel:
    """The fine-tuned model: base model + LoRA adapter, merged, in bfloat16 on the GPU (float32 on a CPU)."""
    base_model = os.environ.get("NUTRIASSIST_BASE_MODEL", DEFAULT_BASE_MODEL)
    if base_model == "demo":
        return build_chat_model(Settings(backend="demo"))[0]

    import torch
    from huggingface_hub import snapshot_download
    from transformers import AutoModelForCausalLM

    from nutriassist.inference.transformers_model import TransformersChatModel, attention_implementation, load_tokenizer

    gpu = torch.cuda.is_available()
    attention = {"attn_implementation": impl} if (impl := attention_implementation(base_model)) else {}
    model = AutoModelForCausalLM.from_pretrained(base_model, dtype=torch.bfloat16 if gpu else torch.float32, **attention)
    tokenizer_source, name = base_model, base_model
    adapter_repo = os.environ.get("NUTRIASSIST_ADAPTER_REPO", DEFAULT_ADAPTER_REPO)
    if adapter_repo.lower() != "none":
        from peft import PeftModel

        folder = os.environ.get("NUTRIASSIST_ADAPTER_FOLDER", "adapter")
        adapter = Path(snapshot_download(adapter_repo, allow_patterns=[f"{folder}/*"])) / folder
        # Merging once at start-up makes every answer faster than running the adapter beside the model.
        # On ZeroGPU no GPU is attached at start-up although CUDA reports one, so load the adapter on the CPU.
        model = PeftModel.from_pretrained(model, str(adapter), torch_device="cpu").merge_and_unload()
        tokenizer_source, name = adapter, f"{base_model} + {adapter_repo}"
    if gpu:
        model.to("cuda")
    settings = GenerationSettings(max_new_tokens=int(os.environ.get("NUTRIASSIST_MAX_NEW_TOKENS", 320)), batch_size=1)
    return ZeroGPUChatModel(TransformersChatModel(model, load_tokenizer(tokenizer_source), settings, name=name))


@dataclass
class Services:
    assistant: NutritionAssistant
    catalogue: FoodCatalogue
    planner: MealPlanner

    @classmethod
    def create(cls, model: ChatModel | None = None) -> "Services":
        env = os.environ.get
        # Space variables: NUTRIASSIST_KINYARWANDA (translate / model / reviewed) and NUTRIASSIST_GROUNDING (RAG).
        settings = Settings(kinyarwanda=env("NUTRIASSIST_KINYARWANDA", Settings.kinyarwanda).lower(),
                            grounding=int(env("NUTRIASSIST_GROUNDING", Settings.grounding)))
        knowledge = build_knowledge_base(settings)
        # Gemini translation needs the Space secret GEMINI_API_KEY; without it Kinyarwanda gets reviewed answers only.
        translator = build_translator(settings) if model is None else None
        assistant = NutritionAssistant(model or load_model(), knowledge=knowledge, translator=translator,
                                       reviewed_only=reviewed_only_languages(settings, knowledge, translator),
                                       grounding=settings.grounding,
                                       examples=build_example_index(settings) if model is None else None)
        catalogue = FoodCatalogue.load()
        return cls(assistant, catalogue, MealPlanner(catalogue))


# ---------------------------------------------------------------- chat

def format_reply(reply: AssistantReply) -> str:
    lang = reply.language
    parts = []
    if reply.safety_level == "urgent":
        parts.append(f"🚨 **{t('urgent_banner', lang)}**")
    elif reply.safety_level == "medical":
        parts.append(f"⚠️ **{t('medical_banner', lang)}**")
    parts.append(reply.answer)
    if reply.translated:
        parts.append(f"_{t('machine_translated', lang)}_")
    if reply.suggestions:
        parts.append("\n".join(f"- {suggestion}" for suggestion in reply.suggestions))
    if reply.source in AI_WRITTEN:
        parts.append(f"_🤖 {t('ai_warning', lang)}_")
    return "\n\n".join(parts)


def question_buttons(questions: Sequence[str]) -> list:
    """Example questions, or the "Did you mean...?" suggestions after an unanswered question."""
    questions = list(questions)[:N_QUESTION_BUTTONS]
    return [gr.update(value=questions[i], visible=True) if i < len(questions) else gr.update(visible=False)
            for i in range(N_QUESTION_BUTTONS)]


# ---------------------------------------------------------------- meal planner

def plan_markdown(plan: dict, lang: str) -> str:
    lines = []
    if plan["unfilled_slots"]:
        lines.append(f"⚠️ **{t('missing_slots', lang)}:**")
        lines += [f"- {t('slot_' + slot, lang)}" for slot in plan["unfilled_slots"]]
        lines.append("")
    for day in plan["days"]:
        if len(plan["days"]) > 1:
            lines.append(f"## {t('day', lang)} {day['day']}")
        for meal in day["meals"]:
            lines += [f"**{meal['meal']}**", "",
                      f"| {t('food', lang)} | {t('amount', lang)} | {t('grams', lang)} |", "|---|---|---:|"]
            lines += [f"| {f['name']} | {f['household_measure']} | {f['grams']} |" for f in meal["foods"]]
            lines.append("")
        lines += [f"**{t('coverage', lang)}**", "",
                  "| " + " | ".join(t(n, lang) for n in NUTRIENTS) + " |", "|" + "---:|" * len(NUTRIENTS),
                  "| " + " | ".join(f"{day['coverage_pct'][n]}%" for n in NUTRIENTS) + " |", ""]
        verdict = t("diversity_ok", lang) if day["meets_min_diversity"] else t("diversity_low", lang)
        lines += [f"**{t('diversity', lang)}: {day['dietary_diversity']}/8** ({verdict})",
                  f"_{', '.join(day['food_groups'])}_", ""]
    lines.append(f"### 💡 {t('tips', lang)}")
    lines += [f"- {tip}" for tip in plan["tips"]]
    return "\n".join(lines)


# ---------------------------------------------------------------- page

def build_demo(services: Services | None = None) -> gr.Blocks:
    services = services or Services.create()
    catalogue = services.catalogue

    def food_choices(lang: str) -> list[tuple[str, str]]:
        name = "name_rw" if lang == "rw" else "name_en"
        return [(getattr(catalogue[key], name), key) for key in catalogue.keys]

    def header(lang: str) -> str:
        return f"# 🥣 NutriAssist-RW\n{t('tagline', lang)}\n\n🚑 **{t('emergency', lang)}**"

    def ask(question: str, history: list, lang: str):
        question = (question or "").strip()
        if not question:
            return (history, "", *[gr.update()] * N_QUESTION_BUTTONS, gr.update())
        history = [*history, {"role": "user", "content": question}]
        suggestions: list[str] = []
        try:
            reply = services.assistant.ask(question)
            answer, suggestions = format_reply(reply), reply.suggestions
        except InvalidQuestion as error:
            answer = str(error)
        except Exception:  # the model or the GPU failed: say so instead of showing half an answer
            log.exception("Model error")
            answer = MODEL_ERROR[lang]
        history.append({"role": "assistant", "content": answer})
        buttons = question_buttons(suggestions or EXAMPLES[lang])
        return (history, "", *buttons, gr.update(visible=not suggestions))

    def make_plan(age: int, breastfed: bool, days: int, available: list[str], excluded: list[str], lang: str):
        try:
            plan = services.planner.plan(PlanRequest(
                age_months=int(age), days=int(days), breastfed=bool(breastfed),
                available=frozenset(available) if available else None, excluded=frozenset(excluded or ()),
            )).to_dict(lang)
        except ValueError as error:
            return f"⚠️ {error}", gr.update(visible=False)
        text = plan_markdown(plan, lang)
        path = Path(tempfile.mkdtemp()) / "nutriassist_meal_plan.md"
        path.write_text(f"# NutriAssist-RW - {t('page_planner', lang)} ({plan['age_months']} months)\n\n{text}\n",
                        encoding="utf-8")
        return text, gr.update(value=str(path), visible=True)

    with gr.Blocks(title="NutriAssist-RW") as demo:
        with gr.Sidebar():
            header_md = gr.Markdown(header("en"))
            language = gr.Radio(LANGUAGES, value="en", label=t("language", "en"))

        with gr.Column(visible=True) as disclaimer_box:   # shown once per visit, before the app can be used
            disclaimer = gr.Markdown(f"## ⚠️ {t('disclaimer_title', 'en')}\n\n{t('disclaimer', 'en')}")
            accept = gr.Button(t("disclaimer_accept", "en"), variant="primary")

        with gr.Tabs(visible=False) as tabs:
            with gr.Tab(f"💬 {t('page_chat', 'en')}") as chat_tab:
                chat_intro = gr.Markdown(t("chat_intro", "en"))
                chatbot = gr.Chatbot(height=480, show_label=False)
                question = gr.Textbox(placeholder=t("chat_placeholder", "en"), show_label=False, submit_btn=True,
                                      autofocus=True)
                examples_title = gr.Markdown(f"**{t('examples', 'en')}**")
                with gr.Row():
                    buttons = [gr.Button(text, size="sm") for text in EXAMPLES["en"][:N_QUESTION_BUTTONS]]
                clear = gr.Button(f"🗑️ {t('clear_chat', 'en')}", size="sm", variant="secondary")

            with gr.Tab(f"🍲 {t('page_planner', 'en')}") as planner_tab:
                planner_intro = gr.Markdown(t("planner_intro", "en"))
                age = gr.Slider(6, 59, value=12, step=1, label=t("age", "en"), info=t("age_help", "en"))
                breastfed = gr.Checkbox(value=True, label=t("breastfed", "en"))
                days = gr.Radio([(t("one_day", "en"), 1), (t("one_week", "en"), 7)], value=1, label=t("days", "en"))
                available = gr.Dropdown(food_choices("en"), multiselect=True, label=t("only_these", "en"))
                excluded = gr.Dropdown(food_choices("en"), multiselect=True, label=t("exclude", "en"))
                make = gr.Button(t("make_plan", "en"), variant="primary")
                plan_output = gr.Markdown()
                download = gr.File(label=t("download", "en"), visible=False)

            with gr.Tab(f"ℹ️ {t('page_about', 'en')}") as about_tab:
                about = gr.Markdown(ABOUT["en"])

        accept.click(lambda: (gr.update(visible=False), gr.update(visible=True)), None, [disclaimer_box, tabs])
        chat_outputs = [chatbot, question, *buttons, examples_title]
        question.submit(ask, [question, chatbot, language], chat_outputs)
        for button in buttons:
            button.click(ask, [button, chatbot, language], chat_outputs)
        clear.click(lambda lang: ([], *question_buttons(EXAMPLES[lang]), gr.update(visible=True)), language,
                    [chatbot, *buttons, examples_title])
        make.click(make_plan, [age, breastfed, days, available, excluded, language], [plan_output, download])

        def switch_language(lang: str):
            return (
                header(lang), gr.update(label=t("language", lang)),
                f"## ⚠️ {t('disclaimer_title', lang)}\n\n{t('disclaimer', lang)}",
                gr.update(value=t("disclaimer_accept", lang)),
                gr.update(label=f"💬 {t('page_chat', lang)}"), t("chat_intro", lang),
                gr.update(placeholder=t("chat_placeholder", lang)), f"**{t('examples', lang)}**",
                *question_buttons(EXAMPLES[lang]), gr.update(value=f"🗑️ {t('clear_chat', lang)}"),
                gr.update(label=f"🍲 {t('page_planner', lang)}"), t("planner_intro", lang),
                gr.update(label=t("age", lang), info=t("age_help", lang)), gr.update(label=t("breastfed", lang)),
                gr.update(label=t("days", lang), choices=[(t("one_day", lang), 1), (t("one_week", lang), 7)]),
                gr.update(label=t("only_these", lang), choices=food_choices(lang)),
                gr.update(label=t("exclude", lang), choices=food_choices(lang)),
                gr.update(value=t("make_plan", lang)), gr.update(label=t("download", lang)),
                gr.update(label=f"ℹ️ {t('page_about', lang)}"), ABOUT[lang],
            )

        language.change(switch_language, language, [
            header_md, language, disclaimer, accept, chat_tab, chat_intro, question, examples_title, *buttons, clear,
            planner_tab, planner_intro, age, breastfed, days, available, excluded, make, download,
            about_tab, about,
        ])
    return demo


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    build_demo().launch()
