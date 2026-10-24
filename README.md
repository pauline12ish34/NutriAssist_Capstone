# NutriAssist-RW

**A bilingual (English / Kinyarwanda) nutrition assistant and meal planner for caregivers of children under 5 in Rwanda.**

Malnutrition remains a leading problem for young children in Rwanda, and caregivers often have no quick,
trustworthy source of feeding advice in their own language. NutriAssist-RW answers questions on
breastfeeding, feeding children from 6 months to 5 years, maternal nutrition and local foods, sends
caregivers to the health centre when a question describes a danger sign, and builds meal plans from
local foods sized for the child's age.

| | |
|---|---|
| **Repository** | https://github.com/pauline12ish34/NutriAssist_Capstone |
| **Live app** | _add the Hugging Face Space link after deployment_ |
| **Walkthrough video** | [Watch the demo on YouTube](https://youtu.be/hVc_Zxnya3w) |
| **Technical report (PDF)** | _add link_ |
| **Training notebook** | [Open in Colab](https://colab.research.google.com/github/pauline12ish34/NutriAssist_Capstone/blob/main/notebooks/nutriassist_training.ipynb) |

> NutriAssist-RW gives general nutrition guidance. It does not diagnose illness or recommend medicines.
> In an emergency, go to the nearest health centre or call **912**.

---

## Features

| Feature | What it does | Where |
|---|---|---|
| Bilingual chat assistant | Answers in the language of the question, from a Qwen2.5-1.5B model fine-tuned with QLoRA on 513 curated question-answer pairs | `src/nutriassist/assistant.py`, `notebooks/` |
| Safety layer | Rule-based detection of WHO/IMCI danger signs in English and Kinyarwanda answers urgent cases with a fixed referral before the model is called; blocks medicine doses; adds a referral when a medical answer lacks one | `src/nutriassist/safety/` |
| Meal planner | 1–7 day plans for children aged 6–59 months from 33 local foods, meeting WHO energy targets and minimum dietary diversity, with portions in tablespoons | `src/nutriassist/planner/` |
| REST API | FastAPI with Swagger UI, input validation and clear errors | `src/nutriassist/api/` |
| Web app | Streamlit app with Chat, Meal planner and How to use pages, switchable between English and Kinyarwanda | `app/` |
| Data pipelines | Cleaning of the food composition workbook; building of the bilingual QA dataset with leak-free splits | `src/nutriassist/food_data/`, `src/nutriassist/qa_data/` |

## Screenshots

_Add screenshots of the chat (English and Kinyarwanda), an urgent safety answer, a 7-day meal plan and the Swagger UI to `docs/images/` and link them here._

## Architecture

```
                    ┌────────────────────────── FastAPI backend ───────────────────────────┐
 Browser ─► Streamlit ─HTTP─► /chat ─► language detection ─► danger-sign rules ─┬─ urgent ─► fixed referral message
 (app/)              │                                                          └─ other ──► LLM (llama.cpp, GGUF)
                     │                                                                         └► dose check, referral check
                     └──────► /meal-plan ─► targets by age (WHO/FAO) ─► greedy food selection ─► portions, coverage, tips
                                                                         (food table, 33 local foods)
```

**Design.** Every answer generator implements one interface, `ChatModel`
(`src/nutriassist/inference/base.py`): `TransformersChatModel` (GPU, used for training and evaluation),
`LlamaCppChatModel` (CPU, used in deployment) and `ScriptedChatModel` (tests and demo mode). The
assistant, the evaluator and the API depend only on that interface, so models can be swapped without
touching them. Configuration lives in dataclasses (`TrainingConfig`, `Settings`), data in typed classes
(`QADataset`, `ChatExample`, `FoodCatalogue`, `MealPlan`), and each package has one responsibility.

**Algorithms and problem solving.**
- *Danger-sign detection:* compiled bilingual patterns with multi-part rules ("baby under 2 months" **and** "fever") and an English negation window ("not vomiting"). Linear in message length; no false urgent alarms on the 707 ordinary questions in the dataset.
- *Meal planning:* greedy slot filling that scores each food by the nutrients still needed, a bonus for a new WHO food group and a penalty for foods eaten in the previous two days; then energy calibration and rounding to household measures.
- *Language detection:* function-word and Kinyarwanda noun-class-prefix scoring; correct on all 1,327 dataset texts.
- *Training:* loss masked to answer tokens only; QLoRA (4-bit NF4 base model, LoRA on all linear layers); resumable experiment runner.
- *Food data cleaning:* the source workbook gives values per serving, not per 100 g, with unit errors and a shifted column in 300 rows; the pipeline detects and corrects them (`docs/nutrient_cleaning.md`).

## Results

_Fill in from `final_comparison.csv` and `experiment_table.csv` after training (notebook sections 5–6)._

| Metric (test set) | Base model | Fine-tuned | Change |
|---|---|---|---|
| ROUGE-L | | | |
| chrF | | | |
| BLEU | | | |
| Perplexity | | | |
| Referral F1 | | | |
| Language match | | | |

## Repository structure

```
├── app/                         Streamlit frontend
│   ├── streamlit_app.py         entry point, sidebar, navigation
│   ├── api_client.py            HTTP client for the backend
│   ├── i18n.py                  English and Kinyarwanda interface text
│   └── views/                   chat, meal planner and how-to pages
├── src/nutriassist/             Python package (installable)
│   ├── api/                     FastAPI app, request/response schemas, settings
│   ├── assistant.py             chat pipeline: language → safety rules → model → output checks
│   ├── safety/                  danger-sign rules, detector, referral detection, messages
│   ├── planner/                 nutrient targets, food catalogue, meal planner, tips
│   ├── inference/               ChatModel interface and GPU / CPU / scripted implementations
│   ├── training/                dataset, tokenisation, QLoRA fine-tuner, experiment runner
│   ├── evaluation/              BLEU, chrF, ROUGE-L, perplexity, classification metrics
│   ├── food_data/               food workbook cleaning pipeline
│   ├── qa_data/                 QA dataset builder and Kinyarwanda review sheet
│   ├── language.py              English / Kinyarwanda detector
│   └── prompts.py               system prompt shared by training and the app
├── notebooks/                   Colab training notebook
├── data/
│   ├── raw/                     original food workbook (read-only)
│   ├── processed/               cleaned food tables
│   ├── QA_data/                 QA sources, processed splits, review sheets
│   └── reference/               Kinyarwanda food names, planner foods
├── tests/                       176 tests (unit, integration, end-to-end)
├── docs/                        data, cleaning, dataset and deployment documentation
├── deploy/hf-space/             Hugging Face Space build files
├── scripts/                     local launcher, container start script
├── Dockerfile                   API + app in one container
└── pyproject.toml               package metadata and dependencies
```

## Technical requirements

| | Version used | Notes |
|---|---|---|
| Python | 3.12 (3.10+ supported) | |
| Web app | Streamlit 1.66, FastAPI 0.150, Uvicorn | |
| Inference | llama-cpp-python 0.3.36 | CPU only; any x86-64 or ARM machine with about 4 GB of free RAM |
| Training | PyTorch 2.x, Transformers 5.x, PEFT 0.21, bitsandbytes | Google Colab with a T4 GPU (16 GB) |
| Evaluation | sacrebleu, rouge-score | |
| Optional | Docker 24+ | for the container |

Tested on Windows 11 and Linux (Colab, Docker).

## Installation and running

```bash
git clone https://github.com/pauline12ish34/NutriAssist_Capstone.git
cd NutriAssist_Capstone
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu -e ".[serve,app,dev]"
```

Download the trained model `nutriassist-rw-q4_k_m.gguf` (about 1 GB) from Google Drive into `models/` (see [deployment guide](docs/deployment.md#option-1-run-on-your-own-computer)), then:

```bash
python scripts/run_local.py
```

- App: http://localhost:8501
- API documentation (Swagger UI): http://localhost:8000/docs

Without the model file the app starts in **demo mode**: safety rules and the meal planner work; chat
answers are placeholders.

**Using the app.** Choose English or Kinyarwanda in the sidebar. On *Ask a question*, type a question or
tap an example. On *Meal planner*, set the child's age, whether the child is breastfed, 1 or 7 days, and
optionally the foods you have or want to avoid, then press *Make my plan*. *How to use* explains the
features and their limits.

## Training the model

Open the [training notebook in Colab](https://colab.research.google.com/github/pauline12ish34/NutriAssist_Capstone/blob/main/notebooks/nutriassist_training.ipynb),
choose *Runtime → Change runtime type → T4 GPU*, then *Runtime → Run all*. It installs this package from
GitHub, explores the data, describes the model architecture, scores the base model, runs six
hyperparameter experiments (recording time and GPU memory), evaluates the best one on the test set,
compares answers qualitatively and exports the GGUF model. Outputs are saved to
`MyDrive/NutriAssist-RW/outputs/`. To rebuild the datasets:

```bash
python -m nutriassist.food_data.build_foods
python -m nutriassist.qa_data.build_qa_dataset
```

## Testing

```bash
pytest                    # all 176 tests
pytest -m "not integration"   # fast unit tests only
```

| Strategy | What is tested | Files |
|---|---|---|
| Unit | metrics, encoders, planner rules, safety rules, language detection, data cleaning | `test_evaluation.py`, `test_planner.py`, `test_safety.py`, … |
| Data validation | no train/test leakage; safety rules and language detector checked against every dataset question | `test_qa_dataset.py`, `test_safety.py`, `test_language.py` |
| Integration | real QLoRA training, adapter reload, generation and perplexity with a tiny Qwen2 model on CPU; HTTP API with validation and error cases | `test_integration_training.py`, `test_api.py` |
| End-to-end | Streamlit pages driven against a live API server: chat, urgent alert, language switch, 7-day plan | `test_frontend.py` |

## Deployment

The app is deployed as one Docker container (API + web app) on Hugging Face Spaces (free CPU tier).
The model is published to Hugging Face Hub from Colab and downloaded by the Space at start-up.
Step-by-step instructions for local, Docker and Spaces deployment are in **[docs/deployment.md](docs/deployment.md)**.

## Documentation

- [Data inspection](docs/data_inspection.md) and [nutrient cleaning](docs/nutrient_cleaning.md)
- [QA dataset design](docs/qa_dataset.md) and [dataset report](data/QA_data/processed/qa_report.md)
- [Deployment guide](docs/deployment.md)

## Author

Pauline Ishimwe — BSc Software Engineering capstone, African Leadership University. Supervisor: Junior Turatsinze.
