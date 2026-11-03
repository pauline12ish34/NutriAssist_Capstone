"""Malnutrition screening from the measurements community health workers take: weight, MUAC and height.

Rules (the cut-offs used by WHO and Rwanda's community-based nutrition programme):

    severe   bilateral oedema, MUAC < 11.5 cm (6-59 months) or weight-for-height < -3
             -> health centre today; no meal plan, because food at home is not the treatment
    moderate MUAC 11.5-12.5 cm, weight-for-height < -2 or > +2, height-for-age < -2, weight-for-age < -2
             -> refer for a check, plus feeding advice and a meal plan
    check    a z-score outside the WHO plausibility limits: probably a measuring or typing mistake
    normal   none of the above

A child is classified by the worst finding. Every result is a fixed rule, so the same measurements
always give the same answer and each line of the result can be traced back to a cut-off.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .growth import WHO_TABLE, ZScores, z_scores
from .messages import (ADVICE, FINDINGS, INDICATORS, INPUT_ERRORS, LEVELS, MUAC_NOT_USED, NO_HEIGHT,
                       RWANDA_STUNTING, TIPS)

LEVEL_ORDER = ("severe", "moderate", "check", "normal")
MUAC_SEVERE_CM = 11.5
MUAC_MODERATE_CM = 12.5
MUAC_FROM_MONTHS = 6
LIMITS = {"weight": (1.0, 35.0), "height": (40.0, 125.0), "muac": (6.0, 26.0)}


# Z-score cut-offs per indicator, from the worst: (cut-off, finding key, level, True for "higher than").
Z_RULES = {
    "wfh": ((-3, "sam_whz", "severe", False), (-2, "mam_whz", "moderate", False), (2, "overweight", "moderate", True)),
    "hfa": ((-3, "severe_stunting", "moderate", False), (-2, "stunting", "moderate", False)),
    "wfa": ((-3, "severe_underweight", "moderate", False), (-2, "underweight", "moderate", False)),
}


def classify_z(indicator: str, z: float) -> tuple[str, str] | None:
    """The (finding key, level) for a z-score, or None when it is within the normal range."""
    for cutoff, key, level, above in Z_RULES[indicator]:
        if (z > cutoff) if above else (z < cutoff):
            return key, level
    return None


class ScreeningInputError(ValueError):
    """An entry the screening cannot use; ``key`` selects the message in INPUT_ERRORS."""

    def __init__(self, key: str) -> None:
        super().__init__(INPUT_ERRORS[key]["en"])
        self.key = key

    def message(self, language: str) -> str:
        return INPUT_ERRORS[self.key][language]


@dataclass(frozen=True)
class ScreeningRequest:
    age_months: int
    sex: str                                  # "male" or "female"
    weight_kg: float
    height_cm: float | None = None
    muac_cm: float | None = None
    oedema: bool = False
    measured_lying: bool | None = None        # None: lying under 2 years, standing from 2 years

    def validate(self) -> None:
        if self.age_months is None or not 0 <= self.age_months <= 59:
            raise ScreeningInputError("age")
        if self.sex not in ("male", "female"):
            raise ScreeningInputError("sex")
        for key, value in (("weight", self.weight_kg), ("height", self.height_cm), ("muac", self.muac_cm)):
            if (value is None and key == "weight") or (value is not None and not LIMITS[key][0] <= value <= LIMITS[key][1]):
                raise ScreeningInputError(key)


@dataclass(frozen=True)
class Finding:
    key: str
    level: str
    values: dict = field(default_factory=dict)

    def text(self, language: str) -> str:
        values = dict(self.values)
        if "indicator" in values:
            values["indicator"] = INDICATORS[values["indicator"]][language]
        return FINDINGS[self.key][language].format(**values)


@dataclass(frozen=True)
class ScreeningResult:
    request: ScreeningRequest
    z: ZScores
    findings: tuple[Finding, ...]

    @property
    def level(self) -> str:
        levels = {finding.level for finding in self.findings} or {"normal"}
        return next(level for level in LEVEL_ORDER if level in levels)

    @property
    def conditions(self) -> set[str]:
        """The feeding problems found: wasting, stunting, underweight, overweight."""
        groups = {"mam_muac": "wasting", "mam_whz": "wasting", "sam_muac": "wasting", "sam_whz": "wasting",
                  "stunting": "stunting", "severe_stunting": "stunting",
                  "underweight": "underweight", "severe_underweight": "underweight", "overweight": "overweight"}
        return {groups[f.key] for f in self.findings if f.key in groups}

    @property
    def gets_meal_plan(self) -> bool:
        """A meal plan helps from 6 months, unless the child must go to the health centre today."""
        return self.request.age_months >= 6 and self.level in ("moderate", "normal")

    def tips(self) -> list[str]:
        if self.level == "severe":
            return []
        if self.request.age_months < 6:
            return ["under_6_months"] if self.level == "moderate" else []
        return [key for key in ("wasting", "underweight", "stunting", "overweight") if key in self.conditions]

    def notes(self) -> list[str]:
        notes = []
        if self.request.muac_cm is not None and self.request.age_months < MUAC_FROM_MONTHS:
            notes.append("muac_not_used")
        if self.request.height_cm is None:
            notes.append("no_height")
        if "stunting" in self.conditions:
            notes.append("rwanda_stunting")
        return notes

    def to_dict(self, language: str = "en") -> dict:
        note_texts = {"muac_not_used": MUAC_NOT_USED, "no_height": NO_HEIGHT, "rwanda_stunting": RWANDA_STUNTING}
        return {
            "level": self.level,
            "title": LEVELS[self.level][language],
            "advice": ADVICE[self.level][language],
            "z_scores": {name: None if value is None else round(value, 2)
                         for name, value in (("wfa", self.z.wfa), ("hfa", self.z.hfa), ("wfh", self.z.wfh))},
            "muac_cm": self.request.muac_cm,
            "findings": [{"key": f.key, "level": f.level, "text": f.text(language)} for f in self.findings],
            "tips": [TIPS[key][language] for key in self.tips()],
            "notes": [note_texts[key][language] for key in self.notes()],
            "meal_plan": self.gets_meal_plan,
        }


def screen(request: ScreeningRequest, who_table=WHO_TABLE) -> ScreeningResult:
    """Classify a child's nutritional status from age, sex, weight and (optionally) height, MUAC and oedema."""
    request.validate()
    z = z_scores(request.age_months, request.sex, request.weight_kg, request.height_cm,
                 request.measured_lying, path=who_table)
    findings: list[Finding] = []
    if request.oedema:
        findings.append(Finding("sam_oedema", "severe"))
    muac = request.muac_cm
    if muac is not None and request.age_months >= MUAC_FROM_MONTHS:
        if muac < MUAC_SEVERE_CM:
            findings.append(Finding("sam_muac", "severe", {"muac": muac}))
        elif muac < MUAC_MODERATE_CM:
            findings.append(Finding("mam_muac", "moderate", {"muac": muac}))
    for indicator in Z_RULES:
        value = getattr(z, indicator)
        if value is None:
            continue
        if indicator in z.flagged:
            findings.append(Finding("check_measurement", "check", {"indicator": indicator, "z": f"{value:+.2f}"}))
        elif (found := classify_z(indicator, value)) is not None:
            findings.append(Finding(*found, {"z": f"{value:+.2f}"}))
    return ScreeningResult(request, z, tuple(findings))
