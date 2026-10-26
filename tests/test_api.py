"""Integration tests: HTTP requests through FastAPI, the safety layer, the planner and a scripted model."""

import json

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from nutriassist.api.app import create_app  # noqa: E402
from nutriassist.api.settings import Settings, build_chat_model, find_model_file  # noqa: E402
from nutriassist.inference.scripted import ScriptedChatModel  # noqa: E402


@pytest.fixture
def model():
    return ScriptedChatModel(lambda q: "Give mashed beans with avocado.")


@pytest.fixture
def client(model):
    with TestClient(create_app(model=model)) as test_client:
        yield test_client


class TestChat:
    def test_answers_an_ordinary_question_with_the_model(self, client, model):
        response = client.post("/chat", json={"question": "What can my 9-month-old eat?"})
        assert response.status_code == 200
        body = response.json()
        assert body["answer"] == "Give mashed beans with avocado."
        assert (body["language"], body["safety_level"], body["source"]) == ("en", "none", "model")
        assert model.calls == ["What can my 9-month-old eat?"]
        assert float(response.headers["X-Process-Time-ms"]) >= 0

    def test_danger_sign_is_answered_by_the_safety_rules(self, client, model):
        body = client.post("/chat", json={"question": "Umwana wanjye aragagara"}).json()
        assert body["source"] == "safety_rule" and body["safety_level"] == "urgent"
        assert body["language"] == "rw" and "912" in body["answer"]
        assert model.calls == []

    @pytest.mark.parametrize("payload", [{}, {"question": ""}, {"question": "x" * 1001}, {"question": 5}])
    def test_invalid_input_is_rejected_with_422(self, client, payload):
        assert client.post("/chat", json=payload).status_code == 422

    def test_whitespace_only_question_is_rejected(self, client):
        response = client.post("/chat", json={"question": "    "})
        assert response.status_code == 422
        assert response.json()["detail"] == "Please type a question."

    def test_model_failure_returns_503(self):
        def broken(question):
            raise RuntimeError("out of memory")

        with TestClient(create_app(model=ScriptedChatModel(broken))) as client:
            response = client.post("/chat", json={"question": "What is porridge?"})
        assert response.status_code == 503
        assert "not available" in response.json()["detail"]


class TestMealPlan:
    def test_returns_a_plan_in_the_requested_language(self, client):
        response = client.post("/meal-plan", json={"age_months": 12, "days": 2, "language": "rw"})
        assert response.status_code == 200
        plan = response.json()
        assert len(plan["days"]) == 2
        assert plan["days"][0]["meals"][0]["meal"] == "Mu gitondo"
        assert plan["days"][0]["meets_min_diversity"]

    def test_respects_excluded_foods(self, client):
        plan = client.post("/meal-plan", json={"age_months": 18, "days": 7, "excluded": ["egg"]}).json()
        assert "egg" not in {f["food"] for d in plan["days"] for m in d["meals"] for f in m["foods"]}

    @pytest.mark.parametrize("payload", [
        {"age_months": 3}, {"age_months": 60}, {"age_months": 12, "days": 8},
        {"age_months": 12, "language": "fr"}, {"age_months": 12, "excluded": ["pizza"]},
    ])
    def test_invalid_requests_are_rejected(self, client, payload):
        response = client.post("/meal-plan", json=payload)
        assert response.status_code == 422


def test_foods_lists_the_catalogue(client):
    foods = client.get("/foods").json()
    assert len(foods) >= 30
    assert {"key", "name_en", "name_rw", "group", "min_age_months"} <= set(foods[0])


def test_health_reports_the_model(client):
    assert client.get("/health").json() == {"status": "ok", "model": "scripted", "demo_mode": False,
                                            "version": "0.1.0"}


def test_swagger_documentation_is_served(client):
    assert client.get("/docs").status_code == 200
    assert "/meal-plan" in client.get("/openapi.json").json()["paths"]


class TestSettings:
    def test_without_a_model_file_the_api_starts_in_demo_mode(self, tmp_path):
        model, demo = build_chat_model(Settings(model_path=tmp_path / "missing.gguf"))
        assert demo and "Demo mode" in model.generate([{"role": "user", "content": "Hi"}])

    def test_demo_answers_follow_the_question_language(self):
        model, _ = build_chat_model(Settings(backend="demo"))
        assert "igerageza" in model.generate([{"role": "user", "content": "Umwana yarya iki?"}])

    def test_llamacpp_backend_requires_the_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            build_chat_model(Settings(backend="llamacpp", model_path=tmp_path / "missing.gguf"))

    def test_unknown_backend_is_rejected(self):
        with pytest.raises(ValueError):
            build_chat_model(Settings(backend="gpu-cluster"))

    def test_reads_environment_variables(self, monkeypatch):
        monkeypatch.setenv("NUTRIASSIST_MODEL_PATH", "elsewhere/model.gguf")
        monkeypatch.setenv("NUTRIASSIST_MAX_NEW_TOKENS", "128")
        settings = Settings.from_env()
        assert str(settings.model_path).replace("\\", "/") == "elsewhere/model.gguf"
        assert settings.max_new_tokens == 128 and settings.backend == "auto"


def test_model_file_discovery_prefers_the_smaller_export(tmp_path):
    q4, q8 = tmp_path / "nutriassist-rw-q4_k_m.gguf", tmp_path / "nutriassist-rw-q8_0.gguf"
    assert find_model_file((q4, q8)) == q4                 # nothing yet: the preferred name
    q8.touch()
    assert find_model_file((q4, q8)) == q8                 # only the 8-bit file was downloaded
    q4.touch()
    assert find_model_file((q4, q8)) == q4


class TestReviewedKinyarwanda:
    @pytest.fixture
    def client_and_log(self, model, tmp_path):
        from nutriassist.knowledge import KnowledgeBase

        log = tmp_path / "unanswered.jsonl"
        app = create_app(model=model, knowledge=KnowledgeBase.load(), reviewed_only=frozenset({"rw"}), unanswered_log=log)
        with TestClient(app) as test_client:
            yield test_client, log

    def test_reviewed_answer_for_a_known_question(self, client_and_log, model):
        client, log = client_and_log
        body = client.post("/chat", json={"question": "Nagaburira nte umwana urwaye?"}).json()
        assert body["source"] == "reviewed_answer" and body["suggestions"] == [] and model.calls == []
        assert not log.exists()

    def test_unknown_question_returns_suggestions_and_is_logged(self, client_and_log, model):
        client, log = client_and_log
        body = client.post("/chat", json={"question": "Nakongera nte ubutare mu biryo by'umwana?"}).json()
        assert body["source"] == "no_reviewed_answer" and body["suggestions"] and model.calls == []
        logged = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
        assert logged["question"] == "Nakongera nte ubutare mu biryo by'umwana?" and logged["language"] == "rw"
        assert set(logged) == {"time", "language", "question", "suggested"}


def test_kinyarwanda_mode_must_be_known():
    from nutriassist.api.settings import reviewed_only_languages

    with pytest.raises(ValueError):
        reviewed_only_languages(Settings(kinyarwanda="google"), None)
    assert reviewed_only_languages(Settings(), None) == frozenset()          # no reviewed answers: model answers
    assert reviewed_only_languages(Settings(kinyarwanda="model"), object()) == frozenset()
