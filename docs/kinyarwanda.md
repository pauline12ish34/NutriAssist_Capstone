# Kinyarwanda: why the model's own answers are not shown, and what the app does instead

## The problem

The first trained model (Qwen2.5-1.5B-Instruct + QLoRA, experiment `exp3_lr_5e-4`) answers English
questions well, but its Kinyarwanda answers are unreliable, even for questions it was trained on.
Reading all 36 Kinyarwanda test answers (`outputs/qualitative_test.csv`) shows four kinds of failure:

| Failure | Example (question → start of the model's answer) |
|---|---|
| Repetition loop | *Ibitoki ni ibiryo byiza ku bana?* → "…amazi meza n'ibishyimbo, amazi meza n'ibishyimbo, amazi meza n'ibishyimbo…" |
| Generic food list | *Nshobora guha icyayi umwana wanjye muto?* (tea) → a list of porridge and groundnut foods |
| Off topic | *Kuki gukingiza ari ingenzi…?* (vaccination) → feeding advice |
| Unsafe | *Umwana wanjye aragagara. Nkore iki?* (convulsions) → a food list. (In the app this question never reaches the model: the danger-sign rules answer it.) |

`scripts/failure_analysis.py` flags loops and echoed questions automatically: **11 of the 36 Kinyarwanda
test answers loop, and none of the 42 English ones do.** The other answers are labelled by a native
speaker in `data/QA_data/review/failure_review.xlsx`; the counts are in `outputs/failure_summary.csv`.

The automatic metrics hide this. chrF on Kinyarwanda rose from 16.4 to 30.3 after fine-tuning (+85%),
because the answers now reuse the right vocabulary; they just do not say the right thing with it.

## Why it happens

1. **The base model knows little Kinyarwanda.** Every small open model splits Kinyarwanda words into
   about twice as many tokens as English words (`scripts/tokenizer_fertility.py`,
   `outputs/tokenizer_fertility.csv`):

   | Tokenizer | tokens per English word | tokens per Kinyarwanda word |
   |---|---:|---:|
   | Gemma 3 (1B, 4B) | 1.28 | 2.63 |
   | Gemma 2 (2B) | 1.28 | 2.68 |
   | Llama 3.2 | 1.28 | 2.83 |
   | Qwen 2.5 | 1.31 | 2.88 |

   The differences between models are small: Kinyarwanda is under-represented in all of them. Before
   fine-tuning, Qwen's perplexity on the reference Kinyarwanda answers was 124, against 11 for English.
2. **181 training pairs teach a style, not a language.** Fine-tuning adapts a model to a task in a
   language it already knows; it cannot teach it the language.
3. **Model selection rewarded the collapse.** The final model was chosen by validation ROUGE-L, which
   counts whole matching words. In Kinyarwanda the easiest way to raise it is to repeat frequent
   training phrases ("ku kigo nderabuzima", "ubunyobwa biseye"), so the run with the highest learning
   rate won. The notebook now chooses by **Kinyarwanda chrF**, which credits partly right words.

## What the app does instead

**The app shows Kinyarwanda only from reviewed answers.** Every Kinyarwanda answer in the dataset was
approved by a native speaker; the model is never allowed to write Kinyarwanda for caregivers. The chat
pipeline (`src/nutriassist/assistant.py`):

1. **Danger signs** are answered by fixed messages, as before.
2. **Reviewed answer** (`src/nutriassist/knowledge.py`): when the question asks the same thing as a
   stored question, one of its paraphrases or an approved extra wording, the reviewed answer is
   returned word for word. Questions made from one template ("Garama 100 z'ibijumba…" / "…z'ibirayi…")
   differ only in a food, an illness or an age, so a match is accepted only when both name the same
   foods and illnesses and no conflicting numbers (`src/nutriassist/terms.py`). Without this check,
   "inyama y'inka" (beef) matched "inyama y'inkoko" (chicken) with a score of 0.86 and would have
   returned the wrong nutrient values.
3. **"Did you mean…?"**: when no reviewed question is close enough, the app says it has no checked
   answer and offers up to three reviewed questions as buttons. The caregiver taps the one that fits
   and gets its reviewed answer; the person asking, not the computer, judges whether it fits. A
   suggestion never brings in a food or illness the question did not name. With no suggestion, the
   fixed message refers the caregiver to the community health worker.
4. Questions with no reviewed answer are kept in `logs/unanswered.jsonl` (text, language and time
   only), to show reviewers which answers to write next.
5. **English** is answered by the fine-tuned model, which writes English well, with the dose and
   referral checks.

## Machine translation was tried and rejected

Translating through English (Kinyarwanda question → English → model → English answer → Kinyarwanda)
was built and evaluated (`src/nutriassist/translation.py`, `scripts/evaluate_pipeline.py`) with
NLLB-200 (600M), the largest open translation model that runs on a CPU.

NLLB gets local food words badly wrong in both directions: *ubunyobwa* (groundnuts) became "a drink",
*ikivuguto* (fermented milk) became "spanking", *isombe* became "sugar"; "fermented milk" and "breast
milk" became forms of *ubuki* (honey, which is dangerous for babies under 12 months); "iron" became
*icyuma* (the metal). Writing known terms in the target language before translating
(`Terminology` in `src/nutriassist/terms.py`) fixed these words, but not the sentences around them.

On the 36 Kinyarwanda test questions the translated answers scored higher than the model's own
Kinyarwanda:

| Metric (Kinyarwanda test) | Model alone | Through translation |
|---|---:|---:|
| chrF | 30.6 | 34.7 |
| ROUGE-L | 14.6 | 16.5 |
| Referral F1 | 56.2% | 71.0% |
| Danger-sign referral rate | 66.7% | 83.3% |

**But a native speaker found every answer read unusable**: *Nshobora konsa ndwaye?* ("Can I breastfeed
when I am sick?") was answered about feeding the child (*kugaburira*), not breastfeeding; the
mother-in-law question got the general rule and ignored the situation asked about; the groundnut
answer was meaningless ("ubishyira mu muriro kugeza ubwo hari umwijima"). Fluent but wrong Kinyarwanda
is more dangerous than broken Kinyarwanda, because a caregiver may trust it. The automatic metrics
rose while the answers stayed unusable: overlap metrics cannot tell whether advice is right, which is
why the final design relies on human review. Translation remains available for evaluation
(`NUTRIASSIST_KINYARWANDA=translate`, needs the `translate` extra) but is off in the app.

## How well matching works

`scripts/evaluate_pipeline.py --matching-only` (tables in `outputs/pipeline/`) asks two kinds of questions:

- **reworded**: the held-out paraphrases of val/test questions. Their original question is indexed,
  the paraphrase wording is not; the right answer is the original's reviewed answer;
- **new**: val/test questions against an index of training pairs only, where any match is a mistake.

Three ways of matching were compared on the 31 Kinyarwanda reworded questions (13 val, 18 test),
taking the best match with no threshold:

| Method | right answer (val + test) |
|---|---:|
| Character n-grams + food/illness/number check (**used**) | 17 of 31 (55%) |
| LaBSE multilingual embeddings (measured before the food check was added) | 4 of 31 (13%) |
| Translate to English (NLLB), then English embeddings (bge-small or MiniLM) | 4 of 31 (13%) |

Translating first loses too much: NLLB mistranslates short questions about local foods.

The scores of right and wrong matches overlap, so the threshold for answering directly is strict:
**0.75**, the lowest with at least 95% of returned answers right in both languages on val. At 0.75 no
Kinyarwanda question received a wrong reviewed answer. Most reworded questions fall below it, and that
is where the suggestions work:

| Kinyarwanda reworded questions (val + test, 31) | |
|---|---:|
| answered directly with the right reviewed answer | 0 (0%) |
| right reviewed answer among the three suggestions, or answered directly | **20 (65%)** |
| … if all 108 drafted extra wordings (batch 1) were approved | 21 (68%) |
| wrong reviewed answer shown directly | 0 |

## How to make Kinyarwanda better over time

Coverage grows with every reviewed wording and pair; quality stays at the level of the review.

1. **Review the drafted extra wordings.** `data/QA_data/curated/extra_wordings_rw.jsonl` holds wordings
   drafted by Claude (batch 1: breastfeeding and feeding by age, 108 wordings).
   `python -m nutriassist.qa_data.wording_review export` writes
   `data/QA_data/review/kinyarwanda_wordings_review.xlsx`; mark each wording `approved`, `corrected` or
   `rejected`, then `python -m nutriassist.qa_data.wording_review apply`. Approved wordings reach the
   app's matching (`data/QA_data/processed/extra_wordings.jsonl`); they are not used for training, so
   the reported training results do not change.
2. **Read `logs/unanswered.jsonl`** from time to time. Questions asked often with no reviewed answer
   become new extra wordings (when an existing answer fits) or new reviewed pairs.
3. **Retrain on a base model with more Kinyarwanda** when one becomes available at this size
   (experiments 7–8 in the notebook compare Gemma 3 and Gemma 2). Even then, its Kinyarwanda should
   pass the same native-speaker review before the app shows it.
