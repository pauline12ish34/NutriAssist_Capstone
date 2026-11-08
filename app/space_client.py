"""Backend for Streamlit Community Cloud: chat on the ZeroGPU Space, everything else in this process.

Streamlit Community Cloud has too little memory for the model, and Hugging Face no longer hosts Streamlit
apps for free. So on Community Cloud:

- **chat** goes to the ``/chat_json`` endpoint of the Gradio ZeroGPU Space (app/gradio_app.py), where the
  safety rules, reviewed answers, translation and the fine-tuned model run on a GPU. Danger signs are the
  exception: they are answered here, by the same rules, so they never wait in the Space's queue;
- the **growth check**, **meal planner** and food list run here: they are fast, pure Python and need no model.

``SpaceClient`` has the same methods and returns the same data as ``NutriAssistClient`` (the FastAPI client),
so the pages work unchanged with either one. ``api_client.make_client`` chooses between them.

Settings (Streamlit Community Cloud secrets, or environment variables):
    NUTRIASSIST_SPACE       the Space, e.g. "pauline-ish/nutriAssist_Rw", or a Gradio URL for local tests
    NUTRIASSIST_API_TOKEN   the same secret as on the Space, so only this app can use its /chat_json endpoint
    HF_TOKEN                optional Hugging Face token: GPU time is then counted on that account, not shared
"""

from __future__ import annotations

import os
import threading
from functools import lru_cache

import requests

from api_client import ApiError
from nutriassist import __version__
from nutriassist.assistant import InvalidQuestion, NutritionAssistant
from nutriassist.inference.scripted import ScriptedChatModel
from nutriassist.planner import FoodCatalogue, MealPlanner, PlanRequest
from nutriassist.safety.subject import is_about_adult_only
from nutriassist.screening import ScreeningInputError, ScreeningRequest, screen

# Space states in which the Space cannot answer. A sleeping Space wakes up on the first question.
DOWN_STAGES = {"PAUSED", "STOPPED", "RUNTIME_ERROR", "BUILD_ERROR", "CONFIG_ERROR", "NO_APP_FILE", "DELETING"}
WAKING_UP = "The assistant is starting up. Please try again in a minute."


@lru_cache(maxsize=1)
def _triage() -> NutritionAssistant:
    """The safety rules alone, to answer danger signs here instead of on the Space.

    On the Space every question waits in one queue, so an urgent message waited behind other people's model
    answers (median 2.2 s in the live load test, docs/results/load_test/). Here it takes about a millisecond
    and still works when the Space is asleep or out of GPU time. Only urgent questions are answered this way,
    so the model is never called (the scripted model is a placeholder).
    """
    return NutritionAssistant(ScriptedChatModel(lambda question: ""))


def _reply_dict(reply) -> dict:
    """The fields of the Space's /chat_json reply (and the FastAPI /chat response)."""
    return {"answer": reply.answer, "language": reply.language, "safety_level": reply.safety_level,
            "danger_signs": list(reply.danger_signs), "source": reply.source.value, "model": reply.model_name,
            "latency_ms": reply.latency_ms, "translated": reply.translated,
            "matched_question": reply.matched_question, "suggestions": list(reply.suggestions)}


@lru_cache(maxsize=1)
def _planner() -> tuple[FoodCatalogue, MealPlanner]:
    catalogue = FoodCatalogue.load()
    return catalogue, MealPlanner(catalogue)


_connections: dict[tuple[str, str | None], object] = {}
_connections_lock = threading.Lock()


def _gradio_client(space: str, hf_token: str | None):
    """One connection per Space, shared by every visitor (connecting fetches the Space's API description)."""
    with _connections_lock:
        if (space, hf_token) not in _connections:
            from gradio_client import Client

            _connections[space, hf_token] = Client(space, token=hf_token, verbose=False)
        return _connections[space, hf_token]


