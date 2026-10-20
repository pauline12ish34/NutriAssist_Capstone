"""Local foods the planner can use, with nutrients per 100 g from the cleaned food table."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

PLANNER_FOODS = Path("data/reference/planner_foods.csv")
FOOD_NUTRIENTS = Path("data/processed/food_nutrients.csv")

# Cleaned-table nutrient names -> planner names. Only values flagged "ok" are used.
_NUTRIENT_COLUMNS = {
    "caloric_value": "energy_kcal",
    "protein": "protein_g",
    "iron": "iron_mg",
    "calcium": "calcium_mg",
    "vitamin_c": "vitamin_c_mg",
}

# The 8 food groups of WHO's minimum dietary diversity indicator (2017).
FOOD_GROUPS = {
    "breast_milk": ("breast milk", "amashereka"),
    "grains_roots": ("grains, roots and tubers", "ibinyampeke n'ibinyabijumba"),
    "legumes_nuts": ("beans, peas and nuts", "ibinyamisogwe n'ubunyobwa"),
    "dairy": ("milk products", "amata n'ibiyakomokaho"),
    "flesh_foods": ("meat and fish", "inyama n'amafi"),
    "eggs": ("eggs", "amagi"),
    "vitamin_a_fruit_veg": ("vitamin A-rich fruits and vegetables", "imbuto n'imboga bikungahaye kuri vitamini A"),
    "other_fruit_veg": ("other fruits and vegetables", "izindi mbuto n'imboga"),
}


@dataclass(frozen=True)
class Food:
    key: str
    name_en: str
    name_rw: str
    group: str
    slots: frozenset[str]
    portion_g: float                 # typical portion for a child aged 12-23 months
    unit: str                        # household measure: "tablespoon", "flour_spoon" or "egg"
    unit_g: float                    # grams in one unit
    min_age_months: int
    per_100g: dict[str, float]

    def name(self, language: str) -> str:
        return self.name_rw if language == "rw" else self.name_en

    def nutrients(self, grams: float) -> dict[str, float]:
        return {nutrient: value * grams / 100 for nutrient, value in self.per_100g.items()}


class FoodCatalogue:
    """The planner's foods, looked up by key or by meal slot."""

    def __init__(self, foods: list[Food]) -> None:
        self._foods = {food.key: food for food in foods}

    @classmethod
    def load(cls, foods_path: str | Path = PLANNER_FOODS, nutrients_path: str | Path = FOOD_NUTRIENTS) -> "FoodCatalogue":
        table = pd.read_csv(foods_path)
        nutrients = pd.read_csv(nutrients_path)
        nutrients = nutrients[nutrients["food_id"].isin(table["food_id"])
                              & (nutrients["value_quality"] == "ok")
                              & nutrients["nutrient_name"].isin(_NUTRIENT_COLUMNS)]
        per_100g = (nutrients.pivot_table(index="food_id", columns="nutrient_name", values="amount_per_100g")
                    .rename(columns=_NUTRIENT_COLUMNS))
        missing = sorted(set(table["food_id"]) - set(per_100g.index))
        if missing:
            raise ValueError(f"No nutrient values for planner foods {missing}")
        unknown_groups = sorted(set(table["group"]) - set(FOOD_GROUPS))
        if unknown_groups:
            raise ValueError(f"Unknown food groups {unknown_groups}")

        foods = [
            Food(
                key=row.key, name_en=row.name_en, name_rw=row.name_rw, group=row.group,
                slots=frozenset(row.slots.split(";")), portion_g=float(row.portion_g), unit=row.unit,
                unit_g=float(row.unit_g), min_age_months=int(row.min_age_months),
                per_100g=_nutrient_values(per_100g.loc[row.food_id]),
            )
            for row in table.itertuples()
        ]
        return cls(foods)

    def __len__(self) -> int:
        return len(self._foods)

    def __contains__(self, key: str) -> bool:
        return key in self._foods

    def __getitem__(self, key: str) -> Food:
        return self._foods[key]

    @property
    def keys(self) -> list[str]:
        return list(self._foods)

    def for_slot(self, slot: str) -> list[Food]:
        return [food for food in self._foods.values() if slot in food.slots]


def _nutrient_values(row: pd.Series) -> dict[str, float]:
    # A missing value counts as 0, so a plan never over-states a nutrient.
    return {n: float(row[n]) if n in row and pd.notna(row[n]) else 0.0 for n in _NUTRIENT_COLUMNS.values()}
