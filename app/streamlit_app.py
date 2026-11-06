"""NutriAssist-RW web app (Streamlit frontend). It talks to the FastAPI backend over HTTP.

Run:  streamlit run app/streamlit_app.py
The API must be running (``uvicorn nutriassist.api.app:app``); set NUTRIASSIST_API_URL if it is not
at http://localhost:8000.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))  # lets the pages import api_client and i18n

import streamlit as st  # noqa: E402

from api_client import ApiError, NutriAssistClient  # noqa: E402
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
        return NutriAssistClient(base_url).health()
    except ApiError:
        return None


@st.cache_resource(show_spinner=False)
def chw_directory() -> DemoChwDirectory:
    return DemoChwDirectory()


def sign_in_page() -> None:
    """Stops the page until a CHW signs in (see app/chw_login.py)."""
    st.title(f"🔐 {t('login_title')}")
    st.markdown(t("login_intro"))
    st.caption(t("login_demo_note"))
    if st.session_state.get("login_attempts", 0) >= MAX_ATTEMPTS:
        st.error(f"⚠️ {t('login_locked')}")
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
            st.error(f"⚠️ {t('login_failed')}")
        else:
            st.session_state.chw_id = chw.chw_id
            st.session_state.pop("login_attempts", None)
            st.rerun()
    st.stop()


def sign_out() -> None:
    for key in ("chw_id", "disclaimer_accepted", "messages", "screening"):
        st.session_state.pop(key, None)


with st.sidebar:
    st.title("🥣 NutriAssist-RW")
    st.caption(t("tagline"))
    st.radio(t("language"), list(LANGUAGES), key="language_choice", horizontal=True, on_change=change_language)

    status = server_status(NutriAssistClient().base_url)
    if status is None:
        st.error(f"● {t('server_down')}")
    else:
        st.success(f"● {t('server_ok')}")
        if status["demo_mode"]:
            st.warning(t("demo_mode"))
    st.info(f"🚑 {t('emergency')}")
    if login_required() and st.session_state.get("chw_id"):
        st.caption(f"👤 {t('signed_in_as')} **{st.session_state.chw_id}**")
        st.button(t("logout"), icon="🚪", on_click=sign_out, use_container_width=True)

if login_required() and not st.session_state.get("chw_id"):
    sign_in_page()

if not st.session_state.get("disclaimer_accepted"):
    st.title(f"⚠️ {t('disclaimer_title')}")
    st.markdown(t("disclaimer"))
    if st.button(t("disclaimer_accept"), type="primary", use_container_width=True):
        st.session_state.disclaimer_accepted = True
        st.rerun()
    st.stop()

navigation = st.navigation([
    st.Page("views/chat.py", title=t("page_chat"), icon="💬", default=True),
    st.Page("views/screening.py", title=t("page_screening"), icon="📏"),
    st.Page("views/meal_planner.py", title=t("page_planner"), icon="🍲"),
    st.Page("views/about.py", title=t("page_about"), icon="ℹ️"),
])
navigation.run()
