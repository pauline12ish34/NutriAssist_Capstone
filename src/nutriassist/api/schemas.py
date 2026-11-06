"""Request and response models. They also generate the Swagger documentation at ``/docs``."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..assistant import MAX_QUESTION_CHARS

Language = Literal["en", "rw"]


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=MAX_QUESTION_CHARS,
                          examples=["What foods should I give my 8-month-old baby?", "Umwana w'amezi 9 yarya iki?"])


class ChatResponse(BaseModel):
    answer: str
    language: Language = Field(description="Language detected in the question; the answer uses it too")
    safety_level: Literal["none", "medical", "urgent"]
    danger_signs: list[str] = Field(description="Danger signs or medical topics found in the question")
    source: Literal["reviewed_answer", "no_reviewed_answer", "model", "model+referral_note", "safety_rule",
                    "dose_blocked", "topic_rule_on_answer", "out_of_scope", "off_topic_blocked"] = Field(
        description="Who wrote the answer: a reviewed stored answer, a fixed 'no checked answer' message (with "
                    "suggestions), the model, the model plus a safety note, the safety rules, or a fixed "
                    "decline because the question (or the model's answer) was outside nutrition")
    model: str
    latency_ms: float
    translated: bool = Field(False, description="The model answered in English and the answer was machine-translated")
    matched_question: str | None = Field(None, description="For a reviewed answer: the stored question it matched")
    suggestions: list[str] = Field(default_factory=list,
                                   description="'Did you mean...?' reviewed questions; send one back as the question")


class MealPlanRequest(BaseModel):
    age_months: int = Field(..., ge=6, le=59, description="Child's age in months (6-59)", examples=[12])
    days: int = Field(1, ge=1, le=7)
    breastfed: bool = True
    language: Language = "en"
    available: list[str] | None = Field(None, description="Use only these foods (keys from /foods); null = all")
    excluded: list[str] = Field(default_factory=list, description="Never use these foods (keys from /foods)")
    conditions: list[Literal["wasting", "underweight", "stunting", "overweight"]] = Field(
        default_factory=list, description="Adjust the plan for a growth-check result (see /screening)")


class PortionOut(BaseModel):
    food: str
    name: str
    grams: int
    household_measure: str
    group: str


class MealOut(BaseModel):
    meal: str
    foods: list[PortionOut]


class DayOut(BaseModel):
    day: int
    meals: list[MealOut]
    nutrients_from_food: dict[str, float]
    coverage_pct: dict[str, int] = Field(description="% of the day's need met by food plus breast milk")
    food_groups: list[str]
    dietary_diversity: int = Field(description="Number of WHO food groups (of 8) eaten in the day")
    meets_min_diversity: bool


class MealPlanResponse(BaseModel):
    adjusted_for: list[str] = Field(default_factory=list, description="Growth-check conditions the plan is adjusted for")
    adjustments: list[str] = Field(default_factory=list, description="What changed in the plan, in words")
    age_months: int
    age_band: str
    breastfed: bool
    targets_from_food: dict[str, float]
    from_breast_milk: dict[str, float]
    days: list[DayOut]
    tips: list[str]
    unfilled_slots: list[str]


class FoodOut(BaseModel):
    key: str
    name_en: str
    name_rw: str
    group: str
    min_age_months: int


class HealthResponse(BaseModel):
    status: Literal["ok"]
    model: str
    demo_mode: bool = Field(description="True when no trained model is installed and answers are placeholders")
    version: str


class ScreeningRequestIn(BaseModel):
    age_months: int = Field(..., description="Child's age in completed months (0-59)", examples=[18])
    sex: Literal["male", "female"] = Field(..., examples=["female"])
    weight_kg: float = Field(..., description="Weight in kg (1-35)", examples=[9.0])
    height_cm: float | None = Field(None, description="Length (lying, under 2 years) or height (standing), cm",
                                    examples=[76.5])
    muac_cm: float | None = Field(None, description="Mid-upper arm circumference in cm (used from 6 months)",
                                  examples=[12.0])
    oedema: bool = Field(False, description="Swelling of both feet (bilateral pitting oedema)")
    breastfed: bool = Field(True, description="For the meal plan: the child is still breastfed")
    language: Language = "en"


class FindingOut(BaseModel):
    key: str
    level: Literal["severe", "moderate", "check"]
    text: str


class ScreeningResponse(BaseModel):
    level: Literal["severe", "moderate", "check", "normal"] = Field(
        description="severe: health centre today; moderate: refer for a check; check: measure again")
    title: str
    advice: str
    z_scores: dict[str, float | None] = Field(description="WHO z-scores: wfa (weight-for-age), hfa "
                                                          "(height-for-age), wfh (weight-for-height)")
    muac_cm: float | None
    findings: list[FindingOut]
    tips: list[str]
    notes: list[str]
    meal_plan: MealPlanResponse | None = Field(None, description="A 1-day plan, unless the child must go to the "
                                                                 "health centre today or is under 6 months")


class ErrorResponse(BaseModel):
    detail: str
