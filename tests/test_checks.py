"""Topic rules on questions and answers, and the scope and answer-relevance checks."""

import pytest

from nutriassist.assistant import NutritionAssistant, ReplySource
from nutriassist.inference.scripted import ScriptedChatModel
from nutriassist.knowledge import KnowledgeBase, ReviewedPair
from nutriassist.safety import messages
from nutriassist.safety.topics import TopicRules


class FakeChecker:
    """Stands in for RelevanceChecker (LaBSE): fixed answers to the two checks."""

    def __init__(self, in_scope=True, on_topic=True):
        self._in_scope, self._on_topic = in_scope, on_topic
        self.answer_checks = []

    def in_scope(self, question):
        return self._in_scope

    def on_topic(self, question, answer):
        self.answer_checks.append((question, answer))
        return self._on_topic


class FakeTranslator:
    name = "fake-mt"

    def __init__(self):
        self.calls = []

    def translate(self, texts, source, target):
        self.calls.append((source, target))
        return [f"[{target}] {t}" for t in texts]


def knowledge():
    pair = ReviewedPair("p", "rw", "c", "Nshobora guha ikawa umwana wanjye muto?", "Oya.")
    return KnowledgeBase([(pair, [pair.question])])


@pytest.mark.parametrize("question", [
    "Uruhinja rwanjye rwanywa icyai?", "Umwana w'umwaka umwe yahabwa chai?", "Ese nshobora guha akana kanjye icyayi?",
    "Is tea ok at 9 months?", "Can my little one have a cup of tea?", "Ese icyayi ni kibi ku bana?",
])
def test_tea_rewordings_that_slipped_past_the_first_rule_are_caught(question):
    assert TopicRules().for_question(question).key == "tea"


def test_tea_for_a_mother_is_not_a_child_rule():
    assert TopicRules().for_question("Ese umugore utwite yanywa icyayi?") is None


def test_a_model_answer_about_tea_for_a_child_is_replaced():
    model = ScriptedChatModel(lambda q: "Yego. Icyayi cyuzuza umubiri n'amavuta.")
    reply = NutritionAssistant(model).ask("Umwana w'amezi 10 yanywa iki?")
    assert reply.source is ReplySource.TOPIC_REPLACED and reply.answer == messages.TEA["rw"]


def test_a_model_answer_mentioning_honey_without_the_age_limit_gets_the_honey_message_added():
    model = ScriptedChatModel(lambda q: "Sweeten the porridge with honey.")
    reply = NutritionAssistant(model).ask("How can I make porridge tastier for my baby?")
    assert reply.answer.startswith("Sweeten") and reply.answer.endswith(messages.HONEY["en"])


def test_out_of_scope_questions_are_declined_without_the_model():
    model = ScriptedChatModel(lambda q: "Restart the phone.")
    reply = NutritionAssistant(model, checker=FakeChecker(in_scope=False)).ask("How do I fix my phone screen?")
    assert reply.source is ReplySource.OUT_OF_SCOPE and reply.answer == messages.OUT_OF_SCOPE["en"]
    assert model.calls == []


def test_danger_signs_come_before_the_scope_check():
    reply = NutritionAssistant(ScriptedChatModel(), checker=FakeChecker(in_scope=False)).ask("Umwana wanjye aragagara")
    assert reply.source is ReplySource.SAFETY_RULE


def test_an_off_topic_answer_is_not_shown():
    model = ScriptedChatModel(lambda q: "Breastfeed every 2 to 3 hours.")
    reply = NutritionAssistant(model, knowledge=knowledge(), checker=FakeChecker(on_topic=False)).ask(
        "What foods help my child have enough blood?")
    assert reply.source is ReplySource.OFF_TOPIC and "Breastfeed" not in reply.answer
    assert reply.answer in (messages.NO_MATCH["en"], messages.NO_MATCH_NO_SUGGESTIONS["en"])


def test_in_the_translation_route_the_check_runs_in_english_before_translating_back():
    translator, checker = FakeTranslator(), FakeChecker(on_topic=False)
    assistant = NutritionAssistant(ScriptedChatModel(lambda q: "Breastfeed often."), knowledge=knowledge(),
                                   translator=translator, checker=checker)
    reply = assistant.ask("Ni ibihe biryo bifasha umwana kugira amaraso ahagije?")
    assert reply.source is ReplySource.OFF_TOPIC and not reply.translated
    assert translator.calls == [("rw", "en")]                      # no second request to translate the answer back
    assert checker.answer_checks == [("[en] Ni ibihe biryo bifasha umwana kugira amaraso ahagije?", "Breastfeed often.")]


