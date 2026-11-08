"""Interface text in English and Kinyarwanda, shared by the Streamlit app and the Gradio (ZeroGPU) app."""

from __future__ import annotations

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
    # Shown once, before the app can be used (the proposal's ethics section).
    # NEEDS REVIEW: Kinyarwanda drafted by Claude, not yet checked by a native speaker.
    "disclaimer_title": {"en": "Before you start", "rw": "Mbere yo gutangira"},
    "disclaimer": {
        "en": (
            "- NutriAssist-RW is a **student project**. It gives general nutrition advice; it is **not a doctor "
            "or a health worker**.\n"
            "- Answers written by AI can contain **mistakes**. Check important decisions with your health worker.\n"
            "- It does **not diagnose illness or give medicine doses**.\n"
            "- In an **emergency**, go to the nearest health centre or call **912**.\n"
            "- Do not type your name or other personal details. Questions are not saved with personal information."
        ),
        "rw": (
            "- NutriAssist-RW ni **umushinga w'umunyeshuri**. Itanga inama rusange ku mirire; **si muganga cyangwa "
            "umukozi w'ubuzima**.\n"
            "- Ibisubizo byanditswe na AI bishobora kugira **amakosa**. Ku byemezo bikomeye, banza ubaze umujyanama "
            "w'ubuzima.\n"
            "- **Ntisuzuma indwara kandi ntitanga ingano y'imiti**.\n"
            "- Mu **bihe byihutirwa**, jya ku kigo nderabuzima kiri hafi cyangwa uhamagare **912**.\n"
            "- Ntwandike izina ryawe cyangwa andi makuru akwerekeyeho. Ibibazo ntibibikwa hamwe n'amakuru yawe bwite."
        ),
    },
    "disclaimer_accept": {"en": "I understand, continue", "rw": "Ndabyumvise, komeza"},
    # Demo sign-in for community health workers (app/chw_login.py).
    # NEEDS REVIEW: Kinyarwanda drafted by Claude, not yet checked by a native speaker.
    "login_title": {"en": "Sign in", "rw": "Injira"},
    "login_intro": {
        "en": "For community health workers: enter your CHW ID and the code you received.",
        "rw": "Ku bajyanama b'ubuzima: andika nimero yawe y'umujyanama w'ubuzima n'umubare w'ibanga wakiriye.",
    },
    "login_demo_note": {
        "en": ("Demo version: the CHW IDs are made up, and a fixed code replaces the code sent by SMS. A real "
               "version would check the Ministry of Health's records of community health workers."),
        "rw": ("Iyi ni verisiyo y'igerageza: nimero z'abajyanama b'ubuzima ni izahimbwe, kandi umubare w'ibanga "
               "udahinduka usimbura uwoherezwa kuri SMS. Verisiyo nyayo yagenzura amakuru ya Minisiteri "
               "y'Ubuzima ku bajyanama b'ubuzima."),
    },
    "login_id": {"en": "CHW ID", "rw": "Nimero y'umujyanama w'ubuzima"},
    "login_code": {"en": "Code", "rw": "Umubare w'ibanga"},
    "login_button": {"en": "Sign in", "rw": "Injira"},
    "login_failed": {"en": "The CHW ID or the code is not correct.",
                     "rw": "Nimero y'umujyanama w'ubuzima cyangwa umubare w'ibanga si byo."},
    "login_locked": {"en": "Too many wrong attempts. Please try again later.",
                     "rw": "Wagerageje inshuro nyinshi bitari byo. Ongera ugerageze nyuma."},
    "signed_in_as": {"en": "Signed in as", "rw": "Winjiye nka"},
    "logout": {"en": "Sign out", "rw": "Sohoka"},
    # Chat
    "chat_intro": {
        "en": "Ask about breastfeeding, feeding your child from 6 months to 5 years, nutrition in pregnancy, or local foods. You can write in English or Kinyarwanda.",
        "rw": "Baza ibijyanye no konsa, kugaburira umwana kuva ku mezi 6 kugeza ku myaka 5, imirire y'umugore utwite, cyangwa ibiribwa byo mu Rwanda. Ushobora kwandika mu Cyongereza cyangwa mu Kinyarwanda.",
    },
    "chat_placeholder": {"en": "Type your question...", "rw": "Andika ikibazo cyawe..."},
    "examples": {"en": "Try an example", "rw": "Gerageza urugero"},
    "thinking": {"en": "Thinking...", "rw": "Ndatekereza..."},
    # NEEDS REVIEW: Kinyarwanda drafted by Claude, not yet checked by a native speaker.
    "thinking_translated": {"en": "Finding the answer and translating it into Kinyarwanda. This can take a little while...",
                            "rw": "Ndimo gushaka igisubizo no kugihindura mu Kinyarwanda. Bishobora gufata akanya gato..."},
    "clear_chat": {"en": "Clear conversation", "rw": "Siba ibiganiro"},
    "urgent_banner": {"en": "Danger sign detected", "rw": "Habonetse ikimenyetso cy'akaga"},
    "medical_banner": {"en": "This needs a health worker", "rw": "Ibi bikeneye umukozi w'ubuzima"},
    # NEEDS REVIEW: the two Kinyarwanda texts below were drafted by Claude and not yet checked by a native speaker.
    # Shown only under answers the model wrote; safety-rule and reviewed answers carry no label.
    "ai_warning": {
        "en": "Written by AI: may contain mistakes. Check with your health worker.",
        "rw": "Cyanditswe na AI: gishobora kugira amakosa. Baza umujyanama w'ubuzima.",
    },
    "machine_translated": {
        "en": "This answer was translated by a computer and may contain mistakes. For important decisions, ask your community health worker.",
        "rw": "Iki gisubizo cyahinduwe na mudasobwa, gishobora kugira amakosa. Ku byemezo bikomeye, baza umujyanama w'ubuzima.",
    },
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
    # Growth screening. NEEDS REVIEW: Kinyarwanda drafted by Claude, not yet checked by a native speaker.
    "page_screening": {"en": "Growth check", "rw": "Isuzuma ry'imikurire"},
    "screening_intro": {
        "en": "For community health workers and caregivers: enter the measurements from growth monitoring or the "
              "child's health booklet. The result uses the WHO Child Growth Standards. Measurements are not saved.",
        "rw": "Ku bajyanama b'ubuzima n'abarera abana: andika ibipimo byo mu gikorwa cyo gukurikirana imikurire "
              "cyangwa byo mu gatabo k'ubuzima bw'umwana. Igisubizo gishingiye ku bipimo by'imikurire bya OMS. "
              "Ibipimo ntibibikwa.",
    },
    "s_age": {"en": "Age (months)", "rw": "Imyaka (mu mezi)"},
    "s_sex": {"en": "Sex", "rw": "Igitsina"},
    "boy": {"en": "Boy", "rw": "Umuhungu"},
    "girl": {"en": "Girl", "rw": "Umukobwa"},
    "s_weight": {"en": "Weight (kg)", "rw": "Ibiro (kg)"},
    "s_height": {"en": "Length / height (cm), optional", "rw": "Uburebure (cm), si ngombwa"},
    "s_height_help": {"en": "Lying down under 2 years, standing from 2 years",
                      "rw": "Aryamye niba ari munsi y'imyaka 2, ahagaze guhera ku myaka 2"},
    "s_muac": {"en": "MUAC (cm), optional", "rw": "MUAC (cm), si ngombwa"},
    "s_muac_help": {"en": "From 6 months. Example: 13.2", "rw": "Guhera ku mezi 6. Urugero: 13.2"},
    "s_oedema": {"en": "Both feet are swollen (press for 3 seconds: a dent stays)",
                 "rw": "Ibirenge byombi birabyimbye (kanda amasegonda 3: hagasigara umwobo)"},
    "s_button": {"en": "Check growth", "rw": "Suzuma imikurire"},
    "s_findings": {"en": "What was found", "rw": "Ibyabonetse"},
    "s_none": {"en": "No sign of malnutrition in these measurements.", "rw": "Nta kimenyetso cy'imirire mibi kiri muri ibi bipimo."},
    "s_measure": {"en": "Measure", "rw": "Igipimo"},
    "s_result": {"en": "Result", "rw": "Igisubizo"},
    "s_advice": {"en": "Feeding advice", "rw": "Inama zo kugaburira"},
    "s_plan": {"en": "Meal plan for one day", "rw": "Gahunda y'amafunguro y'umunsi umwe"},
    "s_not_measured": {"en": "not measured", "rw": "ntibyapimwe"},
    "adjusted_for": {"en": "Plan adjusted for the growth check", "rw": "Gahunda yahinduwe hakurikijwe isuzuma ry'imikurire"},
    "s_need_sex": {"en": "Choose whether the child is a boy or a girl.",
                   "rw": "Hitamo niba umwana ari umuhungu cyangwa umukobwa."},
    "s_need_weight": {"en": "Enter the child's weight in kilograms.", "rw": "Andika ibiro by'umwana mu kilogarama."},
    "z_wfa": {"en": "Weight-for-age", "rw": "Ibiro ugereranyije n'imyaka"},
    "z_hfa": {"en": "Height-for-age", "rw": "Uburebure ugereranyije n'imyaka"},
    "z_wfh": {"en": "Weight-for-height", "rw": "Ibiro ugereranyije n'uburebure"},
}

