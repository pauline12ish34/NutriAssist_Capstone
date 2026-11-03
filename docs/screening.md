# Growth check: malnutrition screening from CHW measurements

The **Growth check** tab screens a child aged 0–59 months for malnutrition from the measurements that
community health workers (abajyanama b'ubuzima) already take at monthly growth monitoring: **weight, MUAC and,
where a height board is available, length/height**, plus a check for swelling of both feet (oedema).
These are also written in the child's health booklet, so a caregiver can enter them too.

Code: `src/nutriassist/screening/` (`growth.py` z-scores, `screening.py` rules, `messages.py` texts).

## Why measurements and not photos

No public image dataset or model for child malnutrition from African or Rwandan children was found. The
closest model (NutriScreener, IIT Jodhpur / AIIMS Jodhpur, AAAI 2026) needs an institutional licence, is
research-only, may not be redistributed and was not validated on African children. Child photos are also
sensitive personal data under Rwanda's Law No. 058/2021. Measurements need no new equipment, no photos and
use the international WHO standard. Image screening is left as future work.

## How it works

1. **Z-scores** with the WHO Child Growth Standards (2006), from WHO's official expanded tables
   (`data/raw/who_growth_standards/`, converted by `scripts/build_who_tables.py` into
   `data/reference/who_growth_lms.csv`):
   - weight-for-age (underweight), by age in days
   - length/height-for-age (stunting), by age in days
   - weight-for-length (under 2 years) or weight-for-height (from 2 years) (wasting), by 0.1 cm

   `z = ((y/M)^L − 1) / (L·S)`, with WHO's restricted form beyond ±3 SD for the weight indicators.
   Values outside the WHO Anthro plausibility limits (HAZ ±6, WAZ −6/+5, WHZ ±5) are flagged as probable
   measuring or typing mistakes.
2. **Classification** by the worst finding:

| Level | Rule | What the app does |
|---|---|---|
| 🔴 Severe | oedema, MUAC < 11.5 cm (6–59 months), WHZ < −3 | Health centre **today**; no meal plan (food at home is not the treatment) |
| 🟡 Follow-up | MUAC 11.5–12.5 cm, WHZ < −2 or > +2, HAZ < −2, WAZ < −2 | Refer for a check + condition-specific feeding advice + 1-day meal plan |
| ⚪ Check | a flagged z-score | Ask to check the age and measurements and measure again |
| 🟢 Normal | none of the above | Keep coming to monthly growth monitoring + meal plan |

   MUAC is only used from 6 months. Under 6 months there is no meal plan; a baby with a problem is sent to the
   health centre for a breastfeeding check.
3. **The meal plan follows the result** (`PlanRequest.conditions` in `src/nutriassist/planner/planner.py`):

| Found | How the plan changes |
|---|---|
| Wasting or underweight | Catch-up growth: +25% energy and protein (WHO 2012 technical note on supplementary foods for moderate acute malnutrition: about 25 kcal/kg/day extra), one extra snack, and energy and protein weigh more when foods are chosen |
| Stunting | The planner already gives a food from animals (milk, egg, fish, meat) every day when the family has one, so the choice is not changed; the plan says so, or warns and suggests milk, an egg or indagara when the chosen foods have none |
| Overweight | No added fat (avocado, groundnut paste) and energy weighs less; energy stays at the normal need for the age |

   The plan shows what was changed, and its last tip says it does not replace the health centre.
4. All results and advice are **fixed texts in English and Kinyarwanda** (`messages.py`), never written by
   the language model, so the same measurements always give the same, traceable answer.

## Validation

`tests/test_screening.py` checks the z-score code against WHO's own numbers: every row of the eight WHO
tables (9,832 rows, boys and girls) prints the −3, −2, +2 and +3 SD values, and the code returns those
z-scores to within 0.01 for all of them.

The notebook (section 9.2) turns the same tables into a classification test: 61,396 measurements placed
0.01 kg or cm on each side of every WHO line, plus the medians, each with a known class (severe, moderate,
normal, high). The app's z-scores and cut-offs classify all of them correctly (accuracy, precision, recall
and F1 = 1.00 for every class). Testing this close to the lines caught one bug while building it: z-scores
were rounded to 2 decimals before classifying, so a child at −2.004 counted as normal. Classification now
uses the exact value and only the display is rounded. Other tests cover the median child (z ≈ 0), the restricted z-score
beyond −3, the lying/standing correction (0.7 cm), each classification rule, input limits and both languages.

## Context: Rwanda 2025

From the 2025 Rwanda DHS Key Indicators Report (NISR, Table 13; `data/Nutritional_Status_of_Children__2025_/`),
children under 5: **stunting 26.8%** (severe 6.4%), **wasting 0.9%**, **underweight 6.1%**, overweight 5.1%.
Stunting is about 30 times more common than wasting and peaks at 12–23 months (33.2%), so measuring height
matters most. The app shows the national stunting figure when a child is stunted.

## Limitations and future work

- Kinyarwanda texts were drafted and still need review by a native speaker.
- Age is entered in completed months (converted to days), not from the date of birth, so z-scores can differ
  slightly from WHO Anthro.
- Validation on child-level Rwanda DHS records (requested from the DHS Program) is future work, as is image-based
  screening.
