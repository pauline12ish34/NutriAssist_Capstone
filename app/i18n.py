"""Interface text in English and Kinyarwanda."""

from __future__ import annotations

import streamlit as st

from texts import TEXT


def t(key: str) -> str:
    """Text for ``key`` in the language chosen in the sidebar."""
    return TEXT[key][st.session_state.get("language", "en")]


def language() -> str:
    return st.session_state.get("language", "en")
