"""Reviewed answers: matching, the food/number check, and how the assistant uses them with translation."""

import json

import numpy as np
import pytest

pytest.importorskip("sklearn")

from nutriassist.assistant import NutritionAssistant, ReplySource  # noqa: E402
from nutriassist.inference.scripted import ScriptedChatModel  # noqa: E402
from nutriassist.knowledge import KnowledgeBase, ReviewedPair, load_pairs  # noqa: E402
from nutriassist.prompts import build_grounded_messages, build_messages  # noqa: E402
from nutriassist.terms import KeyTerms, Terminology  # noqa: E402
from nutriassist.translation import TermAwareTranslator, apply_glossary, split_sentences, translate_text  # noqa: E402


@pytest.fixture(scope="module")
def key_terms():
    return KeyTerms.load()


@pytest.fixture(scope="module")
def knowledge():
    return KnowledgeBase.load()


def pair(question, answer, lang="rw", id="p"):
    return ReviewedPair(id, lang, "local_foods", question, answer)


class FakeTranslator:
    """Tags text with the target language, so tests can see each translation step."""

    name = "fake-mt"

    def __init__(self):
        self.calls = []

    def translate(self, texts, source, target):
        self.calls.append((source, target, list(texts)))
        return [f"[{target}] {text}" for text in texts]


class TestKeyTerms:
    def test_names_in_both_languages_map_to_one_food(self, key_terms):
        assert key_terms("Can I give my baby eggs?").topics == key_terms("Nshobora guha umwana amagi?").topics != set()

    def test_longer_names_are_kept_apart(self, key_terms):
        assert key_terms("ubunyobwa biseye").topics != key_terms("ubunyobwa").topics
        assert key_terms("inyama y'inka itetse").topics != key_terms("inyama y'inkoko itetse").topics

    def test_foods_outside_the_nutrient_table(self, key_terms):
        assert key_terms("Ikivuguto ni cyiza?").topics and key_terms("Is isombe good?").topics

    def test_numbers_as_digits_and_words(self, key_terms):
        assert key_terms("Umwana w'umwaka umwe").numbers == {"1"}
        assert key_terms("my nine month old").numbers == key_terms("amezi 9").numbers == {"9"}

    def test_number_words_inside_other_words_are_ignored(self, key_terms):
        assert key_terms("Umwana wanjye ararwaye").numbers == set()

    def test_agreement(self, key_terms):
        assert key_terms("Garama 100 z'ibijumba zirimo iki?").agrees_with(key_terms("Ibijumba birimo iki?"))
        assert not key_terms("Umwana w'amezi 9 arya kangahe?").agrees_with(key_terms("Umwana w'umwaka umwe arya kangahe?"))


class TestKnowledgeBase:
    def test_exact_question_returns_its_reviewed_answer(self, knowledge):
        match = knowledge.find("Nshobora guha icyayi umwana wanjye muto?", "rw")
        assert match is not None and match.score > 0.99 and "icyayi" in match.pair.answer

    def test_only_searches_the_question_language(self, knowledge):
        match = knowledge.best("Nshobora guha icyayi umwana wanjye muto?", "en")
        assert match.pair.lang == "en"

    def test_same_template_with_another_food_is_not_matched(self):
        kb = KnowledgeBase([(pair("Garama 100 z'ibirayi bitetse zirimo iki?", "Ibirayi: 94 kcal."), ["Garama 100 z'ibirayi bitetse zirimo iki?"])],
                           key_terms=KeyTerms.load())
        assert kb.best("Garama 100 z'ibijumba bitetse zirimo iki?", "rw") is None

    def test_weak_matches_are_left_to_the_model(self, knowledge):
        assert knowledge.find("Ni ryari nzajya mu isoko rya Kimironko?", "rw") is None

    def test_meaning_in_the_other_language_finds_the_pair(self):
        # A toy embedder: one dimension per topic, the same in both languages.
        topics = {"tea": ["tea", "icyayi"], "iron": ["iron", "ubutare", "amaraso"]}

        def embed(texts):
            rows = np.array([[float(any(w in t.lower() for w in words)) for words in topics.values()] for t in texts])
            return rows / np.maximum(np.linalg.norm(rows, axis=1, keepdims=True), 1e-9)

        tea = ReviewedPair("t-rw", "rw", "c", "Nshobora guha icyayi?", "Oya.", group="tea")
        iron = ReviewedPair("i-rw", "rw", "c", "Ni ibihe biryo bifite ubutare?", "Ibishyimbo.", group="iron")
        iron_en = ReviewedPair("i-en", "en", "c", "Which foods have iron?", "Beans.", group="iron")
        kb = KnowledgeBase([(tea, [tea.question]), (iron, [iron.question]), (iron_en, [iron_en.question])],
                           embedder=embed, letters_weight=0.0)
        assert kb.suggest("Ni ibihe biryo byongera amaraso?", "rw", k=1, min_score=0.0)[0].pair is iron

    def test_evaluation_can_leave_out_held_out_pairs_and_paraphrases(self):
        train_only = load_pairs(splits={"train"})
        assert train_only and all(len(wordings) >= 1 for _, wordings in train_only)
        no_paraphrases = load_pairs(paraphrase_splits=[])
        assert all(len(wordings) == 1 for _, wordings in no_paraphrases)


