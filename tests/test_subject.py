"""Questions about adults only are out of scope; children, pregnancy, births and breastfeeding stay in."""

import pytest

from nutriassist.assistant import NutritionAssistant, ReplySource
from nutriassist.inference.scripted import ScriptedChatModel
from nutriassist.safety import messages
from nutriassist.safety.subject import is_about_adult_only

ADULT_ONLY = [
    "What should my grandma eat?",
    "My grandmother has diabetes, which foods are good for her?",
    "Is beans good for my grandfather?",
    "What is a good diet for elderly people?",
    "My husband wants to lose weight, what should he eat?",
    "What should my 70-year-old mother eat?",
    "Diet for my dad with high blood pressure",
    "Ni ibihe biryo byiza kuri nyogokuru?",
    "Sogokuru yarya iki?",
    "Umukecuru akwiye kurya iki?",
]

IN_SCOPE = [
    "What should my 2-year-old eat?",
    "My grandmother gives the baby tea, is that okay?",
    "What should I feed my grandson who is 18 months old?",
    "My wife is pregnant, what should she eat?",
    "My wife just gave birth, what should she eat?",
    "What should a breastfeeding mother eat?",
    "Foods for maternal health after delivery",
    "What should a new mother eat postpartum?",
    "Is it okay to give porridge to a 7 month old?",
    "Umwana w'amezi 8 yarya iki?",
    "Nyogokuru aha umwana icyayi, ni byiza?",
    "Umubyeyi wabyaye akwiye kurya iki?",
    "Umugore wanjye utwite yarya iki?",
    "Ni ibihe biryo byongera amashereka?",
    "Which foods are rich in iron?",
]


@pytest.mark.parametrize("question", ADULT_ONLY)
def test_questions_about_adults_only_are_out_of_scope(question):
    assert is_about_adult_only(question)


@pytest.mark.parametrize("question", IN_SCOPE)
def test_children_pregnancy_births_and_breastfeeding_stay_in_scope(question):
    assert not is_about_adult_only(question)


def test_the_model_is_not_called_for_a_question_about_a_grandmother():
    calls = []
    assistant = NutritionAssistant(ScriptedChatModel(lambda q: calls.append(q) or "Eat vegetables."))
    reply = assistant.ask("What should my grandma eat?")
    assert reply.source is ReplySource.OUT_OF_SCOPE
    assert reply.answer == messages.OUT_OF_SCOPE["en"]
    assert calls == []


def test_a_breastfeeding_mother_still_gets_a_model_answer():
    assistant = NutritionAssistant(ScriptedChatModel(lambda q: "Eat beans and drink water."))
    assert assistant.ask("What should a breastfeeding mother eat?").source is ReplySource.MODEL


def test_danger_signs_for_an_adult_still_get_the_urgent_message():
    reply = NutritionAssistant(ScriptedChatModel(lambda q: "")).ask("My grandmother had convulsions")
    assert reply.source in (ReplySource.SAFETY_RULE, ReplySource.OUT_OF_SCOPE)
