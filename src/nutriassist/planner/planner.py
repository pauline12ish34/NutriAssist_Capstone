"""Build daily or weekly meal plans for a child from local foods.

Algorithm, for each day:
1. Lay out the eating occasions for the child's age (WHO: meals and snacks per day).
2. Fill each slot (porridge flour, staple, protein, vegetable, fat, fruit, snack) with the food that
   scores highest:
       score = Σ weight[n] · min(amount[n], still_needed[n]) / target[n]     useful nutrients
             + DIVERSITY_BONUS   if the food adds a food group not eaten yet today
             - REPEAT_PENALTY · (times eaten in the previous REPEAT_WINDOW days)
   A food is used at most once a day. Greedy selection is fast (days × slots × foods) and every
   choice can be explained from the score.
3. Scale all portions so the day's energy from food meets the target, within realistic limits,
   then round to household amounts.
4. Report nutrient coverage (food + breast milk), WHO minimum dietary diversity and feeding tips.

After a growth check the plan is adjusted for what was found (``PlanRequest.conditions``):
    wasting, underweight  catch-up growth: +25% energy and protein, one extra snack, and energy and
                          protein weigh more in the score
    stunting              no change to the food choice: the planner already puts a food from animals
                          (milk products, eggs, meat, fish) in every day when the family has one. The plan
                          says so, or warns when the chosen foods include none.
    overweight            no added-fat slot (avocado, groundnut paste), and energy weighs less
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from .catalogue import FOOD_GROUPS, Food, FoodCatalogue
from .requirements import NUTRIENTS, NutritionTargets, targets_for
from .tips import ADJUSTMENTS, MEAL_NAMES, tip

REFERENCE_FOOD_ENERGY = 550.0            # kcal from food at 12-23 months, which the catalogue portions are sized for
NUTRIENT_WEIGHTS = {"energy_kcal": 1.0, "protein_g": 1.0, "iron_mg": 1.5, "calcium_mg": 0.5}
DIVERSITY_BONUS = 0.3
REPEAT_PENALTY = 0.25
REPEAT_WINDOW = 2                        # days
SCALE_LIMITS = (0.6, 1.6)                # how far energy calibration may stretch the starting portions
MIN_DIETARY_DIVERSITY = 5                # of 8 groups (WHO, children 6-23 months)
IRON_FOODS = frozenset({"legumes_nuts", "vitamin_a_fruit_veg"})

CONDITIONS = ("wasting", "underweight", "stunting", "overweight")
ANIMAL_SOURCE = frozenset({"dairy", "flesh_foods", "eggs"})
CONDITION_WEIGHTS = {   # multiply NUTRIENT_WEIGHTS
    "wasting": {"energy_kcal": 1.5, "protein_g": 1.5},
    "underweight": {"energy_kcal": 1.5, "protein_g": 1.5},
    "overweight": {"energy_kcal": 0.5},
}

MEAL_SLOTS = {
    "breakfast": ("porridge_flour", "porridge_enricher", "fruit"),
    "lunch": ("staple", "protein", "vegetable", "fat"),
    "dinner": ("staple", "protein", "vegetable", "fat"),
    "snack": ("snack",),
}


@dataclass(frozen=True)
class PlanRequest:
    age_months: int
    days: int = 1
    breastfed: bool = True
    available: frozenset[str] | None = None      # only these foods (None = all)
    excluded: frozenset[str] = frozenset()       # never these (allergy, dislike, unavailable)
    conditions: frozenset[str] = frozenset()     # from a growth check: wasting, underweight, stunting, overweight

    def __post_init__(self) -> None:
        if not 1 <= self.days <= 7:
            raise ValueError("A plan covers 1 to 7 days.")
        unknown = sorted(set(self.conditions) - set(CONDITIONS))
        if unknown:
            raise ValueError(f"Unknown conditions {unknown}; use {CONDITIONS}.")

    @property
    def catch_up(self) -> bool:
        return bool({"wasting", "underweight"} & set(self.conditions))


@dataclass(frozen=True)
class Profile:
    """How the food score changes for the child's growth-check result."""
    weights: dict[str, float]
    skip_slots: frozenset[str] = frozenset()      # no added-fat slot, and no added-fat food in any slot

    @classmethod
    def for_conditions(cls, conditions: frozenset[str]) -> "Profile":
        weights = dict(NUTRIENT_WEIGHTS)
        for nutrient in weights:
            factors = [CONDITION_WEIGHTS[c][nutrient] for c in conditions if nutrient in CONDITION_WEIGHTS.get(c, {})]
            if factors:   # wasting and underweight together count once, not 1.5 x 1.5
                weights[nutrient] *= max(factors) if max(factors) > 1 else min(factors)
        return cls(weights, frozenset({"fat"}) if "overweight" in conditions else frozenset())


@dataclass
class Portion:
    food: Food
    grams: float

    def to_dict(self, language: str) -> dict:
        return {"food": self.food.key, "name": self.food.name(language), "grams": round(self.grams),
                "household_measure": household_measure(self.grams / self.food.unit_g, self.food.unit, language),
                "group": self.food.group}


