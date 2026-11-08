"""The Streamlit Community Cloud backend: chat through the Space, growth check and meal planner in the app.

The growth check, meal planner and food list must give exactly what the FastAPI server gives, because the
same Streamlit pages show both.
"""

import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from api_client import ApiError, NutriAssistClient, make_client  # noqa: E402
from nutriassist.api.app import create_app  # noqa: E402
from nutriassist.inference.scripted import ScriptedChatModel  # noqa: E402
from space_client import WAKING_UP, SpaceClient  # noqa: E402


@pytest.fixture(scope="module")
def api():
    app = create_app(model=ScriptedChatModel(lambda q: "Give mashed beans."))
    with TestClient(app) as client:
        yield client


class FakeSpace:
    def __init__(self, reply=None, error: Exception | None = None):
        self.reply, self.error, self.calls = reply, error, []

    def predict(self, *args, api_name):
        self.calls.append((args, api_name))
        if self.error:
            raise self.error
        return self.reply


def client_with(space: FakeSpace, token: str = "s3cret") -> SpaceClient:
    return SpaceClient("pauline-ish/nutriAssist_Rw", api_token=token, hf_token=None, connect=lambda *_: space)


def test_chat_sends_the_question_and_token_to_the_json_endpoint():
    space = FakeSpace({"answer": "Give mashed beans.", "safety_level": "none", "source": "model"})
    assert client_with(space).chat("What should my baby eat?")["answer"] == "Give mashed beans."
    assert space.calls == [(("What should my baby eat?", "s3cret"), "/chat_json")]


@pytest.mark.parametrize("question", ["My child is having a seizure", "Umwana wanjye aragagara"])
def test_danger_signs_are_answered_here_without_waiting_for_the_space(api, question):
    space = FakeSpace(error=AssertionError("a danger sign must not wait in the Space's queue"))
    reply = client_with(space).chat(question)
    assert space.calls == []
    expected = api.post("/chat", json={"question": question}).json()   # the full pipeline, as on the Space
    assert reply.keys() == expected.keys()
    assert (reply["answer"], reply["source"], reply["safety_level"], reply["language"], reply["danger_signs"]) == \
           (expected["answer"], expected["source"], expected["safety_level"], expected["language"],
            expected["danger_signs"])


def test_danger_signs_are_answered_even_when_the_space_is_down():
    reply = client_with(FakeSpace(error=ConnectionError("asleep"))).chat("My baby cannot drink or breastfeed")
    assert reply["safety_level"] == "urgent" and reply["source"] == "safety_rule"


@pytest.mark.parametrize("question", ["What should my grandma eat?", "Sogokuru yarya iki?"])
def test_questions_about_adults_only_are_declined_here_without_the_space(api, question):
    space = FakeSpace(error=AssertionError("an off-scope question must not use the Space's GPU"))
    reply = client_with(space).chat(question)
    assert space.calls == []
    expected = api.post("/chat", json={"question": question}).json()
    assert (reply["answer"], reply["source"]) == (expected["answer"], expected["source"])
    assert reply["source"] == "out_of_scope"


def test_errors_from_the_space_become_api_errors():
    with pytest.raises(ApiError) as error:
        client_with(FakeSpace({"error": "Please type a question.", "status": 422})).chat("")
    assert error.value.message == "Please type a question." and error.value.status == 422


def test_a_sleeping_or_unreachable_space_gives_a_friendly_message():
    with pytest.raises(ApiError, match=WAKING_UP):
        client_with(FakeSpace(error=ConnectionError("timed out"))).chat("What should my baby eat?")


@pytest.mark.parametrize("measurements", [
    dict(age_months=12, sex="male", weight_kg=7.0, height_cm=72.0, muac_cm=12.0, oedema=False),   # moderate
    dict(age_months=24, sex="female", weight_kg=11.5, height_cm=86.0, muac_cm=14.5, oedema=False),  # normal
    dict(age_months=18, sex="female", weight_kg=8.0, height_cm=None, muac_cm=11.0, oedema=False),  # severe
])
def test_growth_check_matches_the_api(api, measurements):
    for language in ("en", "rw"):
        expected = api.post("/screening", json={**measurements, "breastfed": True, "language": language}).json()
        assert client_with(FakeSpace()).screening(**measurements, breastfed=True, language=language) == expected


def test_meal_plan_and_foods_match_the_api(api):
    request = dict(age_months=9, days=7, breastfed=True, language="rw", available=None, excluded=["egg"])
    assert client_with(FakeSpace()).meal_plan(**request) == api.post("/meal-plan", json=request).json()
    assert client_with(FakeSpace()).foods() == api.get("/foods").json()


def test_growth_check_input_errors_are_shown_in_the_chosen_language(api):
    bad = dict(age_months=12, sex="male", weight_kg=0.5, height_cm=None, muac_cm=None, oedema=False,
               breastfed=True, language="rw")
    expected = api.post("/screening", json=bad).json()["detail"]
    with pytest.raises(ApiError) as error:
        client_with(FakeSpace()).screening(**bad)
    assert error.value.message == expected


def test_the_space_is_chosen_only_when_it_is_configured(monkeypatch):
    monkeypatch.delenv("NUTRIASSIST_SPACE", raising=False)
    assert isinstance(make_client(), NutriAssistClient)
    monkeypatch.setenv("NUTRIASSIST_SPACE", "pauline-ish/nutriAssist_Rw")
    client = make_client()
    assert isinstance(client, SpaceClient)
    assert client.base_url == "https://huggingface.co/spaces/pauline-ish/nutriAssist_Rw"
