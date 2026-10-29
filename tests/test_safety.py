import json

import pytest

from conftest import PROCESSED_QA
from nutriassist.assistant import InvalidQuestion, NutritionAssistant, ReplySource
from nutriassist.inference.scripted import ScriptedChatModel
from nutriassist.safety.detector import DangerSignDetector
from nutriassist.safety.rules import SafetyLevel


@pytest.fixture(scope="module")
def detector():
    return DangerSignDetector()


@pytest.fixture(scope="module")
def dataset_questions():
    """(category, question, reference answer) for every question and paraphrase in the dataset."""
    with (PROCESSED_QA / "qa_master.jsonl").open(encoding="utf-8") as f:
        rows = [json.loads(line) for line in f]
    return [(r["category"], q, r["answer"]) for r in rows for q in [r["question"], *r["paraphrases"]]]


class TestDangerSignDetector:
    @pytest.mark.parametrize("message, sign", [
        ("My child is having a seizure", "convulsions"),
        ("Umwana wanjye aragagara. Nkore iki?", "convulsions"),
        ("She is very floppy and won't wake up", "unconscious"),
        ("My baby throws up every feed", "vomits_everything"),
        ("Uruhinja rwanjye ruruka ibintu byose", "vomits_everything"),
        ("My baby can't breastfeed since this morning", "cannot_drink"),
        ("He is breathing very fast", "breathing"),
        ("Umwana arahumeka vuba", "breathing"),
        ("There is blood in her stool", "blood_in_stool"),
        ("Umwana wanjye yituma amaraso", "blood_in_stool"),
        ("Why are my child's legs swollen?", "oedema"),
        ("Ibirenge by'umwana wanjye birabyimbye", "oedema"),
        ("The MUAC tape showed red", "muac_red"),
        ("Agapimo kerekanye ibara ritukura", "muac_red"),
        ("My newborn feels hot", "young_infant_fever"),
        ("My toddler refuses all food for days", "not_eating_for_days"),
        ("Umwana wanjye amaze iminsi ibiri atarya", "not_eating_for_days"),
        ("His skin is peeling", "skin_lesions"),
        ("My child has had diarrhoea for 3 days and is very sleepy and won't drink.", "cannot_drink"),
        ("My child has had diarrhoea for 3 days and is very sleepy and won't drink.", "very_sleepy"),
        ("My baby has a cold and doesn't want to breastfeed", "cannot_drink"),
        ("She is hard to wake this morning", "very_sleepy"),
    ])
    def test_urgent_signs_in_both_languages(self, detector, message, sign):
        result = detector.assess(message)
        assert result.level is SafetyLevel.URGENT
        assert sign in [s.key for s in result.signs]

    @pytest.mark.parametrize("message, sign", [
        ("How much iron syrup should I give my child?", "medicine"),
        ("Ni uwuhe muti naha umwana wanjye?", "medicine"),
        ("Is my child malnourished? She is 2 and weighs 9 kg.", "diagnosis"),
        ("My child has a fever, what should she eat?", "fever"),
        ("Diarrhoea for three weeks, what do I do?", "persistent_diarrhoea"),
    ])
    def test_medical_questions(self, detector, message, sign):
        result = detector.assess(message)
        assert result.level is SafetyLevel.MEDICAL
        assert sign in [s.key for s in result.signs]

    @pytest.mark.parametrize("message", [
        "What foods are rich in iron?",
        "Umwana w'amezi 9 yarya iki?",
        "My child is not vomiting everything, only once after lunch",   # negation
        "What if a mother cannot breastfeed?",                         # the mother, not the child
        "How do I make porridge thicker?",
        "My baby is 5 months old and I can't breastfeed at work",      # the mother, further from "baby"
        "My baby is very sleepy after feeds, is that normal?",
    ])
    def test_ordinary_questions_are_not_flagged(self, detector, message):
        assert detector.assess(message).level is SafetyLevel.NONE

    def test_never_raises_an_urgent_alarm_on_ordinary_dataset_questions(self, detector, dataset_questions):
        alarms = [q for category, q, _ in dataset_questions
                  if category != "safety_redirect" and detector.assess(q).is_urgent]
        assert alarms == []

    def test_most_serious_sign_comes_first(self, detector):
        result = detector.assess("My child has a fever and a seizure")
        assert result.signs[0].level is SafetyLevel.URGENT
        assert result.labels("rw")[0] == "kugagara cyangwa guhinda umushyitsi"

    def test_curly_apostrophes_and_case_are_normalised(self, detector):
        assert detector.assess("MY CHILD CAN’T BREASTFEED").is_urgent


