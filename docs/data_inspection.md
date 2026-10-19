# Food dataset inspection report

**Source inspected:** `data/raw/food_dataset.xlsx` (read-only). **Inspection date:** 2026-10-14.

## Executive summary

- The workbook contains **5 sheets**, all visible: `FOOD-DATA-GROUP1`, `FOOD-DATA-GROUP2`, `FOOD-DATA-GROUP3`, `FOOD-DATA-GROUP4`, `FOOD-DATA-GROUP5`. No hidden sheets were found.
- Every sheet has the same 37-column layout, with the first row as the header and no merged cells, title rows, notes, comments, Excel tables, defined names, or external links detected.
- There are 2,395 total data rows and 2,395 unique food names across the workbook. Food names are disjoint across sheets, so `food` is the practical record key but is not a cross-sheet join key here. The two unnamed integer columns appear to be duplicated source row indexes.
- No formulas were found. `Nutrition Density` is stored as typed numeric values; its calculation method is not encoded in the workbook.
- Numeric values contain no negatives. Many values exceed 100, which is not automatically impossible for nutrients measured in mg/mcg or kcal, but would be impossible for gram quantities in a 100 g serving. Serving basis and units must be confirmed before cleaning.

## 1. Workbook and sheet inventory

| Sheet | Visibility | Data rows | Columns | Header row | Merged cells |
|---|---|---:|---:|---:|---|
| `FOOD-DATA-GROUP1` | visible | 551 | 37 | row 1 | none |
| `FOOD-DATA-GROUP2` | visible | 319 | 37 | row 1 | none |
| `FOOD-DATA-GROUP3` | visible | 571 | 37 | row 1 | none |
| `FOOD-DATA-GROUP4` | visible | 232 | 37 | row 1 | none |
| `FOOD-DATA-GROUP5` | visible | 722 | 37 | row 1 | none |

All sheets occupy a contiguous range beginning at `A1`, with no non-empty rows above or below the detected table. There are no merged cells.

## 2. Common schema, data types, and missingness

The following schema is identical in all five sheets. Missing counts are per sheet; every column has zero missing values in every sheet.

| Column | pandas dtype | Missing in each sheet | Likely unit / interpretation |
|---|---|---:|---|
| `Unnamed: 0.1` | `int64` | 0, 0, 0, 0, 0 | index; unitless |
| `Unnamed: 0` | `int64` | 0, 0, 0, 0, 0 | index; unitless |
| `food` | `str` | 0, 0, 0, 0, 0 | food name; text |
| `Caloric Value` | `int64` | 0, 0, 0, 0, 0 | kcal (unit label not present) |
| `Fat` | `float64` | 0, 0, 0, 0, 0 | g (assumed; confirm) |
| `Saturated Fats` | `float64` | 0, 0, 0, 0, 0 | g (assumed; confirm) |
| `Monounsaturated Fats` | `float64` | 0, 0, 0, 0, 0 | g (assumed; confirm) |
| `Polyunsaturated Fats` | `float64` | 0, 0, 0, 0, 0 | g (assumed; confirm) |
| `Carbohydrates` | `float64` | 0, 0, 0, 0, 0 | g (assumed; confirm) |
| `Sugars` | `float64` | 0, 0, 0, 0, 0 | g (assumed; confirm) |
| `Protein` | `float64` | 0, 0, 0, 0, 0 | g (assumed; confirm) |
| `Dietary Fiber` | `float64` | 0, 0, 0, 0, 0 | g (assumed; confirm) |
| `Cholesterol` | `float64` | 0, 0, 0, 0, 0 | mg (assumed; confirm) |
| `Sodium` | `float64` | 0, 0, 0, 0, 0 | mg (assumed; confirm) |
| `Water` | `float64` | 0, 0, 0, 0, 0 | g or mL-equivalent (confirm) |
| `Vitamin A` | `float64` | 0, 0, 0, 0, 0 | mcg or IU (confirm) |
| `Vitamin B1` | `float64` | 0, 0, 0, 0, 0 | mg (assumed; confirm) |
| `Vitamin B11` | `float64` | 0, 0, 0, 0, 0 | unit unclear; likely a vitamin field, confirm |
| `Vitamin B12` | `float64` | 0, 0, 0, 0, 0 | mcg (assumed; confirm) |
| `Vitamin B2` | `float64` | 0, 0, 0, 0, 0 | mg (assumed; confirm) |
| `Vitamin B3` | `float64` | 0, 0, 0, 0, 0 | mg (assumed; confirm) |
| `Vitamin B5` | `float64` | 0, 0, 0, 0, 0 | mg (assumed; confirm) |
| `Vitamin B6` | `float64` | 0, 0, 0, 0, 0 | mg (assumed; confirm) |
| `Vitamin C` | `float64` | 0, 0, 0, 0, 0 | mg (assumed; confirm) |
| `Vitamin D` | `float64` | 0, 0, 0, 0, 0 | mcg or IU (confirm) |
| `Vitamin E` | `float64` | 0, 0, 0, 0, 0 | mg (assumed; confirm) |
| `Vitamin K` | `float64` | 0, 0, 0, 0, 0 | mcg (assumed; confirm) |
| `Calcium` | `float64` | 0, 0, 0, 0, 0 | mg (assumed; confirm) |
| `Copper` | `float64` | 0, 0, 0, 0, 0 | mg or mcg (confirm) |
| `Iron` | `float64` | 0, 0, 0, 0, 0 | mg (assumed; confirm) |
| `Magnesium` | `float64` | 0, 0, 0, 0, 0 | mg (assumed; confirm) |
| `Manganese` | `float64` | 0, 0, 0, 0, 0 | mg (assumed; confirm) |
| `Phosphorus` | `float64` | 0, 0, 0, 0, 0 | mg (assumed; confirm) |
| `Potassium` | `float64` | 0, 0, 0, 0, 0 | mg (assumed; confirm) |
| `Selenium` | `float64` | 0, 0, 0, 0, 0 | mcg (assumed; confirm) |
| `Zinc` | `float64` | 0, 0, 0, 0, 0 | mg (assumed; confirm) |
| `Nutrition Density` | `float64` | 0, 0, 0, 0, 0 | calculated score; unitless unless defined by nutritionist |

