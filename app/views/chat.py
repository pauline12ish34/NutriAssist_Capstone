"""Chat page: ask a question, get an answer checked by the safety layer."""

import streamlit as st

from api_client import ApiError, NutriAssistClient
from i18n import language, t

EXAMPLES = {
    "en": [
        "What foods should I give my 8-month-old baby?",
        "How can I add more iron to my child's food?",
        "What should I eat while breastfeeding?",
        "My child has a fever, what should she eat?",
    ],
    "rw": [
        "Umwana w'amezi 9 yarya iki?",
        "Nakongera nte ubutare mu biryo by'umwana?",
        "Umugore utwite akwiye kurya iki?",
        "Umwana wanjye afite umuriro, namugaburira iki?",
    ],
}

client = NutriAssistClient()
st.session_state.setdefault("messages", [])

st.title(f"💬 {t('page_chat')}")
st.caption(t("chat_intro"))


def show_message(message: dict) -> None:
    avatar = "🧑🏾" if message["role"] == "user" else "🥣"
    with st.chat_message(message["role"], avatar=avatar):
        meta = message.get("meta")
        if meta and meta["safety_level"] == "urgent":
            st.error(f"**{t('urgent_banner')}**")
        elif meta and meta["safety_level"] == "medical":
            st.warning(t("medical_banner"))
        st.markdown(message["content"])
        if meta:
            who = t("answered_by_rules") if meta["source"] == "safety_rule" else meta["model"]
            st.caption(f"{who} · {meta['latency_ms'] / 1000:.1f} {t('seconds')}")


for message in st.session_state.messages:
    show_message(message)

question = st.chat_input(t("chat_placeholder"))

if not st.session_state.messages:
    st.write(f"**{t('examples')}**")
    columns = st.columns(2)
    for i, example in enumerate(EXAMPLES[language()]):
        if columns[i % 2].button(example, key=f"example-{i}", use_container_width=True):
            question = example

if question:
    user_message = {"role": "user", "content": question}
    st.session_state.messages.append(user_message)
    show_message(user_message)
    try:
        with st.spinner(t("thinking")):
            reply = client.chat(question)
    except ApiError as error:
        st.error(error.message)
    else:
        assistant_message = {"role": "assistant", "content": reply["answer"], "meta": reply}
        st.session_state.messages.append(assistant_message)
        st.rerun()

if st.session_state.messages and st.button(t("clear_chat"), icon="🗑️"):
    st.session_state.messages = []
    st.rerun()
