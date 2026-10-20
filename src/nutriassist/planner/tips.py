"""Feeding advice shown with a meal plan, in English and Kinyarwanda (WHO/PAHO complementary-feeding guidance)."""

from __future__ import annotations

TIPS: dict[str, dict[str, str]] = {
    "keep_breastfeeding": {
        "en": "Keep breastfeeding as often as the child wants, day and night.",
        "rw": "Komeza konsa igihe cyose umwana abishaka, ku manywa na nijoro.",
    },
    "texture_mashed": {
        "en": "Mash all food until it is smooth and thick: it should stay on the spoon without running off.",
        "rw": "Sya ibiryo byose neza, bibe byoroshye kandi bifashe ku buryo biguma ku kiyiko.",
    },
    "texture_chopped": {
        "en": "Give finely chopped or mashed food, and soft pieces the child can pick up with the fingers.",
        "rw": "Muhe ibiryo bikatiwe uduce duto cyangwa biseye, n'uduce tworoshye ashobora gufata n'intoki.",
    },
    "texture_family": {
        "en": "The child can eat family foods, cut into small pieces. Give the child their own plate.",
        "rw": "Umwana ashobora kurya ibiryo by'umuryango bikatiwe uduce duto. Muhe isahani ye bwite.",
    },
    "vitamin_c_with_iron": {
        "en": "Serve a fruit rich in vitamin C (orange, guava, mango, papaya, pineapple) with beans and green "
              "leaves: it helps the body absorb their iron.",
        "rw": "Muhe urubuto rukungahaye kuri vitamini C (icunga, ipera, umwembe, ipapayi, inanasi) hamwe "
              "n'ibishyimbo n'imboga z'amababi: bifasha umubiri gukura ubutare muri byo.",
    },
    "iron_hard_to_reach": {
        "en": "At this age a child needs a lot of iron, and it is hard to get enough from food alone. Ask your "
              "health centre about iron-fortified foods and micronutrient powder.",
        "rw": "Muri iki gihe umwana akenera ubutare bwinshi, kandi biragoye kububona bihagije mu biryo byonyine. "
              "Baza ku kigo nderabuzima ibijyanye n'ibiryo byongewemo ubutare n'ifu y'intungamubiri.",
    },
    "not_breastfed": {
        "en": "Because the child is not breastfed, give an extra snack every day and milk or yoghurt daily.",
        "rw": "Kubera ko umwana atonka, muhe ifunguro rito ry'inyongera buri munsi, n'amata cyangwa yawurute buri munsi.",
    },
    "no_sugar_salt": {
        "en": "Do not add sugar or salt, and do not give tea or sweet drinks with meals.",
        "rw": "Ntukongeremo isukari cyangwa umunyu, kandi ntumuhe icyayi cyangwa ibinyobwa birimo isukari mu gihe cyo kurya.",
    },
    "hygiene": {
        "en": "Wash your hands and the child's hands with soap before preparing food and before eating.",
        "rw": "Karaba intoki zawe n'iz'umwana ukoresheje isabune mbere yo gutegura ibiryo no mbere yo kurya.",
    },
    "guide_only": {
        "en": "This plan is a guide for a healthy child. A child who is sick, losing weight, or in the yellow or "
              "red zone of the MUAC tape needs advice from a health worker.",
        "rw": "Iyi gahunda ni inama ku mwana muzima. Umwana urwaye, utakaza ibiro, cyangwa uri mu ibara "
              "ry'umuhondo cyangwa ritukura kuri MUAC akeneye inama z'umukozi w'ubuzima.",
    },
}

MEAL_NAMES = {
    "breakfast": {"en": "Breakfast", "rw": "Mu gitondo"},
    "lunch": {"en": "Lunch", "rw": "Saa sita"},
    "dinner": {"en": "Dinner", "rw": "Nimugoroba"},
    "snack": {"en": "Snack", "rw": "Hagati"},
}


def tip(key: str, language: str) -> str:
    return TIPS[key]["rw" if language == "rw" else "en"]
