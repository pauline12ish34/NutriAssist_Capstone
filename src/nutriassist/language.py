"""Tell English from Kinyarwanda in short caregiver messages.

A general-purpose language identifier is overkill here: the app only ever sees
these two languages. Each word is scored against English function words and
against Kinyarwanda function words and noun-class/verb prefixes, and the
language with the higher share of matching words wins. Linear in the number of
words, no model download, and accurate on the questions in our dataset
(checked in ``tests/test_language.py``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

ENGLISH = "en"
KINYARWANDA = "rw"

_ENGLISH_WORDS = frozenset("""
a an the and or but if of to in on at for with from by about as into than then so not no yes
i me my we our you your he she it its they them their his her this that these those there here
is are was were be been being am do does did have has had can could should would will shall may might must
what when where which who whom whose why how much many more most some any all every each
child children baby babies kid son daughter mother mom pregnant breastfeeding food foods eat eating feed
give get make good bad old month months year years day days week weeks per too very also
hello hi thanks thank please okay ok
""".split())

_KINYARWANDA_WORDS = frozenset("""
ni na mu ku kuri ko cyangwa kandi ariko ese iki ibiki ryari gute he nde kuki ngo kugira niba nka
nk buri cyane neza nyuma mbere hanyuma ubu iyo uko ibyo icyo uwo abo ubwo aho ari bari biri iri uri
cy by y w z rw bw tw k ry ny nta ntabwo yego oya muri hamwe bike byinshi gusa hafi
umwana abana uruhinja impinja umubyeyi ababyeyi mama nyina umugore utwite yonsa konsa amashereka
ibiryo indyo amafunguro ifunguro amezi umwaka imyaka umunsi iminsi icyumweru igikoma amata
nshobora ashobora yarya arye agomba ndetse nanone nte
muraho mwaramutse mwiriwe murakoze amakuru afite ifite mfite wanjye wawe
""".split())

# Kinyarwanda noun-class and verb prefixes ("umu-", "aba-", "ibi-", "ku-", ...). A word needs
# at least 3 more letters after the prefix, so short English words like "use" do not match.
_KINYARWANDA_PREFIX = re.compile(
    r"^(?:umu|aba|imi|ama|iki|ibi|icy|iby|aka|utu|uru|ubu|uku|aha|n?ku|gu|ba|bi|ka|tu|ru|bu|yi|zi|ki|cy|ry)"
    r"[a-z']{3,}$"
)
_WORD = re.compile(r"[a-z']+")


@dataclass(frozen=True)
class LanguageGuess:
    language: str           # "en" or "rw"
    confidence: float       # 0.5 (a coin flip) to 1.0 (every scored word agrees)


class LanguageDetector:
    """Classifies a message as English (``"en"``) or Kinyarwanda (``"rw"``)."""

    def __init__(self, default: str = ENGLISH) -> None:
        self.default = default

    def detect(self, text: str) -> LanguageGuess:
        # Elided particles such as "cy'" and "by'" carry the apostrophe; split them off.
        words = [w.strip("'") for w in _WORD.findall(text.lower().replace("'", "' "))]
        words = [w for w in words if w]
        english = sum(w in _ENGLISH_WORDS for w in words)
        kinyarwanda = sum(w in _KINYARWANDA_WORDS or (bool(_KINYARWANDA_PREFIX.match(w)) and w not in _ENGLISH_WORDS)
                          for w in words)
        if english == kinyarwanda:
            return LanguageGuess(self.default, 0.5)
        winner = KINYARWANDA if kinyarwanda > english else ENGLISH
        return LanguageGuess(winner, max(english, kinyarwanda) / (english + kinyarwanda))

    def __call__(self, text: str) -> str:
        return self.detect(text).language