@dataclass
class Meal:
    kind: str
    portions: list[Portion] = field(default_factory=list)

    def to_dict(self, language: str) -> dict:
        return {"meal": MEAL_NAMES[self.kind]["rw" if language == "rw" else "en"],
                "foods": [p.to_dict(language) for p in self.portions]}


@dataclass
class DayPlan:
    day: int
    meals: list[Meal]
    from_food: dict[str, float]
    coverage_pct: dict[str, float]
    food_groups: list[str]

    @property
    def dietary_diversity(self) -> int:
        return len(self.food_groups)

    @property
    def meets_min_diversity(self) -> bool:
        return self.dietary_diversity >= MIN_DIETARY_DIVERSITY

    def portions(self) -> Iterable[Portion]:
        return (portion for meal in self.meals for portion in meal.portions)

    def to_dict(self, language: str) -> dict:
        lang = "rw" if language == "rw" else "en"
        return {
            "day": self.day,
            "meals": [meal.to_dict(language) for meal in self.meals],
            "nutrients_from_food": {k: round(v, 1) for k, v in self.from_food.items()},
            "coverage_pct": {k: round(v) for k, v in self.coverage_pct.items()},
            "food_groups": [FOOD_GROUPS[g][1 if lang == "rw" else 0] for g in self.food_groups],
            "dietary_diversity": self.dietary_diversity,
            "meets_min_diversity": self.meets_min_diversity,
        }


@dataclass
class MealPlan:
    request: PlanRequest
    targets: NutritionTargets
    days: list[DayPlan]
    tips: list[str]                       # tip keys
    unfilled_slots: list[str] = field(default_factory=list)

    @property
    def animal_food_every_day(self) -> bool:
        return all(any(p.food.group in ANIMAL_SOURCE for p in day.portions()) for day in self.days)

    def _adjustment_key(self, condition: str) -> str:
        if condition == "stunting" and not self.animal_food_every_day:
            return "stunting_no_animal_food"
        return condition

    def to_dict(self, language: str = "en") -> dict:
        lang = "rw" if language == "rw" else "en"
        adjusted = [c for c in CONDITIONS if c in self.request.conditions]
        return {
            "adjusted_for": adjusted,
            "adjustments": list(dict.fromkeys(ADJUSTMENTS[self._adjustment_key(c)][lang] for c in adjusted)),
            "age_months": self.request.age_months,
            "age_band": self.targets.band.key,
            "breastfed": self.targets.breastfed,
            "targets_from_food": {k: round(v, 1) for k, v in self.targets.from_food.items()},
            "from_breast_milk": {k: round(v, 1) for k, v in self.targets.from_breast_milk.items()},
            "days": [day.to_dict(language) for day in self.days],
            "tips": [tip(key, language) for key in self.tips],
            "unfilled_slots": sorted(set(self.unfilled_slots)),
        }


