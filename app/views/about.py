"""How-to-use page: what the assistant does, how to use it, and its limits."""

import streamlit as st

from i18n import language, t

CONTENT = {
    "en": """
### What NutriAssist-RW does
- **Answers questions** about breastfeeding, feeding children from 6 months to 5 years, nutrition in pregnancy
  and while breastfeeding, and local Rwandan foods, in **English or Kinyarwanda**.
- **Makes meal plans** for a child aged 6 to 59 months from local foods, with amounts in tablespoons.

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
- Meal plans: WHO/FAO nutrient needs and a food table checked against USDA values.
""",
    "rw": """
### NutriAssist-RW ikora iki
- **Isubiza ibibazo** ku konsa, kugaburira abana kuva ku mezi 6 kugeza ku myaka 5, imirire y'umugore utwite
  n'uwonsa, n'ibiribwa byo mu Rwanda, mu **Cyongereza cyangwa mu Kinyarwanda**.
- **Ikora gahunda y'amafunguro** y'umwana ufite hagati y'amezi 6 na 59, ikoresheje ibiribwa byo mu Rwanda,
  n'ingano mu biyiko.

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
- Gahunda y'amafunguro: ibyo umubiri ukeneye bya OMS/FAO n'imbonerahamwe y'ibiribwa yagenzuwe hakoreshejwe USDA.
""",
}

st.title(f"ℹ️ {t('page_about')}")
st.markdown(CONTENT[language()])
