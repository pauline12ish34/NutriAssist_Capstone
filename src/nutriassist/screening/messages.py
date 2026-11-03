"""Screening results and advice in English and Kinyarwanda, shown word for word (never written by the model).

Cut-offs and advice follow the WHO Child Growth Standards (2006), the WHO/UNICEF joint statement on
MUAC (2009) and the WHO guideline on wasting (2023). The Rwanda figure is from the 2025 Rwanda DHS
Key Indicators Report (NISR), Table 13.

NEEDS REVIEW: all Kinyarwanda texts below were drafted by Claude and not yet checked by a native speaker.
"""

from __future__ import annotations

LEVELS = {
    "severe": {"en": "🔴 Signs of severe acute malnutrition", "rw": "🔴 Ibimenyetso by'imirire mibi ikabije"},
    "moderate": {"en": "🟡 The child needs follow-up", "rw": "🟡 Umwana akeneye gukurikiranwa"},
    "check": {"en": "⚪ Check the measurements", "rw": "⚪ Ongera urebe ibipimo"},
    "normal": {"en": "🟢 Growth looks normal for the age", "rw": "🟢 Imikurire isa n'aho ari myiza ugereranyije n'imyaka"},
}

FINDINGS = {
    "sam_oedema": {"en": "Swelling of both feet (bilateral oedema)", "rw": "Kubyimba ibirenge byombi"},
    "sam_muac": {"en": "MUAC {muac} cm: severe acute malnutrition (red, below 11.5 cm)",
                 "rw": "MUAC cm {muac}: imirire mibi ikabije (ibara ritukura, munsi ya cm 11.5)"},
    "mam_muac": {"en": "MUAC {muac} cm: moderate acute malnutrition (yellow, 11.5 to 12.5 cm)",
                 "rw": "MUAC cm {muac}: imirire mibi yoroheje (ibara ry'umuhondo, cm 11.5 kugeza 12.5)"},
    "sam_whz": {"en": "Weight-for-height {z}: severe wasting (below -3)",
                "rw": "Ibiro ugereranyije n'uburebure {z}: kunanuka bikabije (munsi ya -3)"},
    "mam_whz": {"en": "Weight-for-height {z}: moderate wasting (below -2)",
                "rw": "Ibiro ugereranyije n'uburebure {z}: kunanuka (munsi ya -2)"},
    "overweight": {"en": "Weight-for-height {z}: overweight (above +2)",
                   "rw": "Ibiro ugereranyije n'uburebure {z}: ibiro birenze (hejuru ya +2)"},
    "severe_stunting": {"en": "Height-for-age {z}: severe stunting (below -3)",
                        "rw": "Uburebure ugereranyije n'imyaka {z}: kugwingira bikabije (munsi ya -3)"},
    "stunting": {"en": "Height-for-age {z}: stunting (below -2)",
                 "rw": "Uburebure ugereranyije n'imyaka {z}: kugwingira (munsi ya -2)"},
    "severe_underweight": {"en": "Weight-for-age {z}: severely underweight (below -3)",
                           "rw": "Ibiro ugereranyije n'imyaka {z}: ibiro bike cyane (munsi ya -3)"},
    "underweight": {"en": "Weight-for-age {z}: underweight (below -2)",
                    "rw": "Ibiro ugereranyije n'imyaka {z}: ibiro bike (munsi ya -2)"},
    "check_measurement": {"en": "{indicator} z-score {z} is very unusual: check the age, weight and height, then measure again",
                          "rw": "{indicator} {z} ntibisanzwe: ongera urebe imyaka, ibiro n'uburebure, hanyuma wongere upime"},
}

INDICATORS = {
    "wfa": {"en": "Weight-for-age", "rw": "Ibiro ugereranyije n'imyaka"},
    "hfa": {"en": "Height-for-age", "rw": "Uburebure ugereranyije n'imyaka"},
    "wfh": {"en": "Weight-for-height", "rw": "Ibiro ugereranyije n'uburebure"},
}

ADVICE = {
    "severe": {
        "en": "Take the child to the **health centre today**. Severe acute malnutrition needs medical treatment "
              "(therapeutic food such as RUTF, or care in hospital); food at home alone is not enough. Keep "
              "breastfeeding, and keep the child warm on the way. If you cannot travel, call **912**.",
        "rw": "Jyana umwana ku **kigo nderabuzima uyu munsi**. Imirire mibi ikabije ikenera kuvurwa (ibiryo "
              "bivura nka RUTF, cyangwa kuvurirwa mu bitaro); ibiryo byo mu rugo byonyine ntibihagije. Komeza "
              "konsa, kandi ushyushye umwana mu nzira. Niba udashobora kugenda, hamagara **912**.",
    },
    "moderate": {
        "en": "Refer the child to the **health centre** for a check, and ask about the supplementary feeding "
              "programme. Measure the child again at the next growth monitoring session.",
        "rw": "Ohereza umwana ku **kigo nderabuzima** kugira ngo asuzumwe, kandi ubaze ibijyanye na gahunda "
              "yo kongerera abana ibiryo. Ongera upime umwana mu gikorwa gikurikira cyo gukurikirana imikurire.",
    },
    "check": {
        "en": "One result is outside what is possible for a child of this age. This is usually a measuring or "
              "typing mistake: check the age in months, the weight and the height, and measure again.",
        "rw": "Igisubizo kimwe kiri hanze y'ibishoboka ku mwana w'iyi myaka. Akenshi ni ikosa ryo gupima "
              "cyangwa kwandika: ongera urebe imyaka mu mezi, ibiro n'uburebure, hanyuma wongere upime.",
    },
    "normal": {
        "en": "Keep coming to the monthly growth monitoring session (MUAC, weight and height), and keep "
              "feeding the child a variety of local foods.",
        "rw": "Komeza kuza mu gikorwa cya buri kwezi cyo gukurikirana imikurire (MUAC, ibiro n'uburebure), "
              "kandi ukomeze kugaburira umwana ibiribwa bitandukanye byo mu Rwanda.",
    },
}