**Column order:** `Unnamed: 0.1`, `Unnamed: 0`, `food`, `Caloric Value`, `Fat`, `Saturated Fats`, `Monounsaturated Fats`, `Polyunsaturated Fats`, `Carbohydrates`, `Sugars`, `Protein`, `Dietary Fiber`, `Cholesterol`, `Sodium`, `Water`, `Vitamin A`, `Vitamin B1`, `Vitamin B11`, `Vitamin B12`, `Vitamin B2`, `Vitamin B3`, `Vitamin B5`, `Vitamin B6`, `Vitamin C`, `Vitamin D`, `Vitamin E`, `Vitamin K`, `Calcium`, `Copper`, `Iron`, `Magnesium`, `Manganese`, `Phosphorus`, `Potassium`, `Selenium`, `Zinc`, `Nutrition Density`.

## 3. Per-sheet detail

### `FOOD-DATA-GROUP1`

- **Contents:** mixed food records; examples indicate a broad food category/group. The first foods are: cream cheese, neufchatel cheese, requeijao cremoso light catupiry.
- **Shape:** 551 rows x 37 columns; header row 1; range `A1:AK552`; no merged cells; no notes/comments above or below.
- **Data types and missing values:** same common schema above; all 37 columns have 0 missing values.
- **Duplicate food names:** none within this sheet (`food` duplicated count = 0).
- **Formulas:** none; all inspected cells are typed values.

**First three data rows** (all 37 columns; blank cells are shown as empty):