class EnglishOnlyScope(FakeChecker):
    """In scope only once translated: the informal Kinyarwanda spelling scores too low in LaBSE."""

    def __init__(self):
        super().__init__()
        self.scope_checks = []

    def in_scope(self, question):
        self.scope_checks.append(question)
        return question.startswith("[en]")


def test_a_translated_question_is_checked_for_scope_in_english():
    checker = EnglishOnlyScope()
    assistant = NutritionAssistant(ScriptedChatModel(lambda q: "Yes, with a little oil."), knowledge=knowledge(),
                                   translator=FakeTranslator(), checker=checker)
    reply = assistant.ask("Ese amakaroni nimeza kumwana wimyaka 2?")
    assert reply.source is ReplySource.MODEL and reply.translated
    assert checker.scope_checks == ["[en] Ese amakaroni nimeza kumwana wimyaka 2?"]


def test_a_translated_question_out_of_scope_in_english_is_declined_without_the_model():
    model = ScriptedChatModel(lambda q: "Restart the phone.")
    translator = FakeTranslator()
    reply = NutritionAssistant(model, knowledge=knowledge(), translator=translator,
                               checker=FakeChecker(in_scope=False)).ask("Nakora iki ngo telefoni yanjye yongere ikore?")
    assert reply.source is ReplySource.OUT_OF_SCOPE and reply.answer == messages.OUT_OF_SCOPE["rw"]
    assert model.calls == [] and translator.calls == [("rw", "en")]


def test_a_question_naming_a_known_food_is_in_scope_even_with_a_low_score():
    from nutriassist.terms import KeyTerms, Term
    kb = knowledge()
    kb.key_terms = KeyTerms([Term("cabbage", ("cabbage",), ("amashu",))])
    model = ScriptedChatModel(lambda q: "Yes, cook it soft.")
    reply = NutritionAssistant(model, knowledge=kb, checker=FakeChecker(in_scope=False)).ask(
        "I give the child pasta and cabbage")
    assert reply.source is ReplySource.MODEL


def test_scope_needs_a_domain_word_unless_very_close():
    import numpy as np
    from nutriassist.safety.relevance import RelevanceChecker

    def embedder(texts):   # every question scores 0.6 against the one reviewed question
        return np.array([[1.0, 0.0] if t == "reviewed" else [0.6, 0.8] for t in texts])

    checker = RelevanceChecker(embedder, ["reviewed"])
    assert checker.in_scope("I give the child rice")                       # domain word, 0.6 >= 0.50
    assert checker.in_scope("Naha umwana umuceri")
    assert not checker.in_scope("When will the elections be held in Rwanda?")  # no domain word, 0.6 < 0.75


def test_on_topic_answers_pass_unchanged():
    reply = NutritionAssistant(ScriptedChatModel(lambda q: "Give beans and dark green leaves."),
                               checker=FakeChecker()).ask("What foods help my child have enough blood?")
    assert reply.source is ReplySource.MODEL and reply.answer == "Give beans and dark green leaves."


@pytest.mark.parametrize("output", ["", "   ", "感冒"])
def test_an_empty_model_answer_is_declined_as_out_of_scope(output):
    """On the live Space (checks off) an empty generation was shown as a blank answer under the AI label."""
    reply = NutritionAssistant(ScriptedChatModel(lambda q: output)).ask("What foods are good for my baby?")
    assert reply.source is ReplySource.OUT_OF_SCOPE and reply.answer == messages.OUT_OF_SCOPE["en"]


def test_an_empty_model_answer_in_kinyarwanda_is_declined_before_translating_back():
    translator = FakeTranslator()
    reply = NutritionAssistant(ScriptedChatModel(lambda q: ""), translator=translator).ask(
        "Ni ibihe biryo nagaburira umwana wanjye w'amezi 8?")
    assert reply.source is ReplySource.OUT_OF_SCOPE and reply.answer == messages.OUT_OF_SCOPE["rw"]
    assert translator.calls == [("rw", "en")]