class TestTranslation:
    def test_sentences_are_split_on_end_punctuation_and_lines(self):
        assert split_sentences("Give milk. Then beans!\nKeep going?  ") == ["Give milk.", "Then beans!", "Keep going?"]

    def test_glossary_fixes_known_mistranslations(self):
        text = "Icyayi gihagarika umubiri gufata icyuma. Amata y'umubyeyi ni meza."
        assert apply_glossary(text) == "Icyayi gihagarika umubiri gufata ubutare. Amashereka ni meza."

    def test_glossary_only_replaces_whole_words(self):
        assert apply_glossary("ibyuma") == "ibyuma"

    def test_translates_each_sentence_in_one_batch(self):
        translator = FakeTranslator()
        assert translate_text(translator, "One. Two.", "en", "rw") == "[rw] One. [rw] Two."
        assert translator.calls == [("en", "rw", ["One.", "Two."])]

    def test_whole_text_translators_get_the_text_in_one_piece(self):
        translator = FakeTranslator()
        translator.whole_text = True
        assert translate_text(translator, "- One.\n- Two.", "en", "rw") == "[rw] - One.\n- Two."
        assert translator.calls == [("en", "rw", ["- One.\n- Two."])]


class TestAssistantWithReviewedAnswers:
    def make(self, translator=None, responder=lambda q: "Give mashed beans."):
        model = ScriptedChatModel(responder)
        kb = KnowledgeBase([(pair("Nshobora guha icyayi umwana wanjye muto?", "Oya, icyayi si cyiza ku bana bato."),
                             ["Nshobora guha icyayi umwana wanjye muto?"])], key_terms=KeyTerms.load())
        return NutritionAssistant(model, knowledge=kb, translator=translator), model

    def test_matching_question_gets_the_reviewed_answer_without_the_model(self):
        assistant, model = self.make()
        reply = assistant.ask("Nshobora guha icyayi umwana wanjye muto?")
        assert reply.source is ReplySource.REVIEWED and reply.answer.startswith("Oya")
        assert reply.matched_question and reply.model_name == "reviewed answers" and model.calls == []

    def test_unmatched_kinyarwanda_is_answered_in_english_and_translated_back(self):
        translator = FakeTranslator()
        assistant, model = self.make(translator)
        reply = assistant.ask("Umwana w'amezi 9 yarya iki?")
        assert model.calls == ["[en] Umwana w'amezi 9 yarya iki?"]
        assert reply.answer == "[rw] Give mashed beans." and reply.translated and reply.language == "rw"
        assert reply.model_name == "scripted + fake-mt"

    def test_unmatched_english_goes_straight_to_the_model(self):
        translator = FakeTranslator()
        assistant, model = self.make(translator)
        reply = assistant.ask("What can my 9-month-old eat?")
        assert reply.answer == "Give mashed beans." and not reply.translated and translator.calls == []

    def test_urgent_signs_still_come_first(self):
        assistant, model = self.make(FakeTranslator())
        reply = assistant.ask("Umwana wanjye aragagara")
        assert reply.source is ReplySource.SAFETY_RULE and model.calls == []

    def test_a_failed_translator_offers_reviewed_questions_instead_of_an_error(self):
        class BusyTranslator(FakeTranslator):
            def translate(self, texts, source, target):
                raise ConnectionError("503 UNAVAILABLE")

        assistant, model = self.make(BusyTranslator())
        reply = assistant.ask("Nshobora guha umwana wanjye icyayi n'amata?")
        assert reply.source is ReplySource.NO_MATCH and not reply.translated and model.calls == []
        assert reply.suggestions == ["Nshobora guha icyayi umwana wanjye muto?"]

    def test_grounding_puts_the_closest_reviewed_pairs_in_the_prompt(self):
        class RecordingModel(ScriptedChatModel):
            def generate_batch(self, conversations):
                self.prompts = [list(c) for c in conversations]
                return super().generate_batch(conversations)

        model = RecordingModel(lambda q: "Oya, ntukamuhe icyayi.")
        kb = KnowledgeBase([(pair("Nshobora guha icyayi umwana wanjye muto?", "Oya, icyayi si cyiza ku bana bato."),
                             ["Nshobora guha icyayi umwana wanjye muto?"])], key_terms=KeyTerms.load())
        reply = NutritionAssistant(model, knowledge=kb, grounding=3).ask("Icyayi cyaba kibi ku mwana w'amezi 7?")
        system = model.prompts[0][0]["content"]
        assert reply.source is ReplySource.MODEL and "Oya, icyayi si cyiza ku bana bato." in system
        assert model.prompts[0][1] == {"role": "user", "content": "Icyayi cyaba kibi ku mwana w'amezi 7?"}

    def test_without_grounding_the_prompt_is_the_trained_one(self):
        assert build_grounded_messages("Q?", []) == build_messages("Q?")

    def test_doses_in_translated_answers_are_still_blocked(self):
        assistant, _ = self.make(FakeTranslator(), responder=lambda q: "Give 5 ml of paracetamol.")
        reply = assistant.ask("Umwana wanjye afite umuriro, namuha umuti ungana iki?")
        assert reply.source is ReplySource.DOSE_BLOCKED


