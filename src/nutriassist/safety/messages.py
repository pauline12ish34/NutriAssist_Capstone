"""Fixed safety messages in English and Kinyarwanda.

These are shown word for word, so they never depend on what the model generates.
912 is Rwanda's free emergency ambulance number (SAMU).
"""

from __future__ import annotations

URGENT = {
    "en": (
        "⚠️ This may be a danger sign: {signs}.\n\n"
        "Take your child to the nearest health centre or hospital **now**. Do not wait, and do not try to "
        "treat this at home. If you cannot travel, call your community health worker or the free emergency "
        "number **912**.\n\n"
        "On the way, keep the child warm, and if the child can drink, keep breastfeeding or give small sips "
        "of clean water."
    ),
    "rw": (
        "⚠️ Iki gishobora kuba ikimenyetso cy'akaga: {signs}.\n\n"
        "Jyana umwana ku kigo nderabuzima cyangwa ku bitaro biri hafi **nonaha**. Ntutegereze, kandi "
        "ntugerageze kumuvurira mu rugo. Niba udashobora kugenda, hamagara umujyanama w'ubuzima cyangwa "
        "nimero y'ubutabazi itishyurwa **912**.\n\n"
        "Mu nzira, mushyushye, kandi niba umwana ashobora kunywa, komeza umwonse cyangwa umuhe amazi "
        "meza make make."
    ),
}

MEDICAL_NOTE = {
    "en": ("Medicines, doses and diagnosis need a health worker who can examine your child. Please visit your "
           "health centre or talk to your community health worker."),
    "rw": ("Imiti, ingano yayo no gusuzuma indwara bikorwa n'umukozi w'ubuzima ushobora gusuzuma umwana. "
           "Jya ku kigo nderabuzima cyangwa uvugane n'umujyanama w'ubuzima."),
}

DOSE_BLOCKED = {
    "en": ("I can't tell you which medicine to give or how much: the right medicine and dose depend on your "
           "child's weight, age and illness, and a wrong dose can be dangerous. " + MEDICAL_NOTE["en"]),
    "rw": ("Sinshobora kukubwira umuti uha umwana cyangwa ingano yawo: umuti n'ingano bikwiye biterwa "
           "n'ibiro by'umwana, imyaka ye n'indwara afite, kandi ingano itari yo ishobora guteza akaga. "
           + MEDICAL_NOTE["rw"]),
}


# Shown for any question about honey: the fine-tuned model has said honey is safe from 1 month.
HONEY = {
    "en": ("Do not give honey to a baby under 12 months, not even a little or mixed into porridge or tea. Honey "
           "can carry germs that cause infant botulism, a rare but serious illness, and a young baby's gut cannot "
           "fight them. From 12 months, a small amount of honey is safe. If a baby under 12 months has eaten honey "
           "and becomes weak, floppy, constipated or feeds poorly, go to the health centre straight away."),
    "rw": ("Ntugahe ubuki umwana utarageza ku mezi 12, habe na buke cyangwa buvanze n'igikoma cyangwa icyayi. "
           "Ubuki bushobora kugira mikorobe zitera indwara ikomeye yitwa botulisme, kandi amara y'umwana muto "
           "ntashobora kuzirwanya. Guhera ku mezi 12, ubuki buke nta kibazo butera. Niba umwana utarageza ku "
           "mezi 12 yariye ubuki agacika intege, akananirwa kwituma cyangwa akonka nabi, mujyane ku kigo "
           "nderabuzima ako kanya."),
}


# Shown for a question about tea for a child: on the Space, Gemma answered "Yego" (yes) to tea for a
# 10-month-old. The text is the reviewed pair en-feed-13 / rw-feed-13 (Kinyarwanda approved by a native speaker).
TEA = {
    "en": ("It is best not to give tea or coffee to young children. Tea fills the stomach without giving much "
           "nutrition, and it reduces the iron the body takes from food, which can lead to anaemia. If older "
           "children drink tea, give it between meals, not with food. Better drinks are breast milk, clean water "
           "and milk or ikivuguto."),
    "rw": ("Ni byiza kutaha abana bato icyayi cyangwa ikawa. Icyayi cyuzuza igifu ariko nta ntungamubiri nyinshi "
           "gitanga, kandi kibuza umubiri gukura ubutare mu biryo, bishobora gutera kubura amaraso. Niba abana "
           "bakuru banywa icyayi, bakinywe hagati y'amafunguro, si kumwe n'ibiryo. Ibyo kunywa byiza ni "
           "amashereka, amazi meza n'amata cyangwa ikivuguto."),
}


# NEEDS REVIEW: Kinyarwanda drafted by Claude, not yet checked by a native speaker.
# Shown when a question is not close to any reviewed question (RelevanceChecker.in_scope): not the app's topic.
OUT_OF_SCOPE = {
    "en": ("I can only help with nutrition for children under 5 and for pregnant and breastfeeding mothers. "
           "For other questions, please ask someone who can help, or for health problems your community health "
           "worker or the health centre."),
    "rw": ("Nshobora gufasha gusa ku bijyanye n'imirire y'abana bari munsi y'imyaka 5 n'iy'ababyeyi batwite "
           "cyangwa bonsa. Ku bindi bibazo, baza undi ushobora kugufasha, naho ku bibazo by'ubuzima, baza "
           "umujyanama w'ubuzima cyangwa ujye ku kigo nderabuzima."),
}


# NEEDS REVIEW: Kinyarwanda drafted by Claude, not yet checked by a native speaker.
# Shown when a question in a reviewed-only language (Kinyarwanda in the app) matches no reviewed answer.
NO_MATCH = {
    "en": ("I don't have a checked answer to this question yet. Did you mean one of the questions below? "
           "If not, please ask your community health worker or visit the health centre."),
    "rw": ("Nta gisubizo cyagenzuwe mfite kuri iki kibazo. Wenda washakaga kubaza kimwe mu bibazo "
           "bikurikira? Niba atari byo, baza umujyanama w'ubuzima cyangwa ujye ku kigo nderabuzima."),
}
NO_MATCH_NO_SUGGESTIONS = {
    "en": ("I don't have a checked answer to this question yet. Please ask your community health worker or "
           "visit the health centre. You can also try asking in other words."),
    "rw": ("Nta gisubizo cyagenzuwe mfite kuri iki kibazo. Baza umujyanama w'ubuzima cyangwa ujye ku kigo "
           "nderabuzima. Ushobora no kongera kubaza ukoresheje andi magambo."),
}


def join_signs(labels: list[str], language: str) -> str:
    if len(labels) <= 1:
        return "".join(labels)
    conjunction = " na " if language == "rw" else " and "
    return ", ".join(labels[:-1]) + conjunction + labels[-1]
