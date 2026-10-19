import numpy as np
import pandas as pd
import pytest

from nutriassist.food_data.clean_nutrients import (
    SHIFT_CHAIN,
    basis_confidence,
    clean_sheet,
    correct_column_shift,
    estimate_serving_mass,
    source_column,
    value_quality,
)

# Banana (one extra-large fruit) as it appears in the workbook: every value from
# vitamin_b1 onward holds the true value of the column before it.
SHIFTED_BANANA = {
    "food": "banana", "caloric_value": 134, "water": 112.4, "protein": 1.6, "fat": 0.5,
    "carbohydrates": 34.3, "vitamin_a": 0.0, "vitamin_b1": 0.0, "vitamin_b11": 0.085,
    "vitamin_b12": 0.045, "vitamin_b2": 0.0, "vitamin_b3": 0.1, "vitamin_b5": 1.0,
    "vitamin_b6": 0.5, "vitamin_c": 0.6, "vitamin_d": 13.1, "vitamin_e": 0.0, "vitamin_k": 0.2,
    "calcium": 0.035, "copper": 7.5, "iron": 0.1, "magnesium": 0.4, "manganese": 40.5,
    "phosphorus": 0.4, "potassium": 33.0, "selenium": 537.0, "zinc": 0.049,
}

# Raw spinach (one cup) is stored correctly and must not be touched.
CLEAN_SPINACH = {
    "food": "spinach raw", "caloric_value": 7, "water": 27.4, "protein": 0.9, "fat": 0.1,
    "carbohydrates": 1.1, "vitamin_a": 0.0, "vitamin_b1": 0.045, "vitamin_b11": 0.064,
    "vitamin_b12": 0.0, "vitamin_b2": 0.024, "vitamin_b3": 0.2, "vitamin_b5": 0.063,
    "vitamin_b6": 0.094, "vitamin_c": 8.4, "vitamin_d": 0.0, "vitamin_e": 0.6, "vitamin_k": 0.1,
    "calcium": 29.7, "copper": 0.042, "iron": 0.8, "magnesium": 23.7, "manganese": 0.3,
    "phosphorus": 14.7, "potassium": 167.4, "selenium": 0.078, "zinc": 0.2,
}

# Oysters are genuinely rich in copper: one signal only, so no correction.
CLEAN_OYSTER = {**CLEAN_SPINACH, "food": "oyster canned", "copper": 7.2, "potassium": 371.0}


def _frame(*rows: dict) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


def test_shifted_row_is_restored_to_usda_values() -> None:
    corrected, shifted = correct_column_shift(_frame(SHIFTED_BANANA))
    row = corrected.iloc[0]

    assert shifted.tolist() == [True]
    # USDA, extra-large banana (152 g): K 544 mg, Mg 41 mg, Ca 7.6 mg, vit C 13.2 mg
    assert row["potassium"] == 537.0
    assert row["magnesium"] == 40.5
    assert row["calcium"] == 7.5
    assert row["vitamin_c"] == 13.1
    assert np.isnan(row["zinc"])


def test_clean_rows_are_left_alone() -> None:
    frame = _frame(CLEAN_SPINACH, CLEAN_OYSTER)
    corrected, shifted = correct_column_shift(frame)

    assert shifted.tolist() == [False, False]
    pd.testing.assert_frame_equal(corrected, frame)


def test_serving_mass_sums_water_and_macronutrients() -> None:
    mass = estimate_serving_mass(_frame(SHIFTED_BANANA, {**CLEAN_SPINACH, "water": 0, "protein": 0, "fat": 0, "carbohydrates": 0}))
    assert mass.iloc[0] == pytest.approx(148.8)
    assert np.isnan(mass.iloc[1])


def test_flags_and_confidence() -> None:
    tiny = {**CLEAN_SPINACH, "food": "salt pinch", "water": 1.0, "protein": 0.0, "fat": 0.0, "carbohydrates": 0.0, "caloric_value": 0}
    impossible = {**CLEAN_SPINACH, "food": "dense", "caloric_value": 500, "water": 0.0, "protein": 0.0, "fat": 10.0, "carbohydrates": 0.0}
    cleaned = clean_sheet(_frame(SHIFTED_BANANA, CLEAN_SPINACH, CLEAN_OYSTER, tiny, impossible))

    assert cleaned["quality_flags"].iloc[0] == "micronutrient_shift_corrected"
    assert cleaned["quality_flags"].iloc[1] == ""
    assert cleaned["quality_flags"].iloc[2] == "possible_column_shift"
    assert "tiny_serving" in cleaned["quality_flags"].iloc[3]
    assert "impossible_energy_density" in cleaned["quality_flags"].iloc[4]
    assert cleaned["basis_confidence"].tolist() == ["high", "high", "high", "low", "low"]
    assert basis_confidence("serving_mass_unknown") == "unusable"


def test_value_quality_labels() -> None:
    assert value_quality("zinc", 0.2, shifted=True) == "lost_in_shift"
    assert value_quality("iron", 0.0, shifted=False) == "zero_or_missing"
    assert value_quality("vitamin_b12", 0.092, shifted=False) == "below_precision"
    assert value_quality("iron", 0.8, shifted=False) == "ok"


def test_source_column_points_at_the_workbook_cell_used() -> None:
    assert source_column("potassium", shifted=True) == "selenium"
    assert source_column("potassium", shifted=False) == "potassium"
    assert source_column("zinc", shifted=True) == "zinc"
    assert source_column("protein", shifted=True) == "protein"
    assert SHIFT_CHAIN[-1] == "zinc"