class SpaceClient:
    """Same interface as ``api_client.NutriAssistClient``."""

    def __init__(self, space: str | None = None, api_token: str | None = None, hf_token: str | None = None,
                 connect=None) -> None:
        self.space = (space or os.environ.get("NUTRIASSIST_SPACE", "")).strip()
        self.api_token = api_token if api_token is not None else os.environ.get("NUTRIASSIST_API_TOKEN", "")
        self.hf_token = hf_token if hf_token is not None else (os.environ.get("HF_TOKEN") or None)
        self._connect = connect or _gradio_client

    @property
    def is_url(self) -> bool:
        return self.space.startswith(("http://", "https://"))

    @property
    def base_url(self) -> str:
        return self.space if self.is_url else f"https://huggingface.co/spaces/{self.space}"

    # ---------------------------------------------------------------- the Space

    def health(self) -> dict:
        try:
            if self.is_url:
                requests.get(self.space, timeout=5).raise_for_status()
            else:
                info = requests.get(f"https://huggingface.co/api/spaces/{self.space}", timeout=5).json()
                stage = (info.get("runtime") or {}).get("stage", "")
                if stage in DOWN_STAGES:
                    raise ApiError(f"The assistant's server is not running ({stage}).")
        except requests.RequestException as error:
            raise ApiError("Cannot reach the assistant's server.") from error
        return {"status": "ok", "model": f"{self.space} (ZeroGPU)", "demo_mode": False, "version": __version__}

    def chat(self, question: str) -> dict:
        triage = _triage()
        # Danger signs and questions about adults only (a grandmother, a husband) are answered here by the same
        # rules: an urgent message never waits in the Space's queue, and no GPU time goes to off-scope questions.
        if triage.detector.assess(question or "").is_urgent or is_about_adult_only(question or ""):
            try:
                return _reply_dict(triage.ask(question))
            except InvalidQuestion:
                pass   # too long, for example: the Space gives the usual message
        try:
            reply = self._connect(self.space, self.hf_token).predict(question, self.api_token,
                                                                     api_name="/chat_json")
        except Exception as error:   # Space asleep, starting, out of GPU time, or the network failed
            raise ApiError(WAKING_UP) from error
        if not isinstance(reply, dict):
            raise ApiError(WAKING_UP)
        if "error" in reply:
            raise ApiError(reply["error"], reply.get("status"))
        return reply

    # ---------------------------------------------------------------- here, no model needed

    def meal_plan(self, age_months: int, days: int, breastfed: bool, language: str,
                  available: list[str] | None = None, excluded: list[str] | None = None) -> dict:
        _, planner = _planner()
        try:
            plan = planner.plan(PlanRequest(age_months=age_months, days=days, breastfed=breastfed,
                                            available=frozenset(available) if available is not None else None,
                                            excluded=frozenset(excluded or ())))
        except ValueError as error:
            raise ApiError(str(error), 422) from error
        return plan.to_dict(language)

    def screening(self, age_months: int, sex: str, weight_kg: float, height_cm: float | None,
                  muac_cm: float | None, oedema: bool, breastfed: bool, language: str) -> dict:
        try:
            result = screen(ScreeningRequest(age_months=age_months, sex=sex, weight_kg=weight_kg,
                                             height_cm=height_cm, muac_cm=muac_cm, oedema=oedema))
        except ScreeningInputError as error:
            raise ApiError(error.message(language), 422) from error
        data = result.to_dict(language)
        plan = None
        if data.pop("meal_plan"):
            _, planner = _planner()
            plan = planner.plan(PlanRequest(age_months=age_months, days=1, breastfed=breastfed,
                                            conditions=frozenset(result.conditions))).to_dict(language)
        return {**data, "meal_plan": plan}

    def foods(self) -> list[dict]:
        catalogue, _ = _planner()
        return [{"key": f.key, "name_en": f.name_en, "name_rw": f.name_rw, "group": f.group,
                 "min_age_months": f.min_age_months} for f in (catalogue[k] for k in catalogue.keys)]
