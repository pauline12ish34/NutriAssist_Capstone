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
                    "dose_blocked"] = Field(
        description="Who wrote the answer: a reviewed stored answer, a fixed 'no checked answer' message (with "
                    "suggestions), the model, the model plus a safety note, or the safety rules")
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


class ErrorResponse(BaseModel):
    detail: str
