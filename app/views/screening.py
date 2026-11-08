"""Growth check page: malnutrition screening from the weight, MUAC and height that CHWs measure."""

import pandas as pd
import streamlit as st

from api_client import ApiError, make_client
from consent import AGREED, DECLINED, record_consent
from i18n import language, t
from plan_view import show_day

client = make_client()
BOX = {"severe": st.error, "moderate": st.warning, "check": st.info, "normal": st.success}

st.title(t("page_screening"))
st.caption(t("screening_intro"))


def new_child() -> None:
    """Forget the last child's result and consent: each child needs the caregiver's own agreement."""
    for key in ("screening", "consent"):
        st.session_state.pop(key, None)


# Consent first: the CHW reads the text to the caregiver and records the answer (app/consent.py).
if st.session_state.get("consent") != AGREED:
    st.subheader(t("consent_title"))
    st.info(t("consent_script"), icon=":material/record_voice_over:")
    agreed, declined = st.columns(2)
    if agreed.button(t("consent_agree"), type="primary", use_container_width=True):
        record_consent(AGREED, st.session_state.get("chw_id"), language())
        st.session_state.consent = AGREED
        st.rerun()
    if declined.button(t("consent_decline"), use_container_width=True):
        record_consent(DECLINED, st.session_state.get("chw_id"), language())
        st.session_state.consent = DECLINED
    if st.session_state.get("consent") == DECLINED:
        st.warning(t("consent_declined"), icon=":material/block:")
    st.stop()

with st.form("screening_form"):
    left, right = st.columns(2)
    age = left.number_input(t("s_age"), min_value=0, max_value=59, value=12, step=1)
    sex = right.radio(t("s_sex"), ["male", "female"], index=None, horizontal=True,
                      format_func=lambda s: t("boy") if s == "male" else t("girl"))
    weight = st.number_input(t("s_weight"), min_value=0.0, max_value=60.0, value=None, step=0.1, format="%.1f")
    left, right = st.columns(2)
    height = left.number_input(t("s_height"), min_value=0.0, max_value=150.0, value=None, step=0.1, format="%.1f",
                               help=t("s_height_help"))
    muac = right.number_input(t("s_muac"), min_value=0.0, max_value=30.0, value=None, step=0.1, format="%.1f",
                              help=t("s_muac_help"))
    oedema = st.checkbox(t("s_oedema"))
    breastfed = st.checkbox(t("breastfed"), value=True)
    submitted = st.form_submit_button(t("s_button"), type="primary", use_container_width=True)

if submitted:
    if sex is None:
        st.session_state.pop("screening", None)
        st.error(t("s_need_sex"), icon=":material/error:")
    elif weight is None:
        st.session_state.pop("screening", None)
        st.error(t("s_need_weight"), icon=":material/error:")
    else:
        try:
            st.session_state.screening = client.screening(int(age), sex, weight, height or None, muac or None,
                                                          oedema, breastfed, language())
        except ApiError as error:
            st.session_state.pop("screening", None)
            st.error(error.message, icon=":material/error:")

result = st.session_state.get("screening")
if result:
    BOX[result["level"]](f"### {result['title']}\n\n{result['advice']}")

    st.markdown(f"**{t('s_findings')}**")
    for finding in result["findings"] or [{"text": t("s_none")}]:
        st.markdown(f"- {finding['text']}")

    missing = t("s_not_measured")
    rows = [(t(f"z_{name}"), missing if z is None else f"{z:+.2f}") for name, z in result["z_scores"].items()]
    rows.append(("MUAC", missing if result["muac_cm"] is None else f"{result['muac_cm']} cm"))
    st.dataframe(pd.DataFrame(rows, columns=[t("s_measure"), t("s_result")]), hide_index=True,
                 use_container_width=True)
    for note in result["notes"]:
        st.caption(note)

    if result["tips"]:
        st.subheader(t("s_advice"))
        for tip in result["tips"]:
            st.markdown(f"- {tip}")

    plan = result.get("meal_plan")
    if plan:
        st.subheader(t("s_plan"))
        if plan["adjustments"]:
            st.info(f"**{t('adjusted_for')}:**" + "".join(f"\n- {a}" for a in plan["adjustments"]))
        show_day(plan["days"][0])
        for tip in plan["tips"]:
            st.markdown(f"- {tip}")

    st.button(t("consent_next_child"), icon=":material/person_add:", on_click=new_child, use_container_width=True)
