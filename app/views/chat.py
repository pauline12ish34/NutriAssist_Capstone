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
    # Reviewed questions, so each example gets its approved answer (Kinyarwanda comes only from reviewed answers).
    "rw": [
        "Umwana w'amezi 9 akwiye kurya angana iki?",
        "Ni ibihe biryo byo mu Rwanda bikungahaye ku butare?",
        "Abagore batwite bakwiye kurya iki kugira ngo barinde abana babo imirire mibi?",
        "Nagaburira nte umwana urwaye?",
    ],
}

client = NutriAssistClient()
st.session_state.setdefault("messages", [])
st.session_state.setdefault("pending_question", None)   # a "Did you mean...?" button that was tapped

st.title(f"💬 {t('page_chat')}")
st.caption(t("chat_intro"))


def show_message(message: dict, index: int | None = None) -> None:
    avatar = "🧑🏾" if message["role"] == "user" else "🥣"
    with st.chat_message(message["role"], avatar=avatar):
        meta = message.get("meta")
        if meta and meta["safety_level"] == "urgent":
            st.error(f"**{t('urgent_banner')}**")
        elif meta and meta["safety_level"] == "medical":
            st.warning(t("medical_banner"))
        st.markdown(message["content"])
        if meta:
            if meta.get("translated"):
                st.info(t("machine_translated"))
            for n, suggestion in enumerate(meta.get("suggestions") or []):
                # Only the latest answer's suggestions can be tapped; older ones are shown as text.
                if index == len(st.session_state.messages) - 1:
                    if st.button(suggestion, key=f"suggestion-{index}-{n}", icon="❓", use_container_width=True):
                        st.session_state.pending_question = suggestion
                        st.rerun()
                else:
                    st.markdown(f"- {suggestion}")
            who = {"safety_rule": t("answered_by_rules"), "reviewed_answer": t("answered_by_reviewed"),
                   "no_reviewed_answer": t("answered_by_reviewed")}.get(meta["source"], meta["model"])
            st.caption(f"{who} · {meta['latency_ms'] / 1000:.1f} {t('seconds')}")


for i, message in enumerate(st.session_state.messages):
    show_message(message, i)

question = st.chat_input(t("chat_placeholder"))
if st.session_state.pending_question:
    question, st.session_state.pending_question = st.session_state.pending_question, None

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
