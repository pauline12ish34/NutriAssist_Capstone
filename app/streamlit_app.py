"""NutriAssist-RW web app (Streamlit frontend).

Run:  streamlit run app/streamlit_app.py
Two backends (api_client.make_client):
- the FastAPI server (``uvicorn nutriassist.api.app:app``), on your computer or in Docker; set
  NUTRIASSIST_API_URL if it is not at http://localhost:8000;
- on Streamlit Community Cloud, the ZeroGPU Space for chat (set NUTRIASSIST_SPACE), with the growth check and
  meal planner running in this app (app/space_client.py).
"""

import os
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_DIR))  # lets the pages import api_client and i18n
sys.path.insert(1, str(APP_DIR.parent / "src"))  # the nutriassist package, when it is not pip-installed

import streamlit as st  # noqa: E402

# On Streamlit Community Cloud the settings are secrets; the app reads them as environment variables.
SECRET_SETTINGS = ("NUTRIASSIST_SPACE", "NUTRIASSIST_API_TOKEN", "HF_TOKEN", "NUTRIASSIST_LOGIN",
                   "NUTRIASSIST_DEMO_CODE", "NUTRIASSIST_API_URL")
try:
    for _name in SECRET_SETTINGS:
        if _name in st.secrets and not os.environ.get(_name):
            os.environ[_name] = str(st.secrets[_name])
except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):   # no secrets file: fine on your computer
    pass

from api_client import ApiError, make_client  # noqa: E402
from chw_login import MAX_ATTEMPTS, DemoChwDirectory, login_required, sign_in  # noqa: E402
from i18n import t  # noqa: E402

st.set_page_config(page_title="NutriAssist-RW", page_icon="🥣", layout="centered")
LANGUAGES = {"English": "en", "Kinyarwanda": "rw"}
st.session_state.setdefault("language", "en")


def change_language() -> None:
    # Runs before the rerun, so every piece of text on the page switches together.
    st.session_state.language = LANGUAGES[st.session_state.language_choice]


@st.cache_data(ttl=30, show_spinner=False)
def server_status(base_url: str) -> dict | None:
    try:
        return make_client().health()
    except ApiError:
        return None


@st.cache_resource(show_spinner=False)
def chw_directory() -> DemoChwDirectory:
    return DemoChwDirectory()


def sign_in_page() -> None:
    """Stops the page until a CHW signs in (see app/chw_login.py)."""
    st.title(t("login_title"))
    st.markdown(t("login_intro"))
    st.caption(t("login_demo_note"))
    if st.session_state.get("login_attempts", 0) >= MAX_ATTEMPTS:
        st.error(t("login_locked"), icon=":material/lock:")
        st.stop()
    with st.form("sign_in"):
        chw_id = st.text_input(t("login_id"), placeholder="CHW-DEMO-001", max_chars=20)
        code = st.text_input(t("login_code"), type="password", max_chars=12)
        submitted = st.form_submit_button(t("login_button"), type="primary", use_container_width=True)
    if submitted:
        chw = sign_in(chw_directory(), chw_id, code)
        if chw is None:
            st.session_state.login_attempts = st.session_state.get("login_attempts", 0) + 1
            if st.session_state.login_attempts >= MAX_ATTEMPTS:
                st.rerun()   # show the lock message instead of the form
            st.error(t("login_failed"), icon=":material/error:")
        else:
            st.session_state.chw_id = chw.chw_id
            st.session_state.pop("login_attempts", None)
            st.rerun()
    st.stop()


def sign_out() -> None:
    for key in ("chw_id", "disclaimer_accepted", "messages", "screening"):
        st.session_state.pop(key, None)


with st.sidebar:
    st.title("NutriAssist-RW")
    st.caption(t("tagline"))
    st.radio(t("language"), list(LANGUAGES), key="language_choice", horizontal=True, on_change=change_language)

    status = server_status(make_client().base_url)
    if status is None:
        st.error(t("server_down"), icon=":material/cloud_off:")
    else:
        st.success(t("server_ok"), icon=":material/check_circle:")
        if status["demo_mode"]:
            st.warning(t("demo_mode"))
    st.info(t("emergency"), icon="🚑")
    if login_required() and st.session_state.get("chw_id"):
        st.caption(f":material/person: {t('signed_in_as')} **{st.session_state.chw_id}**")
        st.button(t("logout"), icon=":material/logout:", on_click=sign_out, use_container_width=True)

if login_required() and not st.session_state.get("chw_id"):
    sign_in_page()

if not st.session_state.get("disclaimer_accepted"):
    st.title(t("disclaimer_title"))
    st.markdown(t("disclaimer"))
    if st.button(t("disclaimer_accept"), type="primary", use_container_width=True):
        st.session_state.disclaimer_accepted = True
        st.rerun()
    st.stop()

navigation = st.navigation([
    st.Page("views/chat.py", title=t("page_chat"), icon=":material/chat:", default=True),
    st.Page("views/screening.py", title=t("page_screening"), icon=":material/monitor_weight:"),
    st.Page("views/meal_planner.py", title=t("page_planner"), icon=":material/restaurant:"),
    st.Page("views/about.py", title=t("page_about"), icon=":material/info:"),
])
navigation.run()
