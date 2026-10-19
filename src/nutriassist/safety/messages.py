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


def join_signs(labels: list[str], language: str) -> str:
    if len(labels) <= 1:
        return "".join(labels)
    conjunction = " na " if language == "rw" else " and "
    return ", ".join(labels[:-1]) + conjunction + labels[-1]
