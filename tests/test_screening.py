import pytest

from nutriassist.screening import ScreeningInputError, ScreeningRequest, screen, z_scores
from nutriassist.screening.growth import age_in_days, lms_table, lms_z, restricted_z, standing_height
from nutriassist.screening.messages import ADVICE, FINDINGS, INPUT_ERRORS, LEVELS, TIPS

INDICATORS = ("wfa", "hfa", "wfl", "wfh")
SEXES = ("male", "female")


def median(indicator, sex, x):
    return float(lms_table(indicator, sex).loc[x, "M"])


# ---------------------------------------------------------------- WHO z-scores

@pytest.mark.parametrize("indicator", INDICATORS)
@pytest.mark.parametrize("sex", SEXES)
def test_z_scores_match_every_sd_line_printed_by_who(indicator, sex):
    """WHO prints the -3, -2, +2 and +3 SD values (3 decimals) on every row: our z must give those back."""
    z = lms_z if indicator == "hfa" else restricted_z
    worst = 0.0
    for row in lms_table(indicator, sex).itertuples():
        for printed, expected in ((row.sd3neg, -3), (row.sd2neg, -2), (row.sd2, 2), (row.sd3, 3)):
            worst = max(worst, abs(z(printed, row.L, row.M, row.S) - expected))
    assert worst < 0.01


def test_the_median_child_has_z_scores_of_zero():
    days = age_in_days(12)
    height = round(median("hfa", "female", days), 1)
    weight = median("wfa", "female", days)
    z = z_scores(12, "female", weight, height)
    assert z.wfa == pytest.approx(0, abs=1e-9) and z.hfa == pytest.approx(0, abs=0.03)
    assert z.wfh == pytest.approx(0, abs=0.3)   # median weight is close to, not exactly, median weight-for-length


def test_restricted_z_below_minus_3_counts_in_steps_of_the_2_to_3_sd_distance():
    row = lms_table("wfa", "male").loc[730]
    one_step_below = row.sd3neg - (row.sd2neg - row.sd3neg)
    assert restricted_z(one_step_below, row.L, row.M, row.S) == pytest.approx(-4, abs=0.01)


def test_length_and_height_switch_at_two_years():
    assert standing_height(80.0, age_in_days(18), measured_lying=False) == pytest.approx(80.7)
    assert standing_height(90.0, age_in_days(30), measured_lying=True) == pytest.approx(89.3)
    assert standing_height(90.0, age_in_days(30)) == 90.0


def test_a_child_just_below_minus_2_is_not_rounded_up_to_normal():
    row = lms_table("wfa", "female").loc[age_in_days(24)]
    weight = row.sd2neg - 0.002          # z about -2.005: rounds to -2.00 but is below the cut-off
    result = screen(ScreeningRequest(age_months=24, sex="female", weight_kg=weight))
    assert -2.01 < result.z.wfa < -2
    assert "underweight" in {f.key for f in result.findings}


def test_without_height_only_weight_for_age_is_computed():
    z = z_scores(24, "male", 12.0)
    assert z.hfa is None and z.wfh is None and z.wfa is not None


# ---------------------------------------------------------------- classification

def test_red_muac_is_severe_and_gets_no_meal_plan():
    result = screen(ScreeningRequest(age_months=18, sex="male", weight_kg=8.0, muac_cm=11.0))
    assert result.level == "severe"
    assert "sam_muac" in {f.key for f in result.findings}
    assert not result.gets_meal_plan and result.tips() == []


def test_oedema_is_severe_whatever_the_measurements():
    result = screen(ScreeningRequest(age_months=24, sex="female", weight_kg=12.0, muac_cm=14.0, oedema=True))
    assert result.level == "severe"


def test_yellow_muac_is_moderate_with_wasting_advice_and_a_meal_plan():
    result = screen(ScreeningRequest(age_months=18, sex="female", weight_kg=9.5, muac_cm=12.0))
    assert result.level == "moderate"
    assert "wasting" in result.tips() and result.gets_meal_plan


def test_short_child_is_stunted_and_gets_the_rwanda_figure():
    days = age_in_days(30)
    short = float(lms_table("hfa", "male").loc[days, "sd2neg"]) - 1.0
    result = screen(ScreeningRequest(age_months=30, sex="male", weight_kg=12.0, height_cm=round(short, 1), muac_cm=14.5))
    assert "stunting" in result.conditions and result.level == "moderate"
    assert "rwanda_stunting" in result.notes()


def test_a_child_on_the_median_is_normal():
    days = age_in_days(36)
    result = screen(ScreeningRequest(age_months=36, sex="female", weight_kg=median("wfa", "female", days),
                                     height_cm=round(median("hfa", "female", days), 1), muac_cm=15.5))
    assert result.level == "normal" and result.findings == () and result.gets_meal_plan


def test_impossible_measurements_ask_to_measure_again():
    # 60 cm tall at 4 years: height-for-age far below -6
    result = screen(ScreeningRequest(age_months=48, sex="male", weight_kg=15.0, height_cm=60.0))
    assert result.level in ("check", "severe", "moderate")
    assert "check_measurement" in {f.key for f in result.findings}


def test_muac_is_not_used_under_6_months():
    days = age_in_days(4)
    result = screen(ScreeningRequest(age_months=4, sex="female", weight_kg=median("wfa", "female", days), muac_cm=10.0))
    assert result.level == "normal" and "muac_not_used" in result.notes()
    assert not result.gets_meal_plan


def test_underweight_baby_under_6_months_is_sent_to_the_health_centre():
    days = age_in_days(3)
    light = float(lms_table("wfa", "male").loc[days, "sd2neg"]) - 0.3
    result = screen(ScreeningRequest(age_months=3, sex="male", weight_kg=round(light, 1)))
    assert result.level == "moderate" and result.tips() == ["under_6_months"]


@pytest.mark.parametrize("request_kwargs, key", [
    ({"age_months": 70, "sex": "male", "weight_kg": 12}, "age"),
    ({"age_months": 12, "sex": "x", "weight_kg": 9}, "sex"),
    ({"age_months": 12, "sex": "male", "weight_kg": 90}, "weight"),
    ({"age_months": 12, "sex": "male", "weight_kg": 9, "height_cm": 300}, "height"),
    ({"age_months": 12, "sex": "male", "weight_kg": 9, "muac_cm": 2}, "muac"),
])
def test_entries_outside_the_limits_are_rejected(request_kwargs, key):
    with pytest.raises(ScreeningInputError) as error:
        screen(ScreeningRequest(**request_kwargs))
    assert error.value.key == key and error.value.message("rw")


def test_result_reads_in_both_languages():
    result = screen(ScreeningRequest(age_months=18, sex="female", weight_kg=8.5, height_cm=74.0, muac_cm=12.0))
    for lang in ("en", "rw"):
        data = result.to_dict(lang)
        assert data["title"] == LEVELS[result.level][lang] and data["advice"] == ADVICE[result.level][lang]
        assert all(finding["text"] for finding in data["findings"])


def test_every_message_has_both_languages():
    for table in (LEVELS, FINDINGS, ADVICE, TIPS, INPUT_ERRORS):
        for texts in table.values():
            assert set(texts) == {"en", "rw"} and all(texts.values())