| Unnamed: 0.1 | Unnamed: 0 | food | Caloric Value | Fat | Saturated Fats | Monounsaturated Fats | Polyunsaturated Fats | Carbohydrates | Sugars | Protein | Dietary Fiber | Cholesterol | Sodium | Water | Vitamin A | Vitamin B1 | Vitamin B11 | Vitamin B12 | Vitamin B2 | Vitamin B3 | Vitamin B5 | Vitamin B6 | Vitamin C | Vitamin D | Vitamin E | Vitamin K | Calcium | Copper | Iron | Magnesium | Manganese | Phosphorus | Potassium | Selenium | Zinc | Nutrition Density |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 0 | cream cheese | 51 | 5.0 | 2.9 | 1.3 | 0.2 | 0.8 | 0.5 | 0.9 | 0.0 | 14.6 | 0.016 | 7.6 | 0.2 | 0.033 | 0.064 | 0.092 | 0.097 | 0.084 | 0.052 | 0.096 | 0.004 | 0.0 | 0.0 | 0.1 | 0.008 | 14.1 | 0.082 | 0.027 | 1.3 | 0.091 | 15.5 | 19.1 | 0.039 | 7.07 |
| 1 | 1 | neufchatel cheese | 215 | 19.4 | 10.9 | 4.9 | 0.8 | 3.1 | 2.7 | 7.8 | 0.0 | 62.9 | 0.3 | 53.6 | 0.2 | 0.099 | 0.079 | 0.09 | 0.1 | 0.2 | 0.5 | 0.078 | 0.0 | 0.0 | 0.3 | 0.045 | 99.5 | 0.034 | 0.1 | 8.5 | 0.088 | 117.3 | 129.2 | 0.054 | 0.7 | 130.1 |
| 2 | 2 | requeijao cremoso light catupiry | 49 | 3.6 | 2.3 | 0.9 | 0.0 | 0.9 | 3.4 | 0.8 | 0.1 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 5.4 |

**Nutrition Density range:** 1.025 to 1337.0; 0 zero values.

### `FOOD-DATA-GROUP2`

- **Contents:** mixed food records; examples indicate a broad food category/group. The first foods are: eggnog, beer light, beer budweiser.
- **Shape:** 319 rows x 37 columns; header row 1; range `A1:AK320`; no merged cells; no notes/comments above or below.
- **Data types and missing values:** same common schema above; all 37 columns have 0 missing values.
- **Duplicate food names:** none within this sheet (`food` duplicated count = 0).
- **Formulas:** none; all inspected cells are typed values.

**First three data rows** (all 37 columns; blank cells are shown as empty):

| Unnamed: 0.1 | Unnamed: 0 | food | Caloric Value | Fat | Saturated Fats | Monounsaturated Fats | Polyunsaturated Fats | Carbohydrates | Sugars | Protein | Dietary Fiber | Cholesterol | Sodium | Water | Vitamin A | Vitamin B1 | Vitamin B11 | Vitamin B12 | Vitamin B2 | Vitamin B3 | Vitamin B5 | Vitamin B6 | Vitamin C | Vitamin D | Vitamin E | Vitamin K | Calcium | Copper | Iron | Magnesium | Manganese | Phosphorus | Potassium | Selenium | Zinc | Nutrition Density |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 0 | eggnog | 224 | 10.6 | 6.6 | 3.3 | 0.5 | 20.4 | 20.4 | 11.6 | 0.0 | 149.9 | 0.1 | 209.7 | 0.1 | 0.074 | 0.02 | 0.006 | 0.5 | 0.3 | 1.1 | 0.1 | 3.8 | 0.055 | 0.5 | 0.011 | 330.2 | 0.051 | 0.5 | 48.3 | 0.024 | 276.9 | 419.1 | 0.094 | 1.2 | 377.2 |
| 1 | 1 | beer light | 96 | 0.0 | 0.0 | 0.0 | 0.0 | 5.4 | 0.3 | 0.8 | 0.0 | 0.0 | 0.095 | 313.1 | 0.0 | 0.083 | 0.079 | 0.0 | 0.069 | 1.3 | 0.067 | 0.1 | 0.0 | 0.0 | 0.0 | 0.0 | 13.2 | 0.095 | 0.014 | 16.5 | 0.094 | 39.6 | 69.3 | 0.077 | 0.044 | 19.456 |
| 2 | 2 | beer budweiser | 12 | 0.0 | 0.0 | 0.0 | 0.0 | 0.9 | 0.0 | 0.1 | 0.0 | 0.0 | 0.095 | 27.4 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.2 | 0.095 | 0.0 | 2.1 | 0.038 | 3.8 | 9.7 | 0.0 | 0.0 | 2.2 |

**Nutrition Density range:** 0.0 to 1533.5; 4 zero values.

### `FOOD-DATA-GROUP3`

- **Contents:** mixed food records; examples indicate a broad food category/group. The first foods are: nectarine, kiwifruit gold, prickly pear raw.
- **Shape:** 571 rows x 37 columns; header row 1; range `A1:AK572`; no merged cells; no notes/comments above or below.
- **Data types and missing values:** same common schema above; all 37 columns have 0 missing values.
- **Duplicate food names:** none within this sheet (`food` duplicated count = 0).
- **Formulas:** none; all inspected cells are typed values.