def test_different_illnesses_do_not_share_an_answer(key_terms):
    assert not key_terms("My child has a cough, what should I feed him?").agrees_with(
        key_terms("My baby has a fever. What should I feed him?"))
    assert key_terms("Umwana wanjye afite umuriro").agrees_with(key_terms("my baby has a fever"))


@pytest.fixture(scope="module")
def terms():
    return Terminology.load()


class TestTerminology:
    @pytest.mark.parametrize("text, expected", [
        ("Ikivuguto ni cyiza ku bana?", "fermented milk ni cyiza ku bana?"),
        ("Isombe ni nziza ku mwana?", "cassava leaves ni nziza ku mwana?"),
        ("Garama 100 z'ubunyobwa biseye zirimo iki?", "Garama 100 z'groundnut paste zirimo iki?"),
    ])
    def test_kinyarwanda_food_names_become_english_before_translation(self, terms, text, expected):
        assert terms.prepare(text, "rw", "en") == expected

    def test_english_terms_become_kinyarwanda_before_translation(self, terms):
        prepared = terms.prepare("Breast milk and fermented milk. Go to the health centre for iron.", "en", "rw")
        assert prepared == "amashereka and ikivuguto. Go to the ikigo nderabuzima for ubutare."

    def test_a_longer_name_wins_and_is_not_replaced_again(self, terms):
        assert terms.prepare("Orange sweet potato", "en", "rw") == "ibijumba by'umuhondo"

    def test_honey_renderings_of_breast_milk_are_fixed(self):
        assert apply_glossary("Ubuki bw'umubyeyi burinda umwana.") == "Amashereka burinda umwana."

    def test_wrapper_prepares_every_text(self, terms):
        inner = FakeTranslator()
        TermAwareTranslator(inner, terms).translate(["Ikivuguto ni cyiza?"], "rw", "en")
        assert inner.calls == [("rw", "en", ["fermented milk ni cyiza?"])]


def test_chinese_characters_are_removed_from_model_answers():
    assistant = NutritionAssistant(ScriptedChatModel(lambda q: "Common colds (感冒) need fluids."))
    assert assistant.ask("What helps a cold?").answer == "Common colds need fluids."


