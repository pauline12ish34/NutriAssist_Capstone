"""Meal planner page: a 1- or 7-day plan from local foods for a child aged 6-59 months."""

import pandas as pd
import streamlit as st

from api_client import ApiError, NutriAssistClient
from i18n import language, t

NUTRIENTS = ("energy_kcal", "protein_g", "iron_mg", "calcium_mg")
client = NutriAssistClient()


@st.cache_data(ttl=3600, show_spinner=False)
def load_foods(base_url: str) -> list[dict]:
    return NutriAssistClient(base_url).foods()


def food_label(foods: dict[str, dict]):
    name = "name_rw" if language() == "rw" else "name_en"
    return lambda key: foods[key][name]


def plan_as_text(plan: dict) -> str:
    lines = [f"NutriAssist-RW - {t('page_planner')} ({plan['age_months']} months)", ""]
    for day in plan["days"]:
        lines.append(f"{t('day')} {day['day']}")
        for meal in day["meals"]:
            foods = "; ".join(f"{f['name']} - {f['household_measure']} ({f['grams']} g)" for f in meal["foods"])
            lines.append(f"  {meal['meal']}: {foods}")
        lines.append("")
    lines += [f"{t('tips')}:"] + [f"- {tip}" for tip in plan["tips"]]
    return "\n".join(lines)


def show_day(day: dict) -> None:
    for meal in day["meals"]:
        st.markdown(f"**{meal['meal']}**")
        table = pd.DataFrame(meal["foods"])[["name", "household_measure", "grams"]]
        table.columns = [t("food"), t("amount"), t("grams")]
        st.dataframe(table, hide_index=True, use_container_width=True)

    st.markdown(f"**{t('coverage')}**")
    columns = st.columns(len(NUTRIENTS))
    for column, nutrient in zip(columns, NUTRIENTS):
        percent = day["coverage_pct"][nutrient]
        column.metric(t(nutrient), f"{percent}%")
        column.progress(min(percent, 100) / 100)

    groups = day["dietary_diversity"]
    verdict = t("diversity_ok") if day["meets_min_diversity"] else t("diversity_low")
    st.markdown(f"**{t('diversity')}: {groups}/8** ({verdict})")
    st.caption(", ".join(day["food_groups"]))


st.title(f"🍲 {t('page_planner')}")
st.caption(t("planner_intro"))

try:
    foods = {food["key"]: food for food in load_foods(client.base_url)}
except ApiError as error:
    st.error(error.message)
    st.stop()

with st.form("meal_plan_form"):
    age = st.slider(t("age"), min_value=6, max_value=59, value=12, help=t("age_help"))
    breastfed = st.checkbox(t("breastfed"), value=True)
    days = 7 if st.radio(t("days"), [t("one_day"), t("one_week")], horizontal=True) == t("one_week") else 1
    available = st.multiselect(t("only_these"), list(foods), format_func=food_label(foods))
    excluded = st.multiselect(t("exclude"), list(foods), format_func=food_label(foods))
    submitted = st.form_submit_button(t("make_plan"), type="primary", use_container_width=True)

if submitted:
    try:
        st.session_state.meal_plan = client.meal_plan(age, days, breastfed, language(),
                                                 available=available or None, excluded=excluded)
    except ApiError as error:
        st.error(error.message)
        st.session_state.pop("meal_plan", None)

plan = st.session_state.get("meal_plan")
if plan:
    if plan["unfilled_slots"]:
        missing = "".join(f"\n- {t('slot_' + slot)}" for slot in plan["unfilled_slots"])
        st.warning(f"{t('missing_slots')}:{missing}")
    if len(plan["days"]) == 1:
        show_day(plan["days"][0])
    else:
        for tab, day in zip(st.tabs([f"{t('day')} {d['day']}" for d in plan["days"]]), plan["days"]):
            with tab:
                show_day(day)

    st.subheader(f"💡 {t('tips')}")
    for tip in plan["tips"]:
        st.markdown(f"- {tip}")
    st.download_button(t("download"), plan_as_text(plan), file_name="nutriassist_meal_plan.txt", icon="⬇️")