**First three data rows** (all 37 columns; blank cells are shown as empty):

| Unnamed: 0.1 | Unnamed: 0 | food | Caloric Value | Fat | Saturated Fats | Monounsaturated Fats | Polyunsaturated Fats | Carbohydrates | Sugars | Protein | Dietary Fiber | Cholesterol | Sodium | Water | Vitamin A | Vitamin B1 | Vitamin B11 | Vitamin B12 | Vitamin B2 | Vitamin B3 | Vitamin B5 | Vitamin B6 | Vitamin C | Vitamin D | Vitamin E | Vitamin K | Calcium | Copper | Iron | Magnesium | Manganese | Phosphorus | Potassium | Selenium | Zinc | Nutrition Density |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 0 | nectarine | 66 | 0.5 | 0.066 | 0.1 | 0.2 | 15.8 | 11.8 | 1.6 | 2.6 | 0.0 | 0.0 | 131.4 | 0.0 | 0.0 | 0.026 | 0.037 | 0.0 | 0.032 | 1.7 | 0.3 | 0.007 | 8.1 | 0.0 | 1.2 | 0.081 | 9.0 | 0.1 | 0.4 | 13.5 | 0.002 | 39.0 | 301.5 | 0.0 | 20.735 |
| 1 | 1 | kiwifruit gold | 51 | 0.2 | 0.008 | 0.099 | 0.051 | 12.8 | 10.0 | 0.8 | 1.1 | 0.0 | 0.046 | 66.8 | 0.091 | 0.0 | 0.051 | 0.058 | 0.07 | 0.2 | 0.4 | 0.067 | 130.7 | 0.0 | 1.1 | 0.074 | 13.8 | 0.1 | 0.2 | 9.7 | 0.072 | 20.3 | 255.2 | 0.003 | 0.077 | 159.686 |
| 2 | 2 | prickly pear raw | 8 | 0.072 | 0.0 | 0.0 | 0.0 | 1.9 | 0.2 | 0.001 | 1.0 | 0.0 | 0.065 | 17.0 | 0.0 | 0.058 | 0.0 | 0.0 | 0.038 | 0.04 | 0.0 | 0.078 | 2.1 | 0.0 | 0.0 | 0.018 | 34.2 | 0.051 | 0.021 | 13.1 | 0.1 | 2.1 | 24.7 | 0.023 | 0.073 | 39.263 |

**Nutrition Density range:** 0.0 to 1264.074; 1 zero values.

### `FOOD-DATA-GROUP4`

- **Contents:** mixed food records; examples indicate a broad food category/group. The first foods are: chocolate pudding fat free, tapioca pudding, tapioca pudding fat free.
- **Shape:** 232 rows x 37 columns; header row 1; range `A1:AK233`; no merged cells; no notes/comments above or below.
- **Data types and missing values:** same common schema above; all 37 columns have 0 missing values.
- **Duplicate food names:** none within this sheet (`food` duplicated count = 0).
- **Formulas:** none; all inspected cells are typed values.

**First three data rows** (all 37 columns; blank cells are shown as empty):

| Unnamed: 0.1 | Unnamed: 0 | food | Caloric Value | Fat | Saturated Fats | Monounsaturated Fats | Polyunsaturated Fats | Carbohydrates | Sugars | Protein | Dietary Fiber | Cholesterol | Sodium | Water | Vitamin A | Vitamin B1 | Vitamin B11 | Vitamin B12 | Vitamin B2 | Vitamin B3 | Vitamin B5 | Vitamin B6 | Vitamin C | Vitamin D | Vitamin E | Vitamin K | Calcium | Copper | Iron | Magnesium | Manganese | Phosphorus | Potassium | Selenium | Zinc | Nutrition Density |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 0 | chocolate pudding fat free | 105 | 0.3 | 0.0 | 0.0 | 0.0 | 23.6 | 17.8 | 2.2 | 0.3 | 1.1 | 0.1 | 86.1 | 0.0 | 0.021 | 0.06 | 0.069 | 0.046 | 0.022 | 0.2 | 0.084 | 0.0 | 0.0 | 0.0 | 0.098 | 44.1 | 0.035 | 1.9 | 17.0 | 0.04 | 61.0 | 235.0 | 0.052 | 0.3 | 72.4 |
| 1 | 1 | tapioca pudding | 143 | 4.3 | 1.1 | 2.8 | 0.088 | 23.9 | 16.4 | 2.1 | 0.0 | 1.1 | 0.2 | 79.0 | 0.0 | 0.025 | 0.003 | 0.021 | 0.1 | 0.031 | 0.3 | 0.052 | 0.3 | 0.0 | 0.2 | 0.01 | 78.1 | 0.026 | 0.1 | 6.6 | 0.096 | 66.0 | 101.2 | 0.0 | 0.2 | 108.8 |
| 2 | 2 | tapioca pudding fat free | 105 | 0.4 | 0.1 | 0.08 | 0.067 | 23.9 | 15.9 | 1.6 | 0.0 | 1.1 | 0.2 | 85.4 | 0.0 | 0.044 | 0.096 | 0.012 | 0.043 | 0.1 | 0.056 | 0.039 | 0.3 | 0.0 | 0.072 | 0.0 | 58.2 | 0.004 | 0.1 | 5.6 | 0.023 | 73.9 | 78.4 | 0.0 | 0.2 | 84.5 |

