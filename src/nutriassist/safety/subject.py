"""Who is the question about? The app is for children under 5 and for pregnant and breastfeeding mothers.

Questions about a grandmother, a husband, an elderly person or an older child ("food for a 15-year-old
child") reached the model on the live app and got an answer, because they use the domain's words and the
meaning-based scope check (LaBSE, :mod:`.relevance`) is off there. This check needs no model, so the model
is never called for them:

- **pregnancy, a recent birth or breastfeeding** in the question: always in scope (a pregnant teenager too);
- **an age of 6 years or more** (or 60 months or more), or a teenager, with no age under that: out of scope,
  even when the question says "child";
- **an adult** (grandmother, husband, elderly person) and no young child: out of scope.

Anything else is left to the other checks. A question that also names a young child ("my grandmother gives
the baby tea") stays in scope, so a caregiver is never refused because a relative is mentioned. Age 5 is
let through: a parent may say "5 years" for a child just under it.
"""

from __future__ import annotations

import re

MAX_AGE_YEARS = 5          # ages above this are out of scope
MAX_AGE_MONTHS = 59

_MOTHER = re.compile(
    r"\b(?:pregnan\w*|expecting|breast\w*|lactat\w*|nursing|maternal|maternity|"
    r"(?:post|ante|pre)[- ]?(?:partum|natal)|(?:gave|given|giving|give) birth|delivered|after delivery|"
    r"new (?:mums?|moms?|mothers?)|"
    # NEEDS REVIEW: Kinyarwanda words drafted by Claude, not yet checked by a native speaker.
    r"utwite|atwite|batwite|gutwita|konsa|yonsa|bonsa|onsa|amashereka|"
    r"umubyeyi|ababyeyi|kubyara|yabyaye|wabyaye|nabyaye|babyaye)\b", re.IGNORECASE)

_YOUNG_CHILD = re.compile(
    r"\b(?:baby|babies|infants?|toddlers?|newborns?|under (?:5|five)|"
    # NEEDS REVIEW: Kinyarwanda words drafted by Claude, not yet checked by a native speaker.
    r"uruhinja|impinja|akana|utwana)\b", re.IGNORECASE)

_CHILD = re.compile(
    r"\b(?:child|children|childs?|kids?|son|sons|daughters?|"
    r"grand(?:child|children|son|sons|daughter|daughters|kids?|baby)|"
    # NEEDS REVIEW: Kinyarwanda words drafted by Claude, not yet checked by a native speaker.
    r"umwana\w*|abana|umwuzukuru|abuzukuru)\b", re.IGNORECASE)

_ADULT = re.compile(
    r"\b(?:grand(?:ma|mas|mother|mothers|pa|pas|father|fathers|parents?)|granny|grannies|nana|"
    r"elderly|old (?:man|men|woman|women|people|person|age)|aged (?:man|woman|people|person|parents?)|"
    r"seniors?|pensioners?|adults?|grown[- ]ups?|husband|wife|"
    r"(?:my|our|his|her) (?:dad|father|mum|mom|mother|parents?|brother|sister|uncle|aunt(?:ie)?|neighbou?r|boss|"
    r"mother[- ]in[- ]law|father[- ]in[- ]law)|"
    # NEEDS REVIEW: Kinyarwanda words drafted by Claude, not yet checked by a native speaker.
    r"nyogokuru|sogokuru|nyokokuru|sokokuru|nyirakuru|sekuru|umukecuru|abakecuru|umusaza|abasaza|"
    r"abakuze|umuntu mukuru|abantu bakuru|umugabo wanjye|umugore wanjye|mama wanjye|papa wanjye)\b",
    re.IGNORECASE)

_TEEN = re.compile(r"\b(?:teen(?:age|ager|agers)?s?|adolescen\w*|ingimbi|abangavu|umwangavu)\b", re.IGNORECASE)

_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
            "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
            "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
            # NEEDS REVIEW: Kinyarwanda numbers drafted by Claude.
            "itandatu": 6, "irindwi": 7, "umunani": 8, "icyenda": 9, "icumi": 10}
_NUMBER = r"(\d{1,3}|" + "|".join(_NUMBERS) + r")"
_YEARS = [re.compile(p, re.IGNORECASE) for p in (
    r"\b" + _NUMBER + r"\s*-?\s*(?:years?|yrs?|y/?o)\b",   # 15 years old, 15-year-old, 15 yrs, 15yo
    r"\baged?\s+" + _NUMBER + r"\b",                         # aged 15, age 15
    r"imyaka\s*" + _NUMBER + r"\b",                          # imyaka 15, w'imyaka 15, wimyaka 15 (joined)
)]
_MONTHS = [re.compile(p, re.IGNORECASE) for p in (
    r"\b" + _NUMBER + r"\s*-?\s*(?:months?|mos?)\b",
    r"amezi\s*" + _NUMBER + r"\b",                           # amezi 8, w'amezi 8, wamezi 8 (joined)
)]


def _value(text: str) -> int:
    return int(text) if text.isdigit() else _NUMBERS[text.lower()]


def ages(question: str) -> tuple[list[int], list[int]]:
    """The ages the question gives, in years and in months ("15-year-old" -> ([15], []), "amezi 8" -> ([], [8]))."""
    years = [_value(m.group(1)) for p in _YEARS for m in p.finditer(question)]
    months = [_value(m.group(1)) for p in _MONTHS for m in p.finditer(question)]
    return years, months


def outside_target_group(question: str) -> bool:
    """True when the question is about someone the app is not for: an adult, an older child or a teenager."""
    if _MOTHER.search(question):
        return False
    years, months = ages(question)
    young_age = any(y <= MAX_AGE_YEARS for y in years) or any(m <= MAX_AGE_MONTHS for m in months)
    if young_age or _YOUNG_CHILD.search(question):
        return False
    if years or months or _TEEN.search(question):   # an age, none of them under 6: an older child or an adult
        return True
    return bool(_ADULT.search(question)) and not _CHILD.search(question)