EXAMPLES = {
    "en": [
        "What foods should I give my 8-month-old baby?",
        "How can I add more iron to my child's food?",
        "What should I eat while breastfeeding?",
        "My child has a fever, what should she eat?",
    ],
    # Reviewed questions, so each example gets its approved answer (Kinyarwanda comes only from reviewed answers).
    "rw": [
        "Umwana w'amezi 9 akwiye kurya angana iki?",
        "Ni ibihe biryo byo mu Rwanda bikungahaye ku butare?",
        "Abagore batwite bakwiye kurya iki kugira ngo barinde abana babo imirire mibi?",
        "Nagaburira nte umwana urwaye?",
    ],
}

ABOUT = {
    "en": """
### What NutriAssist-RW does
- **Answers questions** about breastfeeding, feeding children from 6 months to 5 years, nutrition in pregnancy
  and while breastfeeding, and local Rwandan foods, in **English or Kinyarwanda**.
- **Makes meal plans** for a child aged 6 to 59 months from local foods, with amounts in tablespoons.
- **Checks growth** from the measurements community health workers take (weight, MUAC and height), using
  the WHO Child Growth Standards, and gives feeding advice or tells you to go to the health centre.

### Growth check
Enter the child's age in months, sex and weight, and the MUAC and height if you have them (from growth
monitoring or the child's health booklet). Tick the box if both feet are swollen. Press *Check growth*:
- 🔴 **Severe:** go to the health centre **today**. No meal plan is given: severe malnutrition needs treatment.
- 🟡 **Follow-up:** see the health centre, with feeding advice and a meal plan.
- 🟢 **Normal:** keep coming to monthly growth monitoring.

### How to use it
1. Choose your language in the sidebar.
2. **Ask a question:** type it in the box at the bottom of the page, or tap an example. The answer comes back
   in the language you wrote in.
3. **Meal planner:** set your child's age, say whether the child is still breastfed, choose 1 or 7 days,
   and press *Make my plan*. You can limit the plan to the foods you have, or leave out foods.
4. Read the **feeding tips** under the plan, and download it if you want to keep it.

### Safety
- NutriAssist-RW **does not diagnose illness or give medicine doses.**
- If your message describes a **danger sign** (convulsions, a child who cannot drink or breastfeed, vomiting
  everything, fast breathing, blood in the stool, swollen feet, MUAC red...), the app tells you straight away
  to go to the health centre. This answer comes from fixed safety rules, not from the AI model.
- In an emergency, go to the nearest health centre or call **912**.

### Where the information comes from
- Answers: a language model fine-tuned on 513 question-answer pairs on child and maternal nutrition,
  checked for safety and reviewed in Kinyarwanda by a native speaker.
- Meal plans: a food composition workbook from a nutritionist in Kigali, with 5 sheets of foods: **2,395 foods**,
  each with 33 nutrients. The planner uses **33 common Rwandan foods** from it, with values checked against
  USDA, and WHO/FAO nutrient needs for the child's age.
""",
    "rw": """
### NutriAssist-RW ikora iki
- **Isubiza ibibazo** ku konsa, kugaburira abana kuva ku mezi 6 kugeza ku myaka 5, imirire y'umugore utwite
  n'uwonsa, n'ibiribwa byo mu Rwanda, mu **Cyongereza cyangwa mu Kinyarwanda**.
- **Ikora gahunda y'amafunguro** y'umwana ufite hagati y'amezi 6 na 59, ikoresheje ibiribwa byo mu Rwanda,
  n'ingano mu biyiko.
- **Isuzuma imikurire** hakoreshejwe ibipimo abajyanama b'ubuzima bafata (ibiro, MUAC n'uburebure),
  ishingiye ku bipimo by'imikurire bya OMS, igatanga inama zo kugaburira cyangwa ikakubwira kujya ku kigo
  nderabuzima.

### Isuzuma ry'imikurire
Andika imyaka y'umwana mu mezi, igitsina n'ibiro, na MUAC n'uburebure niba ubifite (byo mu gikorwa cyo
gukurikirana imikurire cyangwa mu gatabo k'ubuzima bw'umwana). Kanda ku kazu niba ibirenge byombi
bibyimbye. Kanda *Suzuma imikurire*:
- 🔴 **Bikabije:** jya ku kigo nderabuzima **uyu munsi**. Nta gahunda y'amafunguro itangwa: imirire mibi
  ikabije ikenera kuvurwa.
- 🟡 **Gukurikiranwa:** jya ku kigo nderabuzima, uhabwe inama zo kugaburira na gahunda y'amafunguro.
- 🟢 **Ni byiza:** komeza kuza mu gikorwa cya buri kwezi cyo gukurikirana imikurire.

### Uko ikoreshwa
1. Hitamo ururimi mu ruhande rw'ibumoso.
2. **Baza ikibazo:** cyandike mu kazu kari hasi, cyangwa ukande ku rugero. Igisubizo kiza mu rurimi wanditsemo.
3. **Gahunda y'amafunguro:** shyiramo imyaka y'umwana, uvuge niba akonka, uhitemo umunsi 1 cyangwa iminsi 7,
   ukande *Kora gahunda yanjye*. Ushobora gukoresha ibiribwa ufite gusa, cyangwa ugakuramo ibyo udashaka.
4. Soma **inama zo kugaburira** ziri munsi ya gahunda, kandi ushobora kuyikuraho ukayibika.

### Umutekano
- NutriAssist-RW **ntisuzuma indwara kandi ntitanga ingano y'imiti.**
- Niba ubutumwa bwawe buvuga **ikimenyetso cy'akaga** (kugagara, umwana udashobora kunywa cyangwa konka,
  kuruka ibintu byose, guhumeka vuba, kwituma amaraso, kubyimba ibirenge, ibara ritukura kuri MUAC...),
  porogaramu ihita ikubwira kujya ku kigo nderabuzima. Icyo gisubizo gitangwa n'amategeko y'umutekano,
  si porogaramu y'ubwenge bw'ubukorano.
- Mu bihe byihutirwa, jya ku kigo nderabuzima kiri hafi cyangwa uhamagare **912**.

### Amakuru akomoka he
- Ibisubizo: porogaramu y'ururimi yatojwe ku bibazo n'ibisubizo 513 ku mirire y'abana n'ababyeyi,
  byagenzuwe ku mutekano kandi Ikinyarwanda cyasuzumwe n'ukivuga kavukire.
- Gahunda y'amafunguro: imbonerahamwe y'ibiribwa yatanzwe n'inzobere mu mirire i Kigali, ifite impapuro 5:
  **ibiribwa 2.395**, buri kimwe gifite intungamubiri 33. Gahunda ikoresha **ibiribwa 33 bisanzwe mu Rwanda**
  biyirimo, agaciro kabyo kagenzuwe hakoreshejwe USDA, n'ibyo umubiri ukeneye bya OMS/FAO bijyanye n'imyaka
  y'umwana.
""",
}