class MealPlanner:
    def __init__(self, catalogue: FoodCatalogue) -> None:
        self.catalogue = catalogue

    def plan(self, request: PlanRequest) -> MealPlan:
        targets = targets_for(request.age_months, request.breastfed, catch_up=request.catch_up)
        profile = Profile.for_conditions(frozenset(request.conditions))
        foods = self._eligible_foods(request)
        scale = targets.from_food["energy_kcal"] / REFERENCE_FOOD_ENERGY
        recent: deque[Counter] = deque(maxlen=REPEAT_WINDOW)
        days, unfilled = [], []

        for day_number in range(1, request.days + 1):
            meals, missing = self._choose_foods(targets, foods, scale, recent, profile)
            unfilled += missing
            day = self._finish_day(day_number, meals, targets)
            recent.append(Counter(p.food.key for p in day.portions()))
            days.append(day)

        return MealPlan(request, targets, days, self._tips(targets, days, request.conditions), unfilled)

    def _eligible_foods(self, request: PlanRequest) -> list[Food]:
        named = set(request.excluded) | set(request.available or ())
        unknown = sorted(named - set(self.catalogue.keys))
        if unknown:
            raise ValueError(f"Unknown foods: {unknown}")
        keys = request.available if request.available is not None else self.catalogue.keys
        return [self.catalogue[k] for k in self.catalogue.keys
                if k in keys and k not in request.excluded and self.catalogue[k].min_age_months <= request.age_months]

    def _choose_foods(self, targets: NutritionTargets, foods: Sequence[Food], scale: float,
                      recent: deque[Counter], profile: Profile) -> tuple[list[Meal], list[str]]:
        needed = dict(targets.from_food)
        groups_today: set[str] = set()
        used_today: set[str] = set()
        meals, missing = [], []
        for kind in _occasions(targets):
            meal = Meal(kind)
            for slot in MEAL_SLOTS[kind]:
                if slot in profile.skip_slots:
                    continue
                candidates = [f for f in foods if slot in f.slots and f.key not in used_today
                              and not (profile.skip_slots & set(f.slots))]
                if not candidates:
                    missing.append(slot)
                    continue
                best = max(candidates, key=lambda f: (self._score(f, f.portion_g * scale, needed, targets,
                                                                 groups_today, recent, profile), f.key))
                portion = Portion(best, best.portion_g * scale)
                meal.portions.append(portion)
                used_today.add(best.key)
                groups_today.add(best.group)
                for nutrient, amount in best.nutrients(portion.grams).items():
                    if nutrient in needed:
                        needed[nutrient] = max(needed[nutrient] - amount, 0.0)
            if meal.portions:  # with a short list of available foods a snack can end up empty
                meals.append(meal)
        return meals, missing

    @staticmethod
    def _score(food: Food, grams: float, needed: dict[str, float], targets: NutritionTargets,
               groups_today: set[str], recent: deque[Counter], profile: Profile | None = None) -> float:
        profile = profile or Profile(dict(NUTRIENT_WEIGHTS))
        amounts = food.nutrients(grams)
        useful = sum(
            weight * min(amounts.get(n, 0.0), needed[n]) / targets.from_food[n]
            for n, weight in profile.weights.items() if targets.from_food[n] > 0
        )
        diversity = DIVERSITY_BONUS if food.group not in groups_today else 0.0
        repeats = sum(day[food.key] for day in recent)
        return useful + diversity - REPEAT_PENALTY * repeats

    def _finish_day(self, number: int, meals: list[Meal], targets: NutritionTargets) -> DayPlan:
        planned = sum(p.food.nutrients(p.grams)["energy_kcal"] for meal in meals for p in meal.portions)
        if planned > 0:
            factor = min(max(targets.from_food["energy_kcal"] / planned, SCALE_LIMITS[0]), SCALE_LIMITS[1])
            for meal in meals:
                for portion in meal.portions:
                    portion.grams = _round_portion(portion.grams * factor, portion.food)

        from_food = {n: 0.0 for n in NUTRIENTS}
        for meal in meals:
            for portion in meal.portions:
                for nutrient, amount in portion.food.nutrients(portion.grams).items():
                    if nutrient in from_food:
                        from_food[nutrient] += amount
        total_need = targets.need
        coverage = {n: 100 * (from_food[n] + targets.from_breast_milk[n]) / total_need[n] for n in NUTRIENTS}
        groups = {p.food.group for meal in meals for p in meal.portions}
        if targets.breastfed and targets.band.breast_milk_g > 0:
            groups.add("breast_milk")
        ordered_groups = [g for g in FOOD_GROUPS if g in groups]
        return DayPlan(number, meals, from_food, coverage, ordered_groups)

    @staticmethod
    def _tips(targets: NutritionTargets, days: list[DayPlan], conditions: frozenset[str] = frozenset()) -> list[str]:
        tips = []
        if targets.breastfed:
            tips.append("keep_breastfeeding")
        elif targets.band.breast_milk_g > 0:
            tips.append("not_breastfed")
        tips.append(f"texture_{targets.band.texture}")
        if any(p.food.group in IRON_FOODS for day in days for p in day.portions()):
            tips.append("vitamin_c_with_iron")
        if min(day.coverage_pct["iron_mg"] for day in days) < 70:
            tips.append("iron_hard_to_reach")
        tips += ["no_sugar_salt", "hygiene", "adjusted_plan" if conditions else "guide_only"]
        return tips


def _occasions(targets: NutritionTargets) -> list[str]:
    """Meals with snacks between them, e.g. breakfast, snack, lunch, snack, dinner."""
    meals = ["breakfast", "lunch", "dinner"][: targets.meals]
    order = []
    snacks = targets.snacks
    for i, meal in enumerate(meals):
        order.append(meal)
        if snacks and i < len(meals) - 1:
            order.append("snack")
            snacks -= 1
    order += ["snack"] * snacks
    return order


def _round_portion(grams: float, food: Food) -> float:
    """Whole eggs and half eggs; other foods to the nearest 5 g, never below 5 g."""
    if food.unit_g >= 50:
        return max(round(grams / (food.unit_g / 2)) * (food.unit_g / 2), food.unit_g / 2)
    return max(5.0, 5 * round(grams / 5))


# (singular, plural) per language
MEASURES = {
    "tablespoon": {"en": ("tablespoon", "tablespoons"), "rw": ("ikiyiko", "ibiyiko")},
    "flour_spoon": {"en": ("tablespoon of flour", "tablespoons of flour"), "rw": ("ikiyiko cy'ifu", "ibiyiko by'ifu")},
    "egg": {"en": ("egg", "eggs"), "rw": ("igi", "amagi")},
}


def household_measure(units: float, unit: str, language: str) -> str:
    """Rounded to the nearest half: '2½ tablespoons', 'ibiyiko 2½', '½ egg', "igice cy'igi"."""
    halves = max(1, round(units * 2))
    whole, half = divmod(halves, 2)
    singular, plural = MEASURES[unit]["rw" if language == "rw" else "en"]
    if language == "rw":
        if whole == 0:
            return f"igice cy'{singular}"
        return f"{singular if halves == 2 else plural} {whole}{'½' if half else ''}"
    amount = f"{whole if whole else ''}{'½' if half else ''}"
    return f"{amount} {singular if halves <= 2 else plural}"
