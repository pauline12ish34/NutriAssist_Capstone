"""WHO Child Growth Standards z-scores (children 0-59 months).

The WHO standards give, for each sex and each age in days (or each length/height in 0.1 cm steps),
three numbers L, M and S. A child's measurement y becomes a z-score with the LMS formula

    z = ((y / M) ** L - 1) / (L * S)

Weight-for-age and weight-for-length/height use WHO's "restricted" form beyond ±3 SD, where the
distance between the 2 and 3 SD lines is used instead, so very thin or heavy children are not
exaggerated (WHO Child Growth Standards: Methods and development, 2006, chapter 7). Length/height
has L = 1, so the plain formula is used everywhere.

Height is measured lying down (length) under 2 years and standing from 2 years. If the other position
was used, WHO adds 0.7 cm (standing child under 2) or takes off 0.7 cm (lying child of 2 or more).

Flags: WHO Anthro treats z-scores outside these limits as probable measurement or entry errors:
height-for-age below -6 or above +6, weight-for-age below -6 or above +5, weight-for-height
below -5 or above +5.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

WHO_TABLE = Path("data/reference/who_growth_lms.csv")
DAYS_PER_MONTH = 365.25 / 12
MAX_AGE_DAYS = 1856                    # end of the WHO tables (60 months)
LENGTH_TO_HEIGHT_CM = 0.7              # lying length is 0.7 cm longer than standing height
STANDING_FROM_DAYS = 731               # 24 months: WHO switches from length to height
FLAG_LIMITS = {"hfa": (-6.0, 6.0), "wfa": (-6.0, 5.0), "wfh": (-5.0, 5.0)}
SEXES = ("male", "female")


class GrowthInputError(ValueError):
    """A measurement outside what the WHO standards cover (wrong age, impossible weight...)."""


@dataclass(frozen=True)
class ZScores:
    wfa: float                         # weight-for-age (underweight)
    hfa: float | None                  # length/height-for-age (stunting); None without height
    wfh: float | None                  # weight-for-length/height (wasting); None without height
    flagged: frozenset[str]            # indicators outside the WHO plausibility limits


@lru_cache(maxsize=4)
def _tables(path: str) -> dict[tuple[str, str], pd.DataFrame]:
    table = pd.read_csv(path)
    return {(indicator, sex): group.set_index("x").sort_index()
            for (indicator, sex), group in table.groupby(["indicator", "sex"])}


def lms_table(indicator: str, sex: str, path: str | Path = WHO_TABLE) -> pd.DataFrame:
    """The WHO table for ``indicator`` (wfa, hfa, wfl, wfh) and ``sex``, indexed by age in days or cm."""
    return _tables(str(path))[(indicator, sex)]


def lms_z(y: float, L: float, M: float, S: float) -> float:
    """Plain LMS z-score."""
    return float(np.log(y / M) / S) if L == 0 else float(((y / M) ** L - 1) / (L * S))


def _sd_line(z: float, L: float, M: float, S: float) -> float:
    """The measurement that lies exactly ``z`` SD from the median."""
    return float(M * np.exp(S * z)) if L == 0 else float(M * (1 + L * S * z) ** (1 / L))


def restricted_z(y: float, L: float, M: float, S: float) -> float:
    """WHO's z-score for weight: beyond ±3 SD, steps of the 2-3 SD distance (see module docstring)."""
    z = lms_z(y, L, M, S)
    if z > 3:
        sd3, sd2 = _sd_line(3, L, M, S), _sd_line(2, L, M, S)
        return 3 + (y - sd3) / (sd3 - sd2)
    if z < -3:
        sd3, sd2 = _sd_line(-3, L, M, S), _sd_line(-2, L, M, S)
        return -3 - (sd3 - y) / (sd2 - sd3)
    return z


def _lms_at(table: pd.DataFrame, x: float) -> tuple[float, float, float]:
    """L, M, S at ``x``, interpolated linearly between the table rows (0.1 cm or 1 day apart)."""
    index = table.index.to_numpy()
    if not index[0] <= x <= index[-1]:
        raise GrowthInputError(f"{x} is outside the WHO table ({index[0]}-{index[-1]}).")
    return tuple(float(np.interp(x, index, table[column].to_numpy())) for column in ("L", "M", "S"))


def age_in_days(age_months: float) -> int:
    return int(round(age_months * DAYS_PER_MONTH))


def standing_height(height_cm: float, age_days: int, measured_lying: bool | None = None) -> float:
    """The height in the position WHO expects for the age (``measured_lying=None``: the expected one was used)."""
    if measured_lying is None:
        return height_cm
    if age_days < STANDING_FROM_DAYS and not measured_lying:
        return height_cm + LENGTH_TO_HEIGHT_CM
    if age_days >= STANDING_FROM_DAYS and measured_lying:
        return height_cm - LENGTH_TO_HEIGHT_CM
    return height_cm


def z_scores(age_months: float, sex: str, weight_kg: float, height_cm: float | None = None,
             measured_lying: bool | None = None, path: str | Path = WHO_TABLE) -> ZScores:
    """Weight-for-age, length/height-for-age and weight-for-length/height z-scores (unrounded)."""
    if sex not in SEXES:
        raise GrowthInputError(f"sex must be one of {SEXES}.")
    days = age_in_days(age_months)
    if not 0 <= days <= MAX_AGE_DAYS:
        raise GrowthInputError("The WHO standards cover children from birth to 59 months.")
    wfa = restricted_z(weight_kg, *_lms_at(lms_table("wfa", sex, path), days))
    hfa = wfh = None
    if height_cm is not None:
        height = standing_height(height_cm, days, measured_lying)
        hfa = lms_z(height, *_lms_at(lms_table("hfa", sex, path), days))
        table = lms_table("wfl" if days < STANDING_FROM_DAYS else "wfh", sex, path)
        try:
            wfh = restricted_z(weight_kg, *_lms_at(table, round(height, 1)))
        except GrowthInputError:          # height outside 45-110 cm (lying) or 65-120 cm (standing)
            wfh = None
    scores = {"wfa": wfa, "hfa": hfa, "wfh": wfh}
    flagged = frozenset(name for name, z in scores.items()
                        if z is not None and not FLAG_LIMITS[name][0] <= z <= FLAG_LIMITS[name][1])
    return ZScores(*scores.values(), flagged=flagged)   # not rounded: a child at -2.004 is below -2
