"""Locust load test for the live app: the ZeroGPU Space, called exactly as the hosted Streamlit app calls it.

On Streamlit Community Cloud, chat goes through ``app/space_client.SpaceClient`` to the Space's ``/chat_json``
endpoint (one shared Gradio connection for every visitor); the growth check and meal planner run inside
Streamlit and never reach the Space. So this test calls ``SpaceClient.chat`` and nothing else:

- ``Caregiver`` asks English questions the fine-tuned model must answer (the GPU path);
- ``UrgentCaregiver`` (always exactly one) reports a danger sign, answered by the safety rules on the Space.

The question: does the urgent answer stay fast while visitors keep the GPU busy?

**Every model answer uses ZeroGPU time from the account's daily quota.** Keep runs short and do not run this
just before a demo. Settings come from the environment or ``.env``: NUTRIASSIST_SPACE (e.g.
"pauline-ish/nutriAssist_Rw"), NUTRIASSIST_API_TOKEN (the Space's secret) and optionally HF_TOKEN.

A third user, ``StreamlitVisitor``, opens the hosted Streamlit app (NUTRIASSIST_WEB_APP, by default
https://nutriassistcapstone-v1.streamlit.app) to time the web front end itself.

Run with the web page (charts for screenshots at http://localhost:8089):
    python -m locust -f scripts/load_test/locustfile_space.py
"""

import os
import random
import sys
import time
from pathlib import Path

from locust import HttpUser, User, between, constant, task

# Locust patches the network with gevent, and the "truststore" certificate check of the Gradio client's HTTP
# library then recurses without end on every HTTPS connection (every chat failed as "starting up"). With a
# certificate file set, that library uses the file instead of truststore.
import certifi  # noqa: E402

os.environ.setdefault("SSL_CERT_FILE", certifi.where())

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "app")]

from space_client import SpaceClient  # noqa: E402

SETTINGS = ("NUTRIASSIST_SPACE", "NUTRIASSIST_API_TOKEN", "HF_TOKEN")
STREAMLIT_APP = os.environ.get("NUTRIASSIST_WEB_APP", "https://nutriassistcapstone-v1.streamlit.app")
# English questions with no reviewed answer, so the model writes each answer (as in locustfile.py).
MODEL_QUESTIONS = [
    "Can I give my child Irish potatoes?",
    "Is it fine to give my toddler cassava bread every day?",
    "How can I make porridge thicker for my 10 month old?",
    "Can I add sugar to my baby's porridge to make it tasty?",
]
DANGER_SIGNS = [
    "My child is having a seizure",
    "My baby cannot drink or breastfeed",
    "My child vomits everything",
]


def read_settings(env_file: Path = ROOT / ".env") -> None:
    """Fill missing settings from .env ("NAME=value" or "NAME = value"; commented lines are ignored)."""
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        name, _, value = line.partition("=")
        name = name.strip()
        if name in SETTINGS and value.strip() and not os.environ.get(name):
            os.environ[name] = value.strip().strip("'\"")


read_settings()
if not os.environ.get("NUTRIASSIST_SPACE"):
    raise SystemExit("Set NUTRIASSIST_SPACE (and NUTRIASSIST_API_TOKEN) in the environment or .env first.")


class SpaceVisitor(User):
    abstract = True

    def on_start(self):
        self.space = SpaceClient()   # the Gradio connection itself is shared, as in the Streamlit app

    def ask(self, question: str, name: str) -> None:
        start = time.perf_counter()
        error, reply = None, None
        try:
            reply = self.space.chat(question)
        except Exception as exc:   # ApiError: Space asleep, out of GPU time, token wrong, network
            error = exc
        self.environment.events.request.fire(
            request_type="SPACE", name=name, response_time=(time.perf_counter() - start) * 1000,
            response_length=len(str(reply or "")), exception=error, context={})


class Caregiver(SpaceVisitor):
    wait_time = between(1, 3)

    @task
    def ask_the_model(self):
        self.ask(random.choice(MODEL_QUESTIONS), "chat: model answer")


class UrgentCaregiver(SpaceVisitor):
    fixed_count = 1
    wait_time = constant(3)

    @task
    def report_a_danger_sign(self):
        self.ask(random.choice(DANGER_SIGNS), "chat: danger sign")


class StreamlitVisitor(HttpUser):
    """Opens the hosted Streamlit app. Its chat runs over a WebSocket, which Locust cannot drive, so the chat
    itself is measured by the users above, through the same call the app makes."""

    fixed_count = 1
    host = STREAMLIT_APP
    wait_time = between(2, 5)

    @task(3)
    def open_the_app(self):
        self.client.get("/", name="web app: open page", timeout=60)

    @task(1)
    def health(self):
        self.client.get("/_stcore/health", name="web app: health check", timeout=60)