**Nutrition Density range:** 0.0 to 3911.4; 4 zero values.

### `FOOD-DATA-GROUP5`

- **Contents:** mixed food records; examples indicate a broad food category/group. The first foods are: margarine with yoghurt, sunflower seed butter, hazelnut oil.
- **Shape:** 722 rows x 37 columns; header row 1; range `A1:AK723`; no merged cells; no notes/comments above or below.
- **Data types and missing values:** same common schema above; all 37 columns have 0 missing values.
- **Duplicate food names:** none within this sheet (`food` duplicated count = 0).
- **Formulas:** none; all inspected cells are typed values.

**First three data rows** (all 37 columns; blank cells are shown as empty):

| Unnamed: 0.1 | Unnamed: 0 | food | Caloric Value | Fat | Saturated Fats | Monounsaturated Fats | Polyunsaturated Fats | Carbohydrates | Sugars | Protein | Dietary Fiber | Cholesterol | Sodium | Water | Vitamin A | Vitamin B1 | Vitamin B11 | Vitamin B12 | Vitamin B2 | Vitamin B3 | Vitamin B5 | Vitamin B6 | Vitamin C | Vitamin D | Vitamin E | Vitamin K | Calcium | Copper | Iron | Magnesium | Manganese | Phosphorus | Potassium | Selenium | Zinc | Nutrition Density |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 0 | margarine with yoghurt | 88 | 9.8 | 1.9 | 5.6 | 2.0 | 0.073 | 0.0 | 0.058 | 0.0 | 0.0 | 0.018 | 3.9 | 0.1 | 0.074 | 0.086 | 0.073 | 0.005 | 0.097 | 0.0 | 0.075 | 0.082 | 0.0 | 0.7 | 0.002 | 2.8 | 0.001 | 0.027 | 0.3 | 0.0 | 2.2 | 3.5 | 0.0 | 0.008 | 12.971 |
| 1 | 1 | sunflower seed butter | 99 | 8.8 | 0.7 | 6.2 | 1.6 | 3.7 | 1.7 | 2.8 | 0.9 | 0.0 | 0.065 | 0.1 | 0.0 | 0.021 | 0.005 | 0.0 | 0.075 | 1.1 | 0.2 | 0.013 | 0.4 | 0.0 | 3.7 | 0.0 | 10.2 | 0.3 | 0.7 | 49.8 | 0.3 | 106.6 | 92.2 | 0.075 | 0.8 | 27.5 |
| 2 | 2 | hazelnut oil | 120 | 13.6 | 1.0 | 10.6 | 1.4 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 6.4 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 13.6 |

**Nutrition Density range:** 0.1 to 918.8; 0 zero values.

## 4. What each sheet appears to contain

| Sheet | Interpretation from food names | Relationship to other sheets |
|---|---|---|
| `FOOD-DATA-GROUP1` | foods including cheeses and fish; broad food records | Same schema and field meanings; no food names overlap another sheet. |
| `FOOD-DATA-GROUP2` | beverages/alcohol and additional dairy/cheese records | Same schema and field meanings; no food names overlap another sheet. |
| `FOOD-DATA-GROUP3` | fruits and animal foods/meats | Same schema and field meanings; no food names overlap another sheet. |
| `FOOD-DATA-GROUP4` | puddings, cereals, and grain products | Same schema and field meanings; no food names overlap another sheet. |
| `FOOD-DATA-GROUP5` | oils, fats, seeds, nuts, and mushrooms | Same schema and field meanings; no food names overlap another sheet. |

