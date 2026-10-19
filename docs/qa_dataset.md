# QA dataset: scope, curation and splits

**Scope:** caregivers of children aged 0–59 months in Rwanda, plus maternal nutrition during pregnancy and breastfeeding. Answers are in English and Kinyarwanda.
**Build:** `python -m src.qa.build_qa_dataset`. Counts are in `data/QA_data/processed/qa_report.md`.

## Inputs

| File | What it holds |
|---|---|
| `data/QA_data/malnutrition_dataset_final.jsonl` | The original 135 pairs. Never modified. |
| `data/QA_data/curated/revisions.jsonl` | One decision per original pair: `keep`, `edit`, `redirect` or `drop`, with a reason. |
| `data/QA_data/curated/new_en.jsonl` | New English pairs, each with paraphrases. |
| `data/QA_data/curated/new_rw*.jsonl` | Kinyarwanda pairs. A pair shares its `group` with the English pair it translates. `mix-*` groups are code-mixed questions. |
| `data/reference/food_names_rw.csv` | Kinyarwanda names linked to food-table rows that were checked against USDA. |

## Curation rules

1. **Drop** adult, adolescent and feeding-centre management content, plus near-duplicates.
2. **Redirect** clinician protocols (IV fluids, drug doses, transfusion). The question stays; the answer explains the problem in plain words, says what is safe to do now, and sends the caregiver to the health centre. The model must never learn to give doses.
3. **Edit** answers that are out of date or unsafe: the WHO 1999 criteria were replaced with MUAC thresholds in cm; honey was removed for infants; meal frequency was corrected to the WHO age bands; local foods and Rwandan services were added.
4. **Nutrient answers** are templated from the cleaned food table. Only rows with `basis_confidence == "high"`, `value_quality == "ok"` and a manual USDA check are used. Some rows were excluded because their values are wrong (chicken liver iron, beef liver iron) or unreliable (vitamin A).
5. **Out-of-scope** examples teach the model to decline politely and restate what it covers.

## Splits

Splits are by `group`, stratified by category (75/10/15, seed 42). A question, its paraphrases and its translation always land in the same split. Training uses every paraphrase. Validation and test use only the main question. Held-out paraphrases go to `heldout_paraphrases.jsonl`, which measures how well the model handles rewording.

Each example has the form `system` → `user` → `assistant`, with the same system prompt the app will use at inference.

## Kinyarwanda review

Kinyarwanda pairs start as drafts (`review: pending_native_review`). A native speaker reviews them in `data/QA_data/review/kinyarwanda_review.xlsx`:

1. `python -m src.qa.review_sheet` writes or refreshes the sheet. Decisions already made are kept.
2. For each row, set `status` to `approved`, `corrected` (and fill the `*_corrected` columns), or `rejected`.
3. `python -m src.qa.build_qa_dataset` applies the decisions. Adding `--reviewed-only` keeps only approved or corrected pairs; use it for the final training run.

An approval only covers the draft text that was reviewed. If a draft changes later, the row goes back to `pending`. The review counts in `qa_report.md` can be reported as "pairs verified by a native speaker".

## Known limits

- **Kinyarwanda pairs are unverified until reviewed.**
- Isombe, isambaza, indagara, ikivuguto and other local foods are not in the workbook. They need values from a Rwandan or FAO food composition table before they can have numeric answers.
- Pinto beans stand in for common Rwandan beans, and plantain stands in for cooking bananas.
