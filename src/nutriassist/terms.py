"""Bilingual terms (foods, nutrients, illnesses, health services), shared by matching and translation.

Two uses:

- :class:`KeyTerms` finds which foods, illnesses and numbers a question names, so that two questions
  share a reviewed answer only if these agree (``knowledge.py``).
- :class:`Terminology` keeps these words right in machine translation. NLLB-200 mistranslates local
  food words in both directions (*ikivuguto* "fermented milk" became "spanking"; "fermented milk"
  became *ubuki* "honey"; "breast milk" became *ubuki bw'umubyeyi*), but it keeps a noun of the other
  language in place. So before translating, every known term is replaced by its name in the target
  language. Only nouns are listed for translation: verbs left in the other language confuse NLLB.

Foods come from ``data/reference/food_names_rw.csv``; the other terms are listed below.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

FOOD_NAMES = Path("data/reference/food_names_rw.csv")
_LETTER = "a-zÀ-ɏ"
_COOKING_WORDS = re.compile(r"\b(?:cooked|raw|boiled|baked|canned|roasted|whole grain|in tomato sauce)\b")


@dataclass(frozen=True)
class Term:
    key: str
    english: tuple[str, ...]          # the first name is used when translating into English
    kinyarwanda: tuple[str, ...]      # the first name is used when translating into Kinyarwanda
    topic: bool = True                # a food or illness: part of the matching check
    translate: bool = True            # replaced before translation (nouns only)


# English names first, then Kinyarwanda names; the first of each is the preferred translation.
FOODS = [
    Term("tea", ("tea",), ("icyayi",)),
    Term("coffee", ("coffee",), ("ikawa",)),
    Term("milk", ("milk", "cow's milk"), ("amata", "amata y'inka")),
    Term("soy milk", ("soy milk", "soya milk"), ("amata ya soya",)),
    Term("honey", ("honey",), ("ubuki",)),
    Term("sugar", ("sugar",), ("isukari",)),
    Term("salt", ("salt",), ("umunyu",)),
    Term("oil", ("oil",), ("amavuta",)),
    Term("juice", ("juice",), ("umutobe",)),
    # Before "orange" (the fruit) and "sweet potato", which would otherwise each be replaced alone.
    Term("orange sweet potato", ("orange-fleshed sweet potato", "orange sweet potato"), ("ibijumba by'umuhondo",)),
]
ILLNESSES = [
    Term("fever", ("fever", "temperature"), ("umuriro", "arashyushye")),
    Term("cough", ("cough", "coughing"), ("inkorora",)),
    Term("cold", ("flu",), ("ibicurane",)),          # not "cold": "cold hands" is a danger sign, not a cold
    Term("diarrhoea", ("diarrhoea", "diarrhea"), ("impiswi", "acibwamo")),
    Term("vomiting", ("vomiting", "vomit", "throws up"), ("kuruka", "araruka"), translate=False),
    Term("constipation", ("constipation", "constipated"), ("kwituma impatwe",)),
    Term("malaria", ("malaria",), ("malariya",)),
    Term("anaemia", ("anaemia", "anemia"), ("kubura amaraso",)),
    Term("hiv", ("hiv",), ("virusi itera sida", "sida")),
    Term("measles", ("measles",), ("iseru",)),
    Term("worms", ("intestinal worms", "worms"), ("inzoka zo mu nda",)),
    Term("pneumonia", ("pneumonia",), ("umusonga",)),
]
# Words for translation only: not foods or illnesses, so they do not take part in matching.
GLOSSARY = [
    Term("breast milk", ("breast milk", "breastmilk"), ("amashereka",), topic=False),
    Term("colostrum", ("colostrum",), ("umuhondo",), topic=False),
    Term("iron", ("iron",), ("ubutare",), topic=False),
    Term("protein", ("protein", "proteins"), ("poroteyine",), topic=False),
    Term("vitamin a", ("vitamin A",), ("vitamini A",), topic=False),
    Term("calcium", ("calcium",), ("kalisiyumu",), topic=False),
    Term("health centre", ("health centre", "health center", "health facility"), ("ikigo nderabuzima",), topic=False),
    Term("community health worker", ("community health worker", "community health workers"),
         ("umujyanama w'ubuzima", "abajyanama b'ubuzima"), topic=False),
    Term("growth monitoring", ("growth monitoring",), ("gukurikirana imikurire",), topic=False),
]


def load_terms(path: str | Path = FOOD_NAMES) -> list[Term]:
    terms = [*FOODS, *ILLNESSES, *GLOSSARY]
    with Path(path).open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            kinyarwanda = [n.strip() for n in [*row["rw_aliases"].split(";"), row["rw_name"]] if n.strip()]
            display, _, explained = row["display_en"].partition("(")
            english = [display, row["english_name"], explained.rstrip(")")]
            # "egg boiled" and "boiled egg" are also asked about as just "egg(s)".
            english = [" ".join(_COOKING_WORDS.sub(" ", n).split()) for n in english] + english
            english = [n.strip() for n in english if n.strip()]
            # "isombe (cooked cassava leaves)": the English name is the explanation, not "isombe".
            english.sort(key=lambda n: n.lower() in {k.lower() for k in kinyarwanda})
            # Foods outside the nutrient table (igikoma, isombe...) have no food_id.
            terms.append(Term(row["food_id"] or row["display_en"], tuple(dict.fromkeys(english)),
                              tuple(dict.fromkeys(kinyarwanda))))
    return terms


def _pattern(name: str) -> re.Pattern:
    """Whole words only, with an optional English plural ending."""
    return re.compile(rf"(?<![{_LETTER}]){re.escape(name.lower())}(?:e?s)?(?![{_LETTER}])", re.IGNORECASE)


def _longest_first(pairs):
    return sorted(pairs, key=lambda pair: -len(pair[0]))


@dataclass(frozen=True)
class Found:
    topics: frozenset[str]     # foods and illnesses
    numbers: frozenset[str]

    def agrees_with(self, other: "Found") -> bool:
        """Same foods and illnesses, and no conflicting numbers ("Garama 100 z'ibijumba" still matches "ibijumba")."""
        return self.topics == other.topics and self._numbers_agree(other)

    def fits_within(self, question: "Found") -> bool:
        """Names no food or illness the question does not name, and no conflicting number: a stored question
        on a narrower topic ("tea") can be suggested for a broader one ("eggs and tea"), not on another topic."""
        return self.topics <= question.topics and self._numbers_agree(question)

    def _numbers_agree(self, other: "Found") -> bool:
        return not self.numbers or not other.numbers or self.numbers == other.numbers


NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12,
    "umwe": 1, "rimwe": 1, "kimwe": 1, "abiri": 2, "kabiri": 2, "ibiri": 2, "atatu": 3, "gatatu": 3,
    "itatu": 3, "ane": 4, "kane": 4, "ine": 4, "atanu": 5, "gatanu": 5, "itanu": 5, "atandatu": 6,
    "gatandatu": 6, "arindwi": 7, "umunani": 8, "icyenda": 9, "icumi": 10,
}
_NUMBER = re.compile(rf"\d+(?:[.,]\d+)?|(?<![{_LETTER}])(?:{'|'.join(NUMBER_WORDS)})(?![{_LETTER}])")


class KeyTerms:
    """The foods, illnesses and numbers a question names. Two questions can share an answer only if these agree."""

    def __init__(self, terms: list[Term]) -> None:
        # Longest names first, so "ubunyobwa biseye" (paste) is found before "ubunyobwa" (groundnuts).
        names = {(name, term.key) for term in terms if term.topic for name in (*term.english, *term.kinyarwanda)}
        self._patterns = [(_pattern(name), key) for name, key in _longest_first(names)]

    @classmethod
    def load(cls, path: str | Path = FOOD_NAMES) -> "KeyTerms":
        return cls(load_terms(path))

    def __call__(self, text: str) -> Found:
        text = text.lower().replace("’", "'")
        found = set()
        for pattern, key in self._patterns:
            text, count = pattern.subn(" ", text)
            if count:
                found.add(key)
        numbers = {str(NUMBER_WORDS.get(n, n)).replace(",", ".") for n in _NUMBER.findall(text)}
        return Found(frozenset(found), frozenset(numbers))


class Terminology:
    """Puts the target language's name of every known term into a text before it is machine-translated."""

    def __init__(self, terms: list[Term]) -> None:
        # A term needs a name in both languages to be translated (lentils have no Kinyarwanda name in the table).
        terms = [term for term in terms if term.translate and term.english and term.kinyarwanda]
        to_english = {(name, term.english[0]) for term in terms for name in term.kinyarwanda}
        to_kinyarwanda = {(name, term.kinyarwanda[0]) for term in terms for name in term.english}
        self._replacements = {
            ("rw", "en"): [(_pattern(name), target) for name, target in _longest_first(to_english)],
            ("en", "rw"): [(_pattern(name), target) for name, target in _longest_first(to_kinyarwanda)],
        }

    @classmethod
    def load(cls, path: str | Path = FOOD_NAMES) -> "Terminology":
        return cls(load_terms(path))

    def prepare(self, text: str, source: str, target: str) -> str:
        """``text`` with each known term written in ``target``'s language."""
        text = text.replace("’", "'")
        # Placeholders stop a replacement from being replaced again by a shorter name.
        placed: list[str] = []
        for pattern, name in self._replacements.get((source, target), []):
            def place(_, name=name):
                placed.append(name)
                return f"\x00{len(placed) - 1}\x00"
            text = pattern.sub(place, text)
        return re.sub(r"\x00(\d+)\x00", lambda m: placed[int(m.group(1))], text)
