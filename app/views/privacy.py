"""Privacy policy and terms of use. Each promise on this page is kept by code: the consent record
(app/consent.py), nothing saved about the child (app/views/screening.py), sign-out clearing the session
(app/streamlit_app.py) and the 90-day limit on unanswered questions (src/nutriassist/api/app.py)."""

import streamlit as st

from i18n import language, t
from texts import PRIVACY

st.title(t("page_privacy"))
st.markdown(PRIVACY[language()])
