"""Who is the question about? The app is for children under 5 and for pregnant and breastfeeding mothers.

Questions about a grandmother, a husband or an elderly person reached the model on the live Space and got
an answer, because they use the domain's words ("What should my grandma eat?") and the meaning-based scope
check (LaBSE, :mod:`.relevance`) is off there. This check needs no model: a question that names an adult and
no child, pregnancy or breastfeeding is out of scope, and the model is never called.

It is deliberately narrow: a question that also names a child ("my grandmother gives the baby tea"), a
pregnancy, a recent birth or breastfeeding ("my wife just gave birth, what should she eat?") is left to the
other checks, so mothers stay in scope and a caregiver is never refused because a relative is mentioned.
"""

from __future__ import annotations

import re

_ADULT_EN = (
    r"grand(?:ma|mas|mother|mothers|pa|pas|father|fathers|parents?)|granny|grannies|nana|"
    r"elderly|old (?:man|men|woman|women|people|person|age)|aged (?:man|woman|people|person|parents?)|"
    r"seniors?|pensioners?|adults?|grown[- ]ups?|teen(?:ager)?s?|husband|wife|"
    r"(?:my|our|his|her) (?:dad|father|mum|mom|mother|parents?|brother|sister|uncle|aunt(?:ie)?|neighbou?r|boss|"
    r"mother[- ]in[- ]law|father[- ]in[- ]law)|"
    r"\d{2,3}[- ]years?[- ]old"
)
# NEEDS REVIEW: Kinyarwanda words drafted by Claude, not yet checked by a native speaker.
_ADULT_RW = (
    r"nyogokuru|sogokuru|nyokokuru|sokokuru|nyirakuru|sekuru|umukecuru|abakecuru|umusaza|abasaza|"
    r"abakuze|umuntu mukuru|abantu bakuru|umugabo wanjye|umugore wanjye|mama wanjye|papa wanjye"
)
_ADULT = re.compile(rf"\b(?:{_ADULT_EN}|{_ADULT_RW})\b", re.IGNORECASE)

_IN_SCOPE_EN = (
    r"child|children|childs?|baby|babies|infants?|toddlers?|newborns?|kids?|son|sons|daughters?|"
    r"grand(?:child|children|son|sons|daughter|daughters|kids?|baby)|"
    r"pregnan\w*|expecting|breast\w*|lactat\w*|nursing|maternal|maternity|mothers? and babies|"
    r"(?:post|ante|pre)[- ]?(?:partum|natal)|(?:gave|given|giving|give) birth|delivered|after delivery|"
    r"new (?:mums?|moms?|mothers?)|"
    r"\d{1,2}[- ]?months?(?:[- ]old)?|(?:[1-5]|one|two|three|four|five)[- ]years?[- ]old|under (?:5|five)"
)
# NEEDS REVIEW: Kinyarwanda words drafted by Claude, not yet checked by a native speaker.
_IN_SCOPE_RW = (
    r"umwana|abana|umwana\w*|uruhinja|impinja|akana|utwana|umwuzukuru|abuzukuru|amezi|"
    r"utwite|atwite|batwite|gutwita|konsa|yonsa|bonsa|onsa|amashereka|"
    r"umubyeyi|ababyeyi|kubyara|yabyaye|wabyaye|nabyaye|babyaye"
)
_IN_SCOPE = re.compile(rf"\b(?:{_IN_SCOPE_EN}|{_IN_SCOPE_RW})\b", re.IGNORECASE)


def is_about_adult_only(question: str) -> bool:
    """True when the question names an adult and no child, pregnancy or breastfeeding."""
    return bool(_ADULT.search(question)) and not _IN_SCOPE.search(question)
