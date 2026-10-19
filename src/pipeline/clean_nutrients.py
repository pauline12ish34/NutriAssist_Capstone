"""Correct the workbook's serving basis, units and micronutrient column shift.

The workbook stores one *typical serving* per row (not 100 g), records sodium in
grams and several vitamins in milligrams, and in roughly 12% of rows the
micronutrient block is shifted one column to the right. The evidence behind each
rule is documented in ``docs/nutrient_cleaning.md``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Components whose grams add up to the serving weight. Ash (minerals, ~1-2% of
# most foods) is not in the workbook, so the estimate is slightly low.
MASS_COMPONENTS = ("water", "protein", "fat", "carbohydrates")

# Workbook column order of the block that shifts. In a shifted row, column i+1
# holds the true value of column i, and the true zinc value is lost.
SHIFT_CHAIN = (
    "vitamin_a",
    "vitamin_b1",
    "vitamin_b11",
    "vitamin_b12",
    "vitamin_b2",
    "vitamin_b3",
    "vitamin_b5",
    "vitamin_b6",
    "vitamin_c",
    "vitamin_d",
    "vitamin_e",
    "vitamin_k",
    "calcium",
    "copper",
    "iron",
    "magnesium",
    "manganese",
    "phosphorus",
    "potassium",
    "selenium",
    "zinc",
)

# nutrient -> (canonical unit, multiplier from the workbook's unit)
UNIT_CONVERSIONS: dict[str, tuple[str, float]] = {
    "caloric_value": ("kcal", 1.0),
    "fat": ("g", 1.0),
    "saturated_fats": ("g", 1.0),
    "monounsaturated_fats": ("g", 1.0),
    "polyunsaturated_fats": ("g", 1.0),
    "carbohydrates": ("g", 1.0),
    "sugars": ("g", 1.0),
    "protein": ("g", 1.0),
    "dietary_fiber": ("g", 1.0),
    "cholesterol": ("mg", 1.0),
    "sodium": ("mg", 1000.0),  # workbook: g
    "water": ("g", 1.0),
    "vitamin_a": ("mcg", 1000.0),  # workbook: mg
    "vitamin_b1": ("mg", 1.0),
    "vitamin_b11": ("mcg", 1000.0),  # folate; workbook: mg
    "vitamin_b12": ("mcg", 1000.0),  # workbook: mg
    "vitamin_b2": ("mg", 1.0),
    "vitamin_b3": ("mg", 1.0),
    "vitamin_b5": ("mg", 1.0),
    "vitamin_b6": ("mg", 1.0),
    "vitamin_c": ("mg", 1.0),
    "vitamin_d": ("mcg", 1000.0),  # workbook: mg
    "vitamin_e": ("mg", 1.0),
    "vitamin_k": ("mcg", 1000.0),  # workbook: mg
    "calcium": ("mg", 1.0),
    "copper": ("mg", 1.0),
    "iron": ("mg", 1.0),
    "magnesium": ("mg", 1.0),
    "manganese": ("mg", 1.0),
    "phosphorus": ("mg", 1.0),
    "potassium": ("mg", 1.0),
    "selenium": ("mcg", 1000.0),  # workbook: mg
    "zinc": ("mg", 1.0),
}

# Workbook values in (0, 0.1) are dominated by noise (e.g. cream cheese listing
# 0.092 mg of B12 per tablespoon), so they are kept but flagged.
PRECISION_FLOOR = 0.1
MIN_SERVING_G = 0.1  # below the workbook's 0.1 g resolution the weight is unknown
TINY_SERVING_G = 5.0
MAX_KCAL_PER_G = 9.1  # pure fat is ~9 kcal/g; anything denser is impossible
ATWATER_RANGE = (0.75, 1.33)
SHIFT_SIGNAL_THRESHOLD = 2

# Flags that make the per-100 g conversion untrustworthy for a food.
LOW_CONFIDENCE_FLAGS = {"tiny_serving", "impossible_energy_density", "energy_mismatch"}


def _column(frame: pd.DataFrame, name: str) -> pd.Series:
    if name in frame:
        return pd.to_numeric(frame[name], errors="coerce")
    return pd.Series(np.nan, index=frame.index)


def shift_signals(frame: pd.DataFrame) -> pd.Series:
    """Count implausible values that a one-column shift produces.

    A shifted row puts potassium under selenium, calcium under copper and
    magnesium under manganese. One signal alone can be real (oysters are rich
    in copper); two or more almost never are.
    """
    selenium_above_potassium = _column(frame, "selenium") > _column(frame, "potassium")
    copper_too_high = _column(frame, "copper") > 5
    manganese_too_high = _column(frame, "manganese") > 15
    return (
        selenium_above_potassium.astype(int)
        + copper_too_high.astype(int)
        + manganese_too_high.astype(int)
    )


def correct_column_shift(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Shift the micronutrient block back one column in rows that need it.

    Returns the corrected copy and a boolean mask of the corrected rows. The
    true zinc value of a corrected row is unrecoverable and becomes NaN.
    """
    corrected = frame.copy()
    if not all(column in frame for column in SHIFT_CHAIN):
        return corrected, pd.Series(False, index=frame.index)

    shifted = shift_signals(frame) >= SHIFT_SIGNAL_THRESHOLD
    for target, holder in zip(SHIFT_CHAIN[:-1], SHIFT_CHAIN[1:]):
        corrected.loc[shifted, target] = frame.loc[shifted, holder]
    corrected.loc[shifted, SHIFT_CHAIN[-1]] = np.nan
    return corrected, shifted