TIPS = {
    "wasting": {
        "en": "Give 1 or 2 extra meals or snacks every day. Make food richer in energy: add a little oil, "
              "groundnut paste or avocado, and enrich porridge with milk, soy or groundnut flour.",
        "rw": "Ongeraho ifunguro rimwe cyangwa abiri buri munsi. Ongera ingufu mu biryo: shyiramo amavuta "
              "make, ubunyobwa biseye cyangwa avoka, kandi ukungahaze igikoma ukoresheje amata, ifu ya soya "
              "cyangwa iy'ubunyobwa.",
    },
    "stunting": {
        "en": "Stunting builds up over months. Give a food from animals every day if you can (egg, milk, small "
              "fish such as indagara, meat), with beans and dark green leaves. Ask the health centre about "
              "deworming and vitamin A.",
        "rw": "Kugwingira kuza buhoro buhoro mu mezi menshi. Niba bishoboka, buri munsi muhe ikiribwa "
              "gikomoka ku matungo (igi, amata, amafi mato nk'indagara, inyama), hamwe n'ibishyimbo n'imboga "
              "z'amababi y'icyatsi kibisi. Baza ku kigo nderabuzima ibijyanye n'imiti y'inzoka na vitamini A.",
    },
    "underweight": {
        "en": "Feed the child more often, and keep feeding during and after illness: give one extra meal a day "
              "for two weeks after the child is well again.",
        "rw": "Gaburira umwana kenshi, kandi ukomeze kumugaburira igihe arwaye na nyuma yaho: umuhe ifunguro "
              "ry'inyongera buri munsi mu byumweru bibiri nyuma yo gukira.",
    },
    "overweight": {
        "en": "Avoid sugary drinks, sweets and fried snacks, and do not add sugar to porridge. Give fruit and "
              "vegetables, and let the child play actively every day.",
        "rw": "Irinde ibinyobwa birimo isukari, ibiryohereye n'ibikaranze, kandi ntushyire isukari mu gikoma. "
              "Muhe imbuto n'imboga, kandi ureke umwana akine buri munsi.",
    },
    "under_6_months": {
        "en": "Under 6 months a baby needs only breast milk, as often as the baby wants. Take the baby to the "
              "health centre so a health worker can check breastfeeding and the baby's health.",
        "rw": "Umwana uri munsi y'amezi 6 akenera amashereka yonyine, igihe cyose abishaka. Jyana umwana ku "
              "kigo nderabuzima kugira ngo umukozi w'ubuzima arebe uko yonka n'ubuzima bwe.",
    },
}

RWANDA_STUNTING = {
    "en": "In Rwanda, 26.8% of children under 5 are stunted (Rwanda DHS 2025).",
    "rw": "Mu Rwanda, 26.8% by'abana bari munsi y'imyaka 5 baragwingiye (Ubushakashatsi DHS 2025).",
}

MUAC_NOT_USED = {
    "en": "MUAC is used from 6 months, so it was not used for this baby.",
    "rw": "MUAC ikoreshwa guhera ku mezi 6, bityo ntiyakoreshejwe kuri uyu mwana.",
}

NO_HEIGHT = {
    "en": "Without height, stunting and wasting cannot be checked. Measure height if a height board is available.",
    "rw": "Hatabayeho uburebure, kugwingira no kunanuka ntibishobora gusuzumwa. Pima uburebure niba hari "
          "igipimo cy'uburebure.",
}

INPUT_ERRORS = {
    "age": {"en": "Enter the child's age in months, from 0 to 59.",
            "rw": "Andika imyaka y'umwana mu mezi, kuva kuri 0 kugeza kuri 59."},
    "sex": {"en": "Choose whether the child is a boy or a girl.", "rw": "Hitamo niba umwana ari umuhungu cyangwa umukobwa."},
    "weight": {"en": "Enter the weight in kilograms, between 1 and 35 kg.",
               "rw": "Andika ibiro mu kilogarama, hagati ya kg 1 na kg 35."},
    "height": {"en": "Enter the height in centimetres, between 40 and 125 cm (or leave it empty).",
               "rw": "Andika uburebure muri santimetero, hagati ya cm 40 na cm 125 (cyangwa ubireke)."},
    "muac": {"en": "Enter MUAC in centimetres, between 6 and 26 cm (or leave it empty).",
             "rw": "Andika MUAC muri santimetero, hagati ya cm 6 na cm 26 (cyangwa ubireke)."},
}
