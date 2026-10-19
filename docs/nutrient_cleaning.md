# Nutrient cleaning: serving basis, units and column shift

**Source:** `data/raw/food_dataset.xlsx` (Kaggle Food Nutrition Dataset, 2,395 foods). The raw file is never modified.
**Code:** `src/nutriassist/food_data/clean_nutrients.py`, called by `src/nutriassist/food_data/build_foods.py`.
**Generated counts:** `data/processed/cleaning_report.md`.

Comparing workbook rows with USDA FoodData Central values for the same foods turned up four problems. Each one is listed below with its evidence and the rule that fixes it.

## 1. Values are per typical serving, not per 100 g

A banana row lists 134 kcal and 112.4 g of water, which is one extra-large banana (USDA: 152 g, 135 kcal, 113.8 g water). Raw spinach lists 7 kcal and 27.4 g of water, which is one cup (30 g). There is no serving-size column.

**Rule.** Serving weight = water + protein + fat + carbohydrates (g). Every value is then given both per serving and per 100 g (`value × 100 / serving_g`). Ash is not in the workbook, so the weight runs about 1–2% low. For the banana, the estimate is 148.8 g against USDA's 152 g.

**Check.** Calories agree with Atwater energy (4·protein + 4·carbs + 9·fat) within ±20% for 90% of foods, so the macronutrient columns are consistent and can be summed.

## 2. Several units differ from the usual ones

| Nutrient | Workbook unit | Evidence | Published unit |
|---|---|---|---|
| Sodium | g | Cheddar, 28 g: 0.2 (USDA 182 mg) | mg (× 1000) |
| Selenium | mg | Salmon, ~200 g: 0.1 (≈ 80 mcg) | mcg (× 1000) |
| Folate (`vitamin_b11`) | mg | Spinach, 30 g: 0.064 (USDA 58 mcg) | mcg (× 1000) |
| Vitamin K | mg | Spinach, 30 g: 0.1 (USDA 145 mcg) | mcg (× 1000) |
| Vitamins A, B12, D | mg (inferred) | Values sit in the 0–0.1 range | mcg (× 1000) |

All other columns use the expected units (kcal, g, mg).

## 3. In 300 rows the micronutrient block is shifted one column right

In the banana row, `selenium = 537` is really potassium (USDA 544 mg), `manganese = 40.5` is magnesium (41 mg), `copper = 7.5` is calcium (7.6 mg) and `vitamin_d = 13.1` is vitamin C (13.2 mg). The same one-column pattern runs through the whole block from `vitamin_a` to `zinc` in workbook order. Avocado was checked against USDA for every column and fits the same mapping.

**Detection.** Three signals that a shift produces: selenium > potassium, copper > 5 mg, manganese > 15 mg. A row is corrected when **two or more** signals fire. A single signal can be real: canned oysters really do have 7.2 mg of copper. Those 94 rows are only flagged `possible_column_shift`.

**Correction.** Each column takes the value of the column to its right. The true zinc value cannot be recovered and is set to missing (`lost_in_shift`). The `source_column` field records which workbook cell each value came from. After correction, 299 of the 300 rows no longer trigger the detector.

## 4. Very small values are unreliable; zeros are ambiguous

About 22% of cells fall between 0 and 0.1. Many of them are implausible: one tablespoon of cream cheese lists 0.092 mg (92 mcg) of vitamin B12, while the real value is about 0.03 mcg. A further 23% of cells are exactly 0. Raw sorghum, for example, lists magnesium as 0, while USDA gives 165 mg/100 g, so a 0 can mean "not measured".

**Rule.** These values are kept but labelled. Generated Q&A and the meal planner should only use `value_quality == "ok"`.

## Output fields

**`foods.csv`**: `serving_g_estimated`, `basis_confidence`, `quality_flags`

| `basis_confidence` | Meaning |
|---|---|
| `high` | Per-100 g values can be trusted |
| `low` | Serving under 5 g (rounding noise is multiplied 20× or more), energy density above 9.1 kcal/g, or calories off from Atwater by more than 25–33% |
| `unusable` | No serving weight could be estimated; no per-100 g values |

**`food_nutrients.csv`**: `amount_per_serving`, `amount_per_100g`, `unit` (canonical), `value_quality`, `source_column`

| `value_quality` | Meaning |
|---|---|
| `ok` | At or above the 0.1 precision floor |
| `below_precision` | Between 0 and 0.1 in workbook units; likely noise |
| `zero_or_missing` | Exactly 0; the workbook does not distinguish the two |
| `lost_in_shift` | Zinc in a corrected row |

## Validation against USDA (per 100 g, after cleaning)

| Food | kcal | Protein g | Vit C mg | Calcium mg | Iron mg | Potassium mg |
|---|---|---|---|---|---|---|
| Banana *(shift corrected)* | 90 / 89 | 1.1 / 1.1 | 8.8 / 8.7 | 5.0 / 5 | 0.3 / 0.26 | 361 / 358 |
| Cassava | 161 / 160 | 1.4 / 1.4 | 20.7 / 20.6 | 16 / 16 | 0.3 / 0.27 | 273 / 271 |
| Avocado *(shift corrected)* | 163 / 160 | 2.0 / 2.0 | 10.2 / 10 | 12 / 12 | 0.6 / 0.55 | 493 / 485 |
| Spinach, raw | 24 / 23 | 3.1 / 2.9 | 28.5 / 28.1 | 101 / 99 | 2.7 / 2.7 | 568 / 558 |
| Plantain, raw | 123 / 122 | 1.3 / 1.3 | 18.6 / 18.4 | 3 / 3 | 0.6 / 0.6 | 493 / 499 |
| Amaranth leaves, raw | 22 / 23 | 2.5 / 2.5 | 43.8 / 43.3 | 218 / 215 | 2.2 / 2.3 | 620 / 611 |

Each cell shows *workbook after cleaning / USDA FoodData Central*.
