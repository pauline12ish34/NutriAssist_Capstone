"""Daily nutrient needs of children aged 6-59 months, and what breast milk already provides.

Sources (approximate population values, rounded; this is a planning guide, not a prescription):
- Energy from complementary food for breastfed children (200 / 300 / 550 kcal) and average
  breast-milk intake (674 / 616 / 549 g/day): WHO/UNICEF (1998) "Complementary feeding of young
  children in developing countries" and PAHO/WHO (2003) "Guiding principles for complementary feeding".
- Total energy at 24-59 months: FAO/WHO/UNU (2004) "Human energy requirements", average of boys and girls.
- Protein: WHO/FAO/UNU (2007) safe levels (g/kg/day) times WHO median weight for the age band.
- Iron (10% bioavailability) and calcium: FAO/WHO (2004) "Vitamin and mineral requirements in human nutrition".
- Meals and snacks per day: PAHO/WHO (2003); one extra snack when the child is not breastfed.
- Catch-up growth (wasting, underweight): +25% energy and protein and one extra snack, WHO (2012) technical
  note on supplementary foods for moderate acute malnutrition.
- Breast-milk composition per 100 g: about 62 kcal (the density behind the WHO energy figures), 0.9 g protein, 0.03 mg iron, 28 mg calcium.
"""

from __future__ import annotations

from dataclasses import dataclass

NUTRIENTS = ("energy_kcal", "protein_g", "iron_mg", "calcium_mg")
BREAST_MILK_PER_100G = {"energy_kcal": 62.0, "protein_g": 0.9, "iron_mg": 0.03, "calcium_mg": 28.0}
MIN_AGE_MONTHS, MAX_AGE_MONTHS = 6, 59
# Catch-up growth after moderate wasting or underweight: WHO (2012) "Technical note: supplementary foods for
# the management of moderate acute malnutrition" adds about 25 kcal/kg/day, roughly a quarter of the need
# at 6-59 months; protein is raised in the same proportion.
CATCH_UP_FACTOR = 1.25
CATCH_UP_NUTRIENTS = ("energy_kcal", "protein_g")


@dataclass(frozen=True)
class AgeBand:
    key: str
    min_months: int
    max_months: int
    total: dict[str, float]          # whole-day need from all sources
    breast_milk_g: float             # average intake if breastfed (0 from 24 months)
    meals: int
    snacks: int
    texture: str                     # key into the texture tips


AGE_BANDS: tuple[AgeBand, ...] = (
    AgeBand("6-8", 6, 8, {"energy_kcal": 615, "protein_g": 10.0, "iron_mg": 9.3, "calcium_mg": 400},
            674, meals=2, snacks=1, texture="mashed"),
    AgeBand("9-11", 9, 11, {"energy_kcal": 686, "protein_g": 10.4, "iron_mg": 9.3, "calcium_mg": 400},
            616, meals=3, snacks=1, texture="chopped"),
    AgeBand("12-23", 12, 23, {"energy_kcal": 894, "protein_g": 11.3, "iron_mg": 5.8, "calcium_mg": 500},
            549, meals=3, snacks=2, texture="family"),
    AgeBand("24-35", 24, 35, {"energy_kcal": 1050, "protein_g": 12.4, "iron_mg": 5.8, "calcium_mg": 500},
            0, meals=3, snacks=2, texture="family"),
    AgeBand("36-59", 36, 59, {"energy_kcal": 1350, "protein_g": 14.0, "iron_mg": 6.3, "calcium_mg": 600},
            0, meals=3, snacks=2, texture="family"),
)


@dataclass(frozen=True)
class NutritionTargets:
    age_months: int
    band: AgeBand
    breastfed: bool
    from_breast_milk: dict[str, float]
    from_food: dict[str, float]      # what the meal plan has to provide
    total_need: dict[str, float] | None = None   # whole-day need when raised for catch-up growth
    extra_snacks: int = 0

    @property
    def need(self) -> dict[str, float]:
        return self.total_need or self.band.total

    @property
    def meals(self) -> int:
        return self.band.meals

    @property
    def snacks(self) -> int:
        # WHO advises extra feeds for non-breastfed children under 2 years.
        not_breastfed_infant = self.band.breast_milk_g > 0 and not self.breastfed
        return self.band.snacks + (1 if not_breastfed_infant else 0) + self.extra_snacks


def age_band(age_months: int) -> AgeBand:
    if not MIN_AGE_MONTHS <= age_months <= MAX_AGE_MONTHS:
        raise ValueError(f"Meal plans cover children aged {MIN_AGE_MONTHS} to {MAX_AGE_MONTHS} months "
                         f"(got {age_months}). Before 6 months, give breast milk only.")
    return next(band for band in AGE_BANDS if band.min_months <= age_months <= band.max_months)


def targets_for(age_months: int, breastfed: bool = True, catch_up: bool = False) -> NutritionTargets:
    """``catch_up``: a wasted or underweight child gets CATCH_UP_FACTOR more energy and protein, and one more snack."""
    band = age_band(age_months)
    milk_g = band.breast_milk_g if breastfed else 0.0
    from_milk = {n: milk_g * BREAST_MILK_PER_100G[n] / 100 for n in NUTRIENTS}
    total = dict(band.total)
    if catch_up:
        total = {n: v * (CATCH_UP_FACTOR if n in CATCH_UP_NUTRIENTS else 1.0) for n, v in total.items()}
    from_food = {n: max(total[n] - from_milk[n], 0.0) for n in NUTRIENTS}
    return NutritionTargets(age_months, band, breastfed, from_milk, from_food,
                            total_need=total if catch_up else None, extra_snacks=1 if catch_up else 0)
