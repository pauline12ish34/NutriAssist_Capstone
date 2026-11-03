"""Shows one day of a meal plan; used by the meal planner and the growth check pages."""

import pandas as pd
import streamlit as st

from i18n import t

NUTRIENTS = ("energy_kcal", "protein_g", "iron_mg", "calcium_mg")


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