class TestReviewedOnlyKinyarwanda:
    """The app shows Kinyarwanda only from reviewed answers: no match means suggestions, never model text."""

    def make(self):
        model = ScriptedChatModel(lambda q: "Ibitoki by'umwembe, ibitoki by'umwembe")
        return NutritionAssistant(model, knowledge=KnowledgeBase.load(), reviewed_only={"rw"}), model

    def test_unmatched_kinyarwanda_gets_suggestions_and_never_the_model(self):
        assistant, model = self.make()
        reply = assistant.ask("Nakongera nte ubutare mu biryo by'umwana?")
        assert reply.source is ReplySource.NO_MATCH and model.calls == []
        assert reply.suggestions and "Nta gisubizo cyagenzuwe" in reply.answer
        assert "Ni ibihe biryo byo mu Rwanda bikungahaye ku butare?" in reply.suggestions

    def test_a_tapped_suggestion_gets_its_reviewed_answer(self):
        assistant, model = self.make()
        suggestion = assistant.ask("Nakongera nte ubutare mu biryo by'umwana?").suggestions[0]
        reply = assistant.ask(suggestion)
        assert reply.source is ReplySource.REVIEWED and model.calls == []

    def test_no_suggestions_for_unrelated_questions(self):
        assistant, _ = self.make()
        reply = assistant.ask("Ese ejo hazagwa imvura i Kigali?")
        assert reply.source is ReplySource.NO_MATCH and reply.suggestions == []
        assert "umujyanama w'ubuzima" in reply.answer

    def test_english_still_goes_to_the_model(self):
        assistant, model = self.make()
        assistant.ask("Can my baby eat mashed avocado and rice together?")
        assert model.calls

    def test_urgent_signs_still_come_first(self):
        assistant, model = self.make()
        assert assistant.ask("Umwana wanjye aragagara").source is ReplySource.SAFETY_RULE and model.calls == []

    def test_needs_reviewed_answers(self):
        with pytest.raises(ValueError):
            NutritionAssistant(ScriptedChatModel(), reviewed_only={"rw"})


def test_suggestions_are_different_pairs_with_matching_foods_first(knowledge):
    suggestions = knowledge.suggest("Nshobora guha umwana wanjye amagi?", "rw")
    assert len({s.pair.id for s in suggestions}) == len(suggestions) <= 3
    assert "ig" in suggestions[0].pair.question.lower() or "amagi" in suggestions[0].pair.question.lower()


def test_approved_extra_wordings_are_indexed_but_never_a_held_out_paraphrase(tmp_path):
    master = [json.loads(line) for line in open("data/QA_data/processed/qa_master.jsonl", encoding="utf-8")]
    test_pair = next(r for r in master if r["split"] == "test" and r["lang"] == "rw" and r["paraphrases"])
    extra = tmp_path / "extra.jsonl"
    extra.write_text(json.dumps({"id": test_pair["id"], "wordings": ["Ikibazo gishya cyanditswe ukundi?",
                                                                     test_pair["paraphrases"][0]]}), encoding="utf-8")
    deployed = dict((p.id, w) for p, w in load_pairs(extra_wordings=extra))
    evaluation = dict((p.id, w) for p, w in load_pairs(paraphrase_splits={"train"}, extra_wordings=extra))
    assert "Ikibazo gishya cyanditswe ukundi?" in deployed[test_pair["id"]]
    assert "Ikibazo gishya cyanditswe ukundi?" in evaluation[test_pair["id"]]
    assert test_pair["paraphrases"][0] not in evaluation[test_pair["id"]]


def test_approved_gemini_question_wordings_are_matched(tmp_path):
    from nutriassist.knowledge import DEFAULT_THRESHOLD

    master = [json.loads(line) for line in open("data/QA_data/processed/qa_master.jsonl", encoding="utf-8")]
    pair = next(r for r in master if r["split"] == "train" and r["lang"] == "rw")
    augmented = tmp_path / "augmented.jsonl"
    wording = "Ese mbere y'amezi atandatu umwana yanywa utuzi duke?"
    augmented.write_text(json.dumps({"id": pair["id"], "questions": [wording], "answers": ["Igisubizo."]}),
                         encoding="utf-8")
    assert wording in dict((p.id, w) for p, w in load_pairs(augmented=augmented))[pair["id"]]
    knowledge = KnowledgeBase(load_pairs(augmented=augmented), threshold=DEFAULT_THRESHOLD)
    assert knowledge.find(wording, "rw").pair.id == pair["id"]
