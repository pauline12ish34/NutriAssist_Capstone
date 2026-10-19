import pytest

from nutriassist.language import LanguageDetector


@pytest.fixture(scope="module")
def detector():
    return LanguageDetector()


def test_detects_every_dataset_text_in_its_labelled_language(detector, qa_dataset):
    texts = [(ex.lang, text) for examples in qa_dataset.splits().values() for ex in examples
             for text in (ex.question, ex.answer)]
    wrong = [(lang, text) for lang, text in texts if detector(text) != lang]
    assert len(wrong) / len(texts) < 0.01, wrong[:5]


@pytest.mark.parametrize("text, expected", [
    ("What can my 9-month-old eat?", "en"),
    ("Umwana wanjye w'amezi 9 yarya iki?", "rw"),
    ("Muraho", "rw"),
    ("Hello", "en"),
    ("Can I give my baby ubugali?", "en"),        # code-switching: mostly English
    ("Igikoma cy'amasaka gifite iki?", "rw"),
])
def test_short_messages(detector, text, expected):
    assert detector(text) == expected


def test_no_evidence_falls_back_to_default_with_low_confidence():
    guess = LanguageDetector(default="rw").detect("123 ???")
    assert guess.language == "rw"
    assert guess.confidence == 0.5


def test_confidence_reflects_agreement(detector):
    assert detector.detect("the child and the mother").confidence == 1.0
