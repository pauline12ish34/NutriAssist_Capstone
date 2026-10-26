"""Interface text in English and Kinyarwanda."""

from __future__ import annotations

import streamlit as st

TEXT: dict[str, dict[str, str]] = {
    "app_title": {"en": "NutriAssist-RW", "rw": "NutriAssist-RW"},
    "tagline": {
        "en": "Nutrition advice for caregivers of children under 5 in Rwanda",
        "rw": "Inama ku mirire ku barera abana bari munsi y'imyaka 5 mu Rwanda",
    },
    "language": {"en": "Language", "rw": "Ururimi"},
    "page_chat": {"en": "Ask a question", "rw": "Baza ikibazo"},
    "page_planner": {"en": "Meal planner", "rw": "Gahunda y'amafunguro"},
    "page_about": {"en": "How to use", "rw": "Uko bikoreshwa"},
    "server_ok": {"en": "Assistant is online", "rw": "Porogaramu irakora"},
    "server_down": {"en": "Assistant is offline", "rw": "Porogaramu ntiri gukora"},
    "demo_mode": {
        "en": "Demo mode: the trained model is not installed, so chat answers are placeholders. Safety checks and the meal planner work normally.",
        "rw": "Uburyo bw'igerageza: porogaramu yatojwe ntiyashyizweho, ibisubizo by'ibiganiro si ibya nyabyo. Igenzura ry'umutekano na gahunda y'amafunguro birakora neza.",
    },
    "emergency": {
        "en": "Emergency? Go to the nearest health centre or call 912.",
        "rw": "Ibyihutirwa? Jya ku kigo nderabuzima kiri hafi cyangwa uhamagare 912.",
    },
    # Chat
    "chat_intro": {
        "en": "Ask about breastfeeding, feeding your child from 6 months to 5 years, nutrition in pregnancy, or local foods. You can write in English or Kinyarwanda.",
        "rw": "Baza ibijyanye no konsa, kugaburira umwana kuva ku mezi 6 kugeza ku myaka 5, imirire y'umugore utwite, cyangwa ibiribwa byo mu Rwanda. Ushobora kwandika mu Cyongereza cyangwa mu Kinyarwanda.",
    },
    "chat_placeholder": {"en": "Type your question...", "rw": "Andika ikibazo cyawe..."},
    "examples": {"en": "Try an example", "rw": "Gerageza urugero"},
    "thinking": {"en": "Thinking...", "rw": "Ndatekereza..."},
    "clear_chat": {"en": "Clear conversation", "rw": "Siba ibiganiro"},
    "urgent_banner": {"en": "Danger sign detected", "rw": "Habonetse ikimenyetso cy'akaga"},
    "medical_banner": {"en": "This needs a health worker", "rw": "Ibi bikeneye umukozi w'ubuzima"},
    "answered_by_rules": {"en": "Answered by the safety rules", "rw": "Cyasubijwe n'amategeko y'umutekano"},
    # NEEDS REVIEW: the two Kinyarwanda texts below were drafted by Claude and not yet checked by a native speaker.
    "answered_by_reviewed": {"en": "Answer reviewed by a person", "rw": "Igisubizo cyagenzuwe n'umuntu"},
    "machine_translated": {
        "en": "This answer was translated by a computer and may contain mistakes. For important decisions, ask your community health worker.",
        "rw": "Iki gisubizo cyahinduwe na mudasobwa, gishobora kugira amakosa. Ku byemezo bikomeye, baza umujyanama w'ubuzima.",
    },
    "seconds": {"en": "s", "rw": "s"},
    # Meal planner
    "planner_intro": {
        "en": "Get a meal plan from local foods, sized for your child's age. Portions are in tablespoons and grams.",
        "rw": "Bona gahunda y'amafunguro ikoresheje ibiribwa byo mu Rwanda, ijyanye n'imyaka y'umwana wawe. Ingano iri mu biyiko no muri garama.",
    },
    "age": {"en": "Child's age (months)", "rw": "Imyaka y'umwana (mu mezi)"},
    "age_help": {"en": "From 6 months (start of solid food) to 59 months", "rw": "Kuva ku mezi 6 (atangira kurya) kugeza ku mezi 59"},
    "breastfed": {"en": "The child is still breastfed", "rw": "Umwana aracyonka"},
    "days": {"en": "Length of the plan", "rw": "Igihe gahunda imara"},
    "one_day": {"en": "1 day", "rw": "umunsi 1"},
    "one_week": {"en": "7 days", "rw": "iminsi 7"},
    "only_these": {"en": "Use only foods I have (optional)", "rw": "Koresha ibiribwa mfite gusa (si ngombwa)"},
    "exclude": {"en": "Foods to avoid (allergy, dislike)", "rw": "Ibiribwa byo kwirinda (allergie, atabikunda)"},
    "make_plan": {"en": "Make my plan", "rw": "Kora gahunda yanjye"},
    "day": {"en": "Day", "rw": "Umunsi"},
    "food": {"en": "Food", "rw": "Ikiribwa"},
    "amount": {"en": "Amount", "rw": "Ingano"},
    "grams": {"en": "Grams", "rw": "Garama"},
    "coverage": {"en": "Daily needs covered (food + breast milk)", "rw": "Ibyo umubiri ukeneye ku munsi byabonetse (ibiryo + amashereka)"},
    "energy_kcal": {"en": "Energy", "rw": "Ingufu"},
    "protein_g": {"en": "Protein", "rw": "Poroteyine"},
    "iron_mg": {"en": "Iron", "rw": "Ubutare"},
    "calcium_mg": {"en": "Calcium", "rw": "Kalisiyumu"},
    "diversity": {"en": "Food groups today", "rw": "Amatsinda y'ibiribwa uyu munsi"},
    "diversity_ok": {"en": "meets the WHO minimum of 5", "rw": "byujuje 5 bisabwa na OMS"},
    "diversity_low": {"en": "below the WHO minimum of 5", "rw": "biri munsi ya 5 bisabwa na OMS"},
    "tips": {"en": "Feeding tips", "rw": "Inama zo kugaburira"},
    "missing_slots": {
        "en": "Some parts of the meals could not be filled with the foods you chose",
        "rw": "Ibice bimwe by'amafunguro ntibyabonewe ibiribwa mu byo wahisemo",
    },
    "download": {"en": "Download plan", "rw": "Kuramo gahunda"},
    # Meal-plan slots that the chosen foods could not fill
    "slot_porridge_flour": {"en": "porridge flour", "rw": "ifu y'igikoma"},
    "slot_porridge_enricher": {"en": "something to enrich the porridge (soy flour, groundnut paste or yoghurt)",
                               "rw": "icyongera intungamubiri mu gikoma (ifu ya soya, ubunyobwa biseye cyangwa yawurute)"},
    "slot_staple": {"en": "a staple (sweet potato, potato, rice, plantain...)", "rw": "ibiribwa by'ibanze (ibijumba, ibirayi, umuceri, ibitoki...)"},
    "slot_protein": {"en": "a protein food (beans, egg, fish, meat...)", "rw": "ibyubaka umubiri (ibishyimbo, igi, ifi, inyama...)"},
    "slot_vegetable": {"en": "a vegetable", "rw": "imboga"},
    "slot_fat": {"en": "avocado or groundnut paste", "rw": "avoka cyangwa ubunyobwa biseye"},
    "slot_fruit": {"en": "a fruit", "rw": "urubuto"},
    "slot_snack": {"en": "a snack (fruit, yoghurt, egg or avocado)", "rw": "ifunguro rito (urubuto, yawurute, igi cyangwa avoka)"},
}


def t(key: str) -> str:
    """Text for ``key`` in the language chosen in the sidebar."""
    return TEXT[key][st.session_state.get("language", "en")]


def language() -> str:
    return st.session_state.get("language", "en")
