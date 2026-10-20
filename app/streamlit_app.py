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

navigation = st.navigation([
    st.Page("views/chat.py", title=t("page_chat"), icon="💬", default=True),
    st.Page("views/meal_planner.py", title=t("page_planner"), icon="🍲"),
    st.Page("views/about.py", title=t("page_about"), icon="ℹ️"),
])
navigation.run()