def source_column(nutrient: str, shifted: bool) -> str:
    """Name the workbook column a corrected value was read from."""
    if shifted and nutrient in SHIFT_CHAIN[:-1]:
        return SHIFT_CHAIN[SHIFT_CHAIN.index(nutrient) + 1]
    return nutrient


def estimate_serving_mass(frame: pd.DataFrame) -> pd.Series:
    """Estimate each serving's weight in grams; NaN when it cannot be estimated."""
    if not all(component in frame for component in MASS_COMPONENTS):
        return pd.Series(np.nan, index=frame.index)
    mass = sum(_column(frame, component) for component in MASS_COMPONENTS)
    return mass.where(mass >= MIN_SERVING_G)


def food_quality_flags(frame: pd.DataFrame, mass: pd.Series, shifted: pd.Series) -> pd.Series:
    """Return a ';'-separated list of quality flags for every food."""
    kcal = _column(frame, "caloric_value")
    atwater = (
        4 * _column(frame, "protein")
        + 4 * _column(frame, "carbohydrates")
        + 9 * _column(frame, "fat")
    )
    energy_ratio = kcal / atwater.where(atwater > 0)
    low, high = ATWATER_RANGE

    conditions = {
        "serving_mass_unknown": mass.isna(),
        "tiny_serving": mass < TINY_SERVING_G,
        "impossible_energy_density": (kcal / mass) > MAX_KCAL_PER_G,
        "energy_mismatch": (energy_ratio < low) | (energy_ratio > high),
        "micronutrient_shift_corrected": shifted,
        "possible_column_shift": ~shifted & (shift_signals(frame) == 1),
    }
    flags = pd.Series("", index=frame.index)
    for name, mask in conditions.items():
        mask = mask.fillna(False)
        flags[mask] = flags[mask].map(lambda text, flag=name: f"{text};{flag}" if text else flag)
    return flags


def basis_confidence(flags: str) -> str:
    """Summarise how far the per-100 g values of a food can be trusted."""
    names = set(filter(None, flags.split(";")))
    if "serving_mass_unknown" in names:
        return "unusable"
    if names & LOW_CONFIDENCE_FLAGS:
        return "low"
    return "high"


def value_quality(nutrient: str, amount: float, shifted: bool) -> str:
    """Classify one workbook value (in workbook units, after shift correction)."""
    if shifted and nutrient == SHIFT_CHAIN[-1]:
        return "lost_in_shift"
    if pd.isna(amount):
        return "missing"
    if amount == 0:
        return "zero_or_missing"  # the workbook does not distinguish the two
    if amount < PRECISION_FLOOR:
        return "below_precision"
    return "ok"


def clean_sheet(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a corrected copy of one loaded sheet with serving and quality columns."""
    corrected, shifted = correct_column_shift(frame)
    mass = estimate_serving_mass(corrected)
    flags = food_quality_flags(frame, mass, shifted)
    corrected["serving_g_estimated"] = mass.round(1)
    corrected["shift_corrected"] = shifted
    corrected["quality_flags"] = flags
    corrected["basis_confidence"] = flags.map(basis_confidence)
    return corrected


def to_canonical(nutrient: str, amount: float) -> tuple[float, str]:
    """Convert a workbook value to its canonical unit."""
    unit, multiplier = UNIT_CONVERSIONS[nutrient]
    return (np.nan if pd.isna(amount) else float(amount) * multiplier), unit