Potential link fields are `food` and the two unnamed index columns. The indexes restart at 0 in every sheet and therefore are only sheet-local row identifiers. `food` values match exactly within each sheet but have **zero pairwise intersections** across all sheets; no cross-sheet relational link exists in this workbook.

- `FOOD-DATA-GROUP1` vs `FOOD-DATA-GROUP2`: 0 matching `food` values; all 551 foods are only in `FOOD-DATA-GROUP1`, and all 319 are only in `FOOD-DATA-GROUP2`.
- `FOOD-DATA-GROUP1` vs `FOOD-DATA-GROUP3`: 0 matching `food` values; all 551 foods are only in `FOOD-DATA-GROUP1`, and all 571 are only in `FOOD-DATA-GROUP3`.
- `FOOD-DATA-GROUP1` vs `FOOD-DATA-GROUP4`: 0 matching `food` values; all 551 foods are only in `FOOD-DATA-GROUP1`, and all 232 are only in `FOOD-DATA-GROUP4`.
- `FOOD-DATA-GROUP1` vs `FOOD-DATA-GROUP5`: 0 matching `food` values; all 551 foods are only in `FOOD-DATA-GROUP1`, and all 722 are only in `FOOD-DATA-GROUP5`.
- `FOOD-DATA-GROUP2` vs `FOOD-DATA-GROUP3`: 0 matching `food` values; all 319 foods are only in `FOOD-DATA-GROUP2`, and all 571 are only in `FOOD-DATA-GROUP3`.
- `FOOD-DATA-GROUP2` vs `FOOD-DATA-GROUP4`: 0 matching `food` values; all 319 foods are only in `FOOD-DATA-GROUP2`, and all 232 are only in `FOOD-DATA-GROUP4`.
- `FOOD-DATA-GROUP2` vs `FOOD-DATA-GROUP5`: 0 matching `food` values; all 319 foods are only in `FOOD-DATA-GROUP2`, and all 722 are only in `FOOD-DATA-GROUP5`.
- `FOOD-DATA-GROUP3` vs `FOOD-DATA-GROUP4`: 0 matching `food` values; all 571 foods are only in `FOOD-DATA-GROUP3`, and all 232 are only in `FOOD-DATA-GROUP4`.
- `FOOD-DATA-GROUP3` vs `FOOD-DATA-GROUP5`: 0 matching `food` values; all 571 foods are only in `FOOD-DATA-GROUP3`, and all 722 are only in `FOOD-DATA-GROUP5`.
- `FOOD-DATA-GROUP4` vs `FOOD-DATA-GROUP5`: 0 matching `food` values; all 232 foods are only in `FOOD-DATA-GROUP4`, and all 722 are only in `FOOD-DATA-GROUP5`.

## 5. Units, serving basis, and value checks

The workbook does not include unit annotations, serving-size columns, or a data dictionary. The unit labels below are therefore hypotheses based on conventional nutrition databases, not confirmed facts.

| Field groups | Expected conventional unit (must confirm) |
|---|---|
| Caloric Value | kcal |
| Fat, Saturated Fats, Monounsaturated Fats, Polyunsaturated Fats, Carbohydrates, Sugars, Protein, Dietary Fiber | g |
| Cholesterol, Sodium, Calcium, Iron, Magnesium, Manganese, Phosphorus, Potassium, Zinc, most B vitamins, Vitamin C, Vitamin E | usually mg |
| Vitamin A, B12, D, K, Selenium (and possibly Copper) | often mcg, but not confirmed; Vitamin A/D may be IU |
| Water | usually g per 100 g, but not stated |
| Nutrition Density | unitless calculated score, formula unknown |

**Range checks:** no negative numeric values were found in any sheet. Values above 100 occur in calorie, mineral, vitamin, cholesterol, water, macronutrient, and score columns. This is plausible for kcal/mg/mcg per 100 g, but impossible for g of a single component per 100 g in many cases. In particular, `Water` exceeds 100 in many rows and macronutrients/fats also exceed 100 in some rows, so the workbook cannot be safely assumed to be physically consistent per 100 g without source definitions.

