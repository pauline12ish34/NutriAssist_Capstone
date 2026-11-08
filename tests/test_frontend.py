"""End-to-end tests: the Streamlit pages talking to a real API server over HTTP.

The API runs in a background thread with a scripted model; Streamlit's AppTest drives
the pages the way a user would (typing, clicking, switching language and page).
"""

import os
import socket
import sys
import threading
import time
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
uvicorn = pytest.importorskip("uvicorn")
from streamlit.testing.v1 import AppTest  # noqa: E402

from nutriassist.api.app import create_app  # noqa: E402
from nutriassist.inference.scripted import ScriptedChatModel  # noqa: E402

APP = str(Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py")
pytestmark = pytest.mark.integration


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module", autouse=True)
def api_server():
    port = _free_port()
    model = ScriptedChatModel(lambda q: "Give mashed beans with avocado and a little oil.")
    server = uvicorn.Server(uvicorn.Config(create_app(model=model), port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    os.environ["NUTRIASSIST_API_URL"] = f"http://127.0.0.1:{port}"
    os.environ["NUTRIASSIST_LOGIN"] = "off"   # the sign-in page has its own tests below
    sys.modules.pop("api_client", None)  # re-read the URL
    yield
    server.should_exit = True
    thread.join(timeout=5)


def start_app() -> AppTest:
    """The app, past the disclaimer shown on first use."""
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    at.button[0].click().run()
    return at


def test_disclaimer_comes_before_the_chat():
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert at.title[0].value == "Before you start"
    assert "912" in at.markdown[0].value and not at.chat_input
    at.button[0].click().run()
    assert at.title[0].value == "Ask a question"


def test_sidebar_shows_the_server_is_online():
    at = start_app()
    assert "online" in at.sidebar.success[0].value
    assert "912" in at.sidebar.info[0].value


def test_example_question_gets_an_answer():
    at = start_app()
    at.button[0].click().run()
    messages = at.chat_message
    assert [m.name for m in messages] == ["user", "assistant"]
    assert "mashed beans" in messages[1].markdown[0].value


def test_danger_sign_in_kinyarwanda_shows_the_urgent_alert():
    at = start_app()
    at.chat_input[0].set_value("Umwana wanjye aragagara").run()
    assert at.chat_message[-1].error[0].value == "**Danger sign detected**"
    assert "kigo nderabuzima" in at.chat_message[-1].markdown[0].value


def test_switching_to_kinyarwanda_translates_the_interface():
    at = start_app()
    at.sidebar.radio[0].set_value("Kinyarwanda").run()
    assert at.title[0].value == "Baza ikibazo"


def test_week_plan_in_kinyarwanda_has_seven_days():
    at = start_app()
    at.sidebar.radio[0].set_value("Kinyarwanda").run()
    at.switch_page("views/meal_planner.py").run()
    at.slider[0].set_value(9)
    at.radio[0].set_value("iminsi 7")
    at.button[0].click().run()
    assert not at.exception
    assert len(at.tabs) == 7
    assert at.metric[0].label == "Ingufu"


def test_plan_with_few_foods_explains_what_is_missing():
    at = start_app()
    at.switch_page("views/meal_planner.py").run()
    at.multiselect[0].set_value(["maize_flour", "beans", "banana"])
    at.button[0].click().run()
    assert not at.exception
    assert "could not be filled" in at.warning[0].value
    assert "a vegetable" in at.warning[0].value


def test_growth_check_red_muac_says_go_to_the_health_centre():
    at = start_app()
    at.switch_page("views/screening.py").run()
    at.number_input[0].set_value(18)
    at.radio[0].set_value("male")
    at.number_input[1].set_value(8.0)
    at.number_input[2].set_value(78.0)
    at.number_input[3].set_value(11.0)
    at.button[0].click().run()
    assert not at.exception
    assert "severe acute malnutrition" in at.error[0].value and "912" in at.error[0].value


def test_growth_check_normal_child_gets_a_meal_plan():
    at = start_app()
    at.switch_page("views/screening.py").run()
    at.number_input[0].set_value(24)
    at.radio[0].set_value("female")
    at.number_input[1].set_value(11.5)
    at.number_input[2].set_value(86.0)
    at.number_input[3].set_value(14.5)
    at.button[0].click().run()
    assert not at.exception
    assert "normal" in at.success[0].value
    assert at.metric[0].label == "Energy"


def test_growth_check_asks_for_the_sex():
    at = start_app()
    at.switch_page("views/screening.py").run()
    at.number_input[1].set_value(9.0)
    at.button[0].click().run()
    assert "boy or a girl" in at.error[0].value


def test_how_to_use_page_renders():
    at = start_app()
    at.switch_page("views/about.py").run()
    assert not at.exception
    assert "How to use it" in at.markdown[0].value


def test_sign_in_comes_first_when_login_is_on(monkeypatch):
    monkeypatch.setenv("NUTRIASSIST_LOGIN", "on")
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert at.title[0].value == "Sign in"
    assert not at.chat_input


def test_wrong_code_is_refused_without_saying_which_part_is_wrong(monkeypatch):
    monkeypatch.setenv("NUTRIASSIST_LOGIN", "on")
    at = AppTest.from_file(APP, default_timeout=30).run()
    for chw_id, code in (("CHW-DEMO-001", "000000"), ("CHW-FAKE-999", "123456"), ("CHW-DEMO-006", "123456")):
        at.text_input[0].set_value(chw_id)
        at.text_input[1].set_value(code)
        at.button[0].click().run()
        assert at.error[0].value == "The CHW ID or the code is not correct."
        assert at.title[0].value == "Sign in"


def test_too_many_wrong_attempts_lock_the_form(monkeypatch):
    monkeypatch.setenv("NUTRIASSIST_LOGIN", "on")
    at = AppTest.from_file(APP, default_timeout=30).run()
    for _ in range(5):
        at.text_input[0].set_value("CHW-DEMO-001")
        at.text_input[1].set_value("999999")
        at.button[0].click().run()
    assert "Too many wrong attempts" in at.error[0].value
    assert not at.text_input


def test_demo_chw_signs_in_and_out(monkeypatch):
    monkeypatch.setenv("NUTRIASSIST_LOGIN", "on")
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.text_input[0].set_value(" chw-demo-002 ")
    at.text_input[1].set_value("123456")
    at.button[0].click().run()
    assert at.title[0].value == "Before you start"
    assert "CHW-DEMO-002" in at.sidebar.caption[-1].value
    at.sidebar.button[0].click().run()
    assert at.title[0].value == "Sign in"
