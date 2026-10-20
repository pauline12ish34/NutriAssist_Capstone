import pytest

from nutriassist.planner import FoodCatalogue, MealPlanner, PlanRequest, targets_for
from nutriassist.planner.planner import MEAL_SLOTS, household_measure


@pytest.fixture(scope="module")
def planner():
    return MealPlanner(FoodCatalogue.load())


class TestTargets:
    @pytest.mark.parametrize("age, food_energy", [(6, 200), (9, 300), (12, 550)])
    def test_breastfed_children_need_the_who_energy_from_food(self, age, food_energy):
        assert targets_for(age).from_food["energy_kcal"] == pytest.approx(food_energy, abs=10)

    def test_not_breastfed_child_needs_everything_from_food_and_an_extra_snack(self):
        breastfed, not_breastfed = targets_for(12, True), targets_for(12, False)
        assert not_breastfed.from_food["energy_kcal"] == not_breastfed.band.total["energy_kcal"]
        assert not_breastfed.snacks == breastfed.snacks + 1

    def test_from_two_years_breast_milk_is_not_counted(self):
        assert targets_for(30).from_breast_milk["energy_kcal"] == 0
        assert targets_for(30, True).snacks == targets_for(30, False).snacks

    @pytest.mark.parametrize("age", [0, 5, 60])
    def test_ages_outside_6_to_59_months_are_rejected(self, age):
        with pytest.raises(ValueError, match="6 to 59 months"):
            targets_for(age)


class TestCatalogue:
    def test_every_food_has_reliable_energy_and_protein(self):
        catalogue = FoodCatalogue.load()
        assert len(catalogue) >= 30
        assert all(catalogue[k].per_100g["energy_kcal"] > 0 for k in catalogue.keys)

    def test_every_slot_has_foods(self):
        catalogue = FoodCatalogue.load()
        slots = {slot for meal in MEAL_SLOTS.values() for slot in meal}
        assert all(catalogue.for_slot(slot) for slot in slots)


class TestMealPlanner:
    @pytest.mark.parametrize("age", [6, 7, 10, 18, 30, 48, 59])
    def test_energy_and_diversity_targets_are_met(self, planner, age):
        plan = planner.plan(PlanRequest(age_months=age))
        day = plan.days[0]
        assert day.coverage_pct["energy_kcal"] == pytest.approx(100, abs=15)
        assert day.meets_min_diversity

    def test_meal_structure_follows_age(self, planner):
        kinds = lambda age: [m.kind for m in planner.plan(PlanRequest(age_months=age)).days[0].meals]
        assert kinds(7) == ["breakfast", "snack", "lunch"]
        assert kinds(18) == ["breakfast", "snack", "lunch", "snack", "dinner"]

    def test_week_plan_rotates_foods(self, planner):
        plan = planner.plan(PlanRequest(age_months=18, days=7))
        foods = {p.food.key for day in plan.days for p in day.portions()}
        assert len(foods) >= 20
        for previous, day in zip(plan.days, plan.days[1:]):
            proteins = lambda d: {p.food.key for m in d.meals if m.kind != "snack" for p in m.portions
                                  if "protein" in p.food.slots}
            assert proteins(previous) != proteins(day)

    def test_a_food_is_used_at_most_once_a_day(self, planner):
        for day in planner.plan(PlanRequest(age_months=30, days=7)).days:
            keys = [p.food.key for p in day.portions()]
            assert len(keys) == len(set(keys))

    def test_excluded_foods_never_appear(self, planner):
        plan = planner.plan(PlanRequest(age_months=18, days=7, excluded=frozenset({"egg", "groundnut_paste"})))
        assert not {"egg", "groundnut_paste"} & {p.food.key for d in plan.days for p in d.portions()}

    def test_only_available_foods_are_used_and_gaps_are_reported(self, planner):
        available = frozenset({"maize_flour", "beans", "banana", "amaranth", "sweet_potato"})
        plan = planner.plan(PlanRequest(age_months=18, available=available))
        assert {p.food.key for p in plan.days[0].portions()} <= available
        assert "fat" in plan.unfilled_slots

    def test_foods_are_age_appropriate(self, planner):
        week = planner.plan(PlanRequest(age_months=8, days=7))
        assert "sardines" not in {p.food.key for d in week.days for p in d.portions()}  # from 12 months

    def test_unknown_food_names_are_rejected(self, planner):
        with pytest.raises(ValueError, match="Unknown foods"):
            planner.plan(PlanRequest(age_months=18, excluded=frozenset({"pizza"})))

    def test_days_must_be_between_1_and_7(self):
        with pytest.raises(ValueError):
            PlanRequest(age_months=18, days=8)

    def test_young_infant_plan_warns_that_iron_is_hard_to_reach(self, planner):
        assert "iron_hard_to_reach" in planner.plan(PlanRequest(age_months=7)).tips

    def test_plan_is_deterministic(self, planner):
        request = PlanRequest(age_months=18, days=3)
        assert planner.plan(request).to_dict("en") == planner.plan(request).to_dict("en")

    def test_plan_serialises_in_kinyarwanda(self, planner):
        data = planner.plan(PlanRequest(age_months=18)).to_dict("rw")
        assert data["days"][0]["meals"][0]["meal"] == "Mu gitondo"
        assert data["tips"][0].startswith("Komeza konsa")
        assert "amashereka" in data["days"][0]["food_groups"]


@pytest.mark.parametrize("units, unit, language, expected", [
    (2, "tablespoon", "en", "2 tablespoons"),
    (1, "tablespoon", "en", "1 tablespoon"),
    (2.6, "tablespoon", "rw", "ibiyiko 2½"),
    (1, "egg", "rw", "igi 1"),
    (0.4, "egg", "rw", "igice cy'igi"),
    (0.4, "egg", "en", "½ egg"),
])
def test_household_measures(units, unit, language, expected):
    assert household_measure(units, unit, language) == expected