| Sheet | Numeric columns with values > 100 | Interpretation |
|---|---:|---|
| `FOOD-DATA-GROUP1` | 16 columns / 2852 cells | Includes `Water`, `Caloric Value`, and minerals/vitamins; also some g-labelled candidates. Requires unit and serving-basis confirmation. |
| `FOOD-DATA-GROUP2` | 19 columns / 1191 cells | Includes `Water`, `Caloric Value`, and minerals/vitamins; also some g-labelled candidates. Requires unit and serving-basis confirmation. |
| `FOOD-DATA-GROUP3` | 23 columns / 2781 cells | Includes `Water`, `Caloric Value`, and minerals/vitamins; also some g-labelled candidates. Requires unit and serving-basis confirmation. |
| `FOOD-DATA-GROUP4` | 18 columns / 788 cells | Includes `Water`, `Caloric Value`, and minerals/vitamins; also some g-labelled candidates. Requires unit and serving-basis confirmation. |
| `FOOD-DATA-GROUP5` | 20 columns / 2499 cells | Includes `Water`, `Caloric Value`, and minerals/vitamins; also some g-labelled candidates. Requires unit and serving-basis confirmation. |

## 6. Formulas and nutrient-density field

- Formula scan found **0 formula cells** in all sheets; there is no formula to show.
- `Nutrition Density` is a typed `float64` column, not an Excel-calculated column. Values vary substantially (overall observed range 0.0 to 3911.4), including repeated values and zeros. No definition, denominator, reference daily values, or calculation formula is present, so it should not be treated as interpretable/calculable until the nutritionist explains it.

## 7. Language and spelling observations

- All 2,395 food-name values are ASCII/Latin text; no Kinyarwanda-specific names or diacritics were detected by a simple character scan.
- Names are predominantly English-style common names, with brand/product and foreign-language tokens such as `requeijao cremoso light catupiry`, `heidelbeeren jutro`, `profeel proteiinirahka valio`, and `cupu assu oil`. These are not necessarily errors.
- No exact duplicate food names occur within or across sheets. Near-duplicate spellings, translations, singular/plural variants, abbreviations, and brand aliases were not normalized because cleaning is out of scope and no canonical-name rule was supplied.
- Examples of naming conventions requiring a decision include `red salmon sockeye filets smoked`, `crispy chicken strips tyson`, and product/brand qualifiers embedded in `food`.

## 8. Questions to answer before cleaning

1. What is the authoritative unit for every nutrient column, especially `Vitamin A`, `Vitamin D`, `Vitamin K`, `Vitamin B11`, `Vitamin B12`, `Copper`, `Selenium`, and `Water`?
2. Are all measurements intended to be per 100 g edible portion, per serving, or a mixture? If per serving, where is serving size stored?
3. Why do `Water`, fat/macronutrient fields, and some micronutrients exceed 100; are these values unit-scaled (mg/mcg), data-entry errors, or not per 100 g?
4. What are `Unnamed: 0.1` and `Unnamed: 0`: duplicate indexes, source IDs, or meaningful identifiers? Should one be retained?
5. What is the exact definition and formula for `Nutrition Density`, including units, reference values, and whether zero values are valid?
6. What does `Vitamin B11` represent? Is it a valid nutrient field, a mislabeled column, or a source-specific measure?
7. Are the five sheets intentionally disjoint food groups, and should they be combined into one table for the assistant?
8. Is `food` the intended stable identifier, or is there an external food ID/canonical name that should be used for joins and deduplication?
9. Should brand names, product descriptors, foreign-language names, and preparation-state words remain in the canonical food name?
10. Should Kinyarwanda names be added, and if so, should they be translated, stored in a separate language column, or used as aliases?
11. What spelling/alias policy should be applied to near-duplicates (for example, singular/plural, `filets`/`fillets`, brand variants, and raw/cooked/smoked variants)?
12. Are zeros true measured zeros, unavailable values encoded as zero, or rounded values? This affects missing-value handling.
13. Are all values typed source values, or were any exported from formulas before this workbook was delivered? If a source formula specification exists, please provide it.
14. What validation rules should define an impossible food record (macronutrient sum, water plus solids, calorie consistency, micronutrient bounds, and allowable score range)?

## Scope boundary

This is inspection only. The raw workbook was not modified, no cleaning code was added, and no assumptions above should be applied as cleaning rules until the questions are answered.
