"""Questions about adults only are out of scope; children, pregnancy, births and breastfeeding stay in."""

import pytest

from nutriassist.assistant import NutritionAssistant, ReplySource
from nutriassist.inference.scripted import ScriptedChatModel
from nutriassist.safety import messages
from nutriassist.safety.subject import outside_target_group

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
    # older children and teenagers, even when called "child"
    "What food can you give a 15 years old child?",
    "Food for a 15-year-old child",
    "My 8 year old son refuses vegetables",
    "What should my 10yo daughter eat?",
    "Diet for a child aged 12",
    "Is milk good for my teenage son?",
    "What should teenagers eat?",
    "Food for a 72 month old child",
    "Umwana w'imyaka 15 yarya iki?",
    "umwana wimyaka 10 akwiye kurya iki",
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
    "My 3-year-old won't eat, what can I do?",
    "What should my 5 year old eat?",
    "Food for a 24 month old",
    "My 15 month old has no appetite",
    "My 3-year-old and her 8-year-old brother eat together, what should I cook?",
    "My 16-year-old daughter is pregnant, what should she eat?",
    "Umwana w'imyaka 2 yarya iki?",
    "Umwana w'amezi 15 yarya iki?",
    "umwana wamezi 10 yanywa icyayi?",
]


@pytest.mark.parametrize("question", ADULT_ONLY)
def test_questions_about_adults_only_are_out_of_scope(question):
    assert outside_target_group(question)


@pytest.mark.parametrize("question", IN_SCOPE)
def test_children_pregnancy_births_and_breastfeeding_stay_in_scope(question):
    assert not outside_target_group(question)


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
