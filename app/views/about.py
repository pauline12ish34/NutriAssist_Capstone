"""How-to-use page: what the assistant does, how to use it, and its limits."""

import streamlit as st

from i18n import language, t
from texts import ABOUT

st.title(f"ℹ️ {t('page_about')}")
st.markdown(ABOUT[language()])
