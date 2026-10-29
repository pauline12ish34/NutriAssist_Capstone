"""Danger-sign and medical-question rules in English and Kinyarwanda.

The urgent signs follow the WHO/IMCI general danger signs and the signs of severe
acute malnutrition that Rwanda's community health workers refer on. Phrasings
come from the questions caregivers ask in our dataset (see ``tests/test_safety.py``,
which checks the rules against every dataset question).

A rule matches when **every** pattern group in ``all_of`` matches somewhere in the
message. Most rules have one group; combinations such as "baby under 2 months"
+ "fever" use two.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class SafetyLevel(IntEnum):
    """Ordered so that ``max()`` picks the most serious level."""

    NONE = 0
    MEDICAL = 1   # needs a health worker, not an emergency: medicines, doses, diagnosis, fever
    URGENT = 2    # danger sign: go to the health centre now


@dataclass(frozen=True)
class DangerRule:
    key: str
    level: SafetyLevel
    label_en: str
    label_rw: str
    all_of: tuple[str, ...]


def _any(*patterns: str) -> str:
    return "(?:" + "|".join(patterns) + ")"


URGENT, MEDICAL = SafetyLevel.URGENT, SafetyLevel.MEDICAL

RULES: tuple[DangerRule, ...] = (
    # ---- Urgent: general danger signs and severe acute malnutrition ----
    DangerRule("convulsions", URGENT, "convulsions or fits", "kugagara cyangwa guhinda umushyitsi", (_any(
        r"\bseizures?\b", r"\bconvuls", r"shaking and not responding", r"\bfitting\b",
        r"gaga(?:r|y)", r"hinda umushyitsi",
    ),)),
    DangerRule("unconscious", URGENT, "not waking up or not responding", "kutumva cyangwa guta ubwenge", (_any(
        r"\bunconscious", r"not (?:waking|responding|responsive)", r"(?:won't|will not|cannot|can't) wake",
        r"passed out", r"\bfaint(?:ed|ing|s)?\b", r"\blethargic", r"\bfloppy\b",
        r"yataye ubwenge", r"\bata ubwenge", r"\bntiyumva\b", r"ntakanguka", r"yaguye igihumure",
    ),)),
    DangerRule("very_sleepy", URGENT, "very sleepy or hard to wake", "gusinzira cyane cyangwa kudakanguka", (_any(
        # "Sleepy after feeds" is normal, so it is not a danger sign.
        r"(?:very|unusually|too|extremely|abnormally) (?:sleepy|drowsy)(?! after)", r"(?:hard|difficult) to wake",
        r"(?:won't|will not|cannot|can't) stay awake",
        r"sinzira cyane\b", r"\bntakangurwa\b",
    ),)),
    DangerRule("vomits_everything", URGENT, "vomiting everything", "kuruka ibintu byose", (_any(
        r"vomit\w* (?:everything|all)", r"throws? up (?:everything|every)",
        r"(?:can't|cannot|can not) keep (?:anything|food|milk) down",
        r"ruka (?:ibintu byose|byose|buri)",
    ),)),
    DangerRule("cannot_drink", URGENT, "unable to drink or breastfeed", "kunanirwa kunywa cyangwa konka", (_any(
        # The child must be the subject: "a mother cannot breastfeed" is a feeding question, not a danger sign.
        # Up to 60 characters may separate them ("my baby has diarrhoea and won't drink"), but not "I" or the mother.
        r"(?:child|baby|infant|toddler|son|daughter|\bhe|\bshe)(?:(?!\bi\b|\bmother|\bmom|\bmum|\bwife)[^.?!]){0,60}"
        r"(?:cannot|can't|unable to|not able to|won't|will not|refuses to|stopped|doesn't want to|does not want to) "
        r"(?:drink|breastfeed|breast feed|suck|nurse)",
        r"not (?:drinking|breastfeeding|sucking) (?:at all|anything)",
        r"ntashobora (?:konka|kunywa)", r"\bntiyonka\b", r"yanze konka", r"\bntakonka\b", r"\bntanywa\b",
    ),)),
    DangerRule("breathing", URGENT, "fast or difficult breathing", "guhumeka vuba cyangwa bigoranye", (_any(
        r"breath\w* (?:very )?(?:fast|quick|hard|heavily)", r"difficult\w* breath", r"trouble breath",
        r"struggling to breathe", r"(?:can't|cannot) breathe", r"chest (?:in-?drawing|pulling in|sinks)",
        r"humeka (?:vuba|nabi|bigoranye)", r"\bntahumeka\b", r"kubura umwuka",
    ),)),
    DangerRule("blood_in_stool", URGENT, "blood in the stool", "kwituma amaraso", (_any(
        r"blood\w* (?:in|on) (?:the |his |her |their |my )?(?:stool|poo|poop|diarr)",
        r"bloody (?:stool|diarr|poo)", r"ituma amaraso",
    ),)),
    DangerRule("oedema", URGENT, "swelling of both feet (oedema)", "kubyimba ibirenge cyangwa amaguru", (_any(
        r"swollen (?:feet|legs|ankles|face)", r"(?:feet|legs|ankles) (?:are |is |look |looks )?(?:swollen|puffy|swelling)",
        r"puffy (?:feet|legs)", r"\bo?edema\b",
        r"(?:ibirenge|amaguru|ikirenge|ukuguru|isura)[^.?!]{0,40}byimb", r"byimb\w*[^.?!]{0,20}(?:ibirenge|amaguru)",
    ),)),
    DangerRule("muac_red", URGENT, "MUAC tape in the red zone", "ibara ritukura kuri MUAC", (_any(
        r"muac[^.?!]{0,40}\bred\b", r"\bred zone\b", r"ibara ritukura",
    ),)),
    DangerRule("young_infant_fever", URGENT, "fever in a baby under 2 months", "umuriro ku ruhinja ruto", (
        _any(r"\bnew ?born", r"\bneonate", r"\b(?:1|one|2|two) months? old", r"\b(?:1|one) month\b",
             r"\b(?:[1-7]|one|two|three|four) weeks? old", r"\buruhinja", r"rukivuka", r"ukwezi kumwe"),
        _any(r"\bfever", r"\bfeels? hot", r"\bhot body", r"high temperature",
             r"umuriro", r"rurashyushye", r"arashyushye"),
    )),
    DangerRule("not_eating_for_days", URGENT, "not eating for days", "kumara iminsi atarya", (
        _any(r"not eaten", r"n't eaten", r"not eating", r"refus\w* (?:all |any |to eat|food)", r"won't eat",
             r"will not eat", r"stopped eating", r"\batarya\b", r"\bntarya\b", r"yanze kurya", r"yaretse kurya"),
        _any(r"\bdays?\b", r"\biminsi\b"),
    )),
    DangerRule("skin_lesions", URGENT, "peeling or broken skin", "uruhu rwomoka cyangwa rwasatagurika", (_any(
        r"peeling skin", r"skin (?:is )?peeling", r"skin (?:is )?(?:cracking|cracked|flaking)",
        r"uruhu rwomoka", r"uruhu rwasatagurik",
    ),)),
    DangerRule("severe_dehydration", URGENT, "signs of severe dehydration", "ibimenyetso byo kubura amazi mu mubiri gukabije", (_any(
        r"sunken eyes", r"no (?:urine|pee|wee)\b", r"not (?:urinating|peeing)", r"skin pinch goes back (?:very )?slowly",
        r"\bntanyara\b", r"ntiyanyara",
    ),)),
    # ---- Medical: a health worker must decide ----
    DangerRule("medicine", MEDICAL, "medicines or doses", "imiti cyangwa ingano yayo", (_any(
        r"\bmedicines?\b", r"\bmedications?\b", r"\bantibiotics?\b", r"\bsyrup\b", r"\bdos(?:e|es|age)\b",
        r"\btablets?\b", r"\bpills?\b", r"\bparacetamol", r"\bibuprofen", r"\bamoxicillin",
        r"\bmultivitamin", r"vitamin \w* ?(?:supplements?|pills?|tablets?|from the shop)", r"adult vitamins",
        r"appetite stimulant", r"\bherbs?\b", r"\bherbal\b", r"traditional healer", r"\brutf\b", r"plumpy",
        r"\b[ui]?muti\b", r"\bi?miti\b", r"izihe vitamini", r"antibiyotike", r"\bsirop\b", r"\bibinini\b", r"\bdoze\b", r"vitamini z",
        r"\bibyatsi\b", r"muvuzi gakondo", r"\budupaki\b",
    ),)),
    DangerRule("diagnosis", MEDICAL, "a diagnosis", "gusuzuma indwara", (_any(
        r"\bdiagnos", r"is my (?:child|baby|son|daughter) malnourished", r"tell me if my (?:child|baby)",
        r"does my (?:child|baby) have", r"(?:wambwira|mbwira) niba", r"nsuzumir",
        r"umwana wanjye[^.?!]{0,60}afite imirire mibi\?",
    ),)),
    DangerRule("fever", MEDICAL, "fever", "umuriro", (_any(
        r"\bfever", r"high temperature", r"\bhot body", r"\bumuriro\b", r"arashyushye",
    ),)),
    DangerRule("persistent_diarrhoea", MEDICAL, "diarrhoea for 2 weeks or more", "impiswi imaze ibyumweru 2 cyangwa birenga", (
        _any(r"diarrh", r"\bimpiswi\b"),
        _any(r"\bweeks?\b", r"\b(?:14|fourteen) days", r"\bibyumweru\b"),
    )),
)