class TestNutritionAssistant:
    def test_urgent_signs_skip_the_model(self):
        model = ScriptedChatModel()
        reply = NutritionAssistant(model).ask("Umwana wanjye aragagara")
        assert model.calls == []
        assert reply.source is ReplySource.SAFETY_RULE
        assert reply.language == "rw" and reply.safety_level == "urgent"
        assert "kigo nderabuzima" in reply.answer and "912" in reply.answer
        assert "kugagara" in reply.answer

    def test_english_urgent_message_names_all_urgent_signs(self):
        reply = NutritionAssistant(ScriptedChatModel()).ask("My baby has blood in the stool and swollen feet")
        assert reply.language == "en"
        assert "blood in the stool and swelling of both feet" in reply.answer

    def test_ordinary_questions_get_the_model_answer_unchanged(self):
        reply = NutritionAssistant(ScriptedChatModel(lambda q: "Give mashed beans.")).ask("What can a 9-month-old eat?")
        assert (reply.answer, reply.source, reply.safety_level) == ("Give mashed beans.", ReplySource.MODEL, "none")

    def test_medicine_doses_from_the_model_are_blocked(self):
        model = ScriptedChatModel(lambda q: "Give 5 ml of paracetamol syrup three times a day.")
        reply = NutritionAssistant(model).ask("How much paracetamol syrup should I give?")
        assert reply.source is ReplySource.DOSE_BLOCKED
        assert "5 ml" not in reply.answer and "health centre" in reply.answer

    def test_missing_referral_is_added_to_medical_answers(self):
        model = ScriptedChatModel(lambda q: "Keep breastfeeding and give fluids.")
        reply = NutritionAssistant(model).ask("My child has a fever, what should she eat?")
        assert reply.source is ReplySource.MODEL_WITH_REFERRAL
        assert reply.answer.startswith("Keep breastfeeding") and "health centre" in reply.answer

    def test_medical_answer_with_a_referral_is_kept(self):
        model = ScriptedChatModel(lambda q: "Take her to the health centre; keep breastfeeding.")
        reply = NutritionAssistant(model).ask("My child has a fever, what should she eat?")
        assert reply.source is ReplySource.MODEL

    @pytest.mark.parametrize("question, lang", [
        ("Is it safe to give honey to my 4 month old baby?", "en"),
        ("Nshobora guha ubuki umwana wanjye w'amezi 4?", "rw"),
    ])
    def test_honey_questions_get_the_fixed_answer(self, question, lang):
        model = ScriptedChatModel(lambda q: "Honey is safe from 1 month.")
        reply = NutritionAssistant(model).ask(question)
        assert model.calls == []
        assert reply.source is ReplySource.SAFETY_RULE and reply.language == lang
        assert "12" in reply.answer and "1 month" not in reply.answer

    def test_honey_note_is_added_when_the_model_leaves_out_the_age_limit(self):
        model = ScriptedChatModel(lambda q: "Sweeten the porridge with a little honey or mashed banana.")
        reply = NutritionAssistant(model).ask("How can I make porridge tastier for my 7-month-old?")
        assert reply.answer.startswith("Sweeten") and "under 12 months" in reply.answer

    def test_honey_note_is_not_repeated_when_the_model_gives_the_age_limit(self):
        answer = "Never give honey before 12 months. Add mashed banana instead."
        reply = NutritionAssistant(ScriptedChatModel(lambda q: answer)).ask("How can I sweeten porridge?")
        assert reply.answer == answer

    @pytest.mark.parametrize("question", ["", "   ", "x" * 1001])
    def test_invalid_questions(self, question):
        with pytest.raises(InvalidQuestion):
            NutritionAssistant(ScriptedChatModel()).ask(question)

    def test_reference_answers_are_never_blocked(self, dataset_questions):
        answers = {q: a for _, q, a in dataset_questions}
        assistant = NutritionAssistant(ScriptedChatModel(answers.get))
        blocked = [q for q in answers if assistant.ask(q).source is ReplySource.DOSE_BLOCKED]
        assert blocked == []
