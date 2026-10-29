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
| **Live app** | https://huggingface.co/spaces/pauline-ish/nutriAssist_Rw (free ZeroGPU Space; the first visit after 48 hours without visitors takes a few minutes to wake up) |
| **Walkthrough video** | [Watch the demo on YouTube](https://youtu.be/hVc_Zxnya3w) |
| **Technical report (PDF)** | _add link_ |
| **Training notebook** | [Open in Colab](https://colab.research.google.com/github/pauline12ish34/NutriAssist_Capstone/blob/main/notebooks/nutriassist_training.ipynb) |

> NutriAssist-RW gives general nutrition guidance. It does not diagnose illness or recommend medicines.
> In an emergency, go to the nearest health centre or call **912**.

---

## Features

| Feature | What it does | Where |
|---|---|---|
| Bilingual chat assistant | Answers in the language of the question with a small language model fine-tuned with QLoRA on 513 curated question-answer pairs: Gemma-3-4B online (GPU), Qwen2.5-1.5B locally (CPU). AI-written answers carry a warning | `src/nutriassist/assistant.py`, `notebooks/` |
| Reviewed Kinyarwanda answers | Kinyarwanda is shown only from answers approved by a native speaker: a matching question gets its reviewed answer word for word, otherwise the app offers up to three "Did you mean...?" reviewed questions. The fine-tuned model's own Kinyarwanda, and machine translation through English, were evaluated and judged unreliable ([why](docs/kinyarwanda.md)) | `src/nutriassist/knowledge.py`, `src/nutriassist/terms.py` |
| Safety layer | Rule-based detection of WHO/IMCI danger signs in English and Kinyarwanda answers urgent cases with a fixed referral before the model is called; blocks medicine doses; adds a referral when a medical answer lacks one; a fixed answer for honey (unsafe under 12 months) | `src/nutriassist/safety/` |
| Meal planner | 1–7 day plans for children aged 6–59 months from 33 local foods, meeting WHO energy targets and minimum dietary diversity, with portions in tablespoons | `src/nutriassist/planner/` |
| REST API | FastAPI with Swagger UI, input validation and clear errors | `src/nutriassist/api/` |
| Web app | Chat, Meal planner and How to use pages in English and Kinyarwanda, with a disclaimer before first use: Gradio online (`app/gradio_app.py`), Streamlit locally (`app/streamlit_app.py`); both share `app/texts.py` | `app/` |
| Data pipelines | Cleaning of the food composition workbook; building of the bilingual QA dataset with leak-free splits | `src/nutriassist/food_data/`, `src/nutriassist/qa_data/` |

## Screenshots

_Screenshots go in `docs/images/` (taken from the live app):_

| | |
|---|---|
| ![Disclaimer before first use](docs/images/disclaimer.png) | ![Chat in English with an AI answer](docs/images/chat_en.png) |
| ![Urgent danger-sign answer](docs/images/urgent.png) | ![Kinyarwanda reviewed answer](docs/images/chat_rw.png) |
| ![7-day meal plan](docs/images/meal_plan.png) | ![Swagger UI of the API](docs/images/swagger.png) |

## Architecture

The same pipeline runs in two deployments:

| | Online (live app) | Local, optionally in Docker |
|---|---|---|
| Interface | Gradio, assistant in the same process | Streamlit, talking to FastAPI over HTTP (Swagger at `/docs`) |
| Model | Gemma-3-4B + LoRA adapter, Transformers on a ZeroGPU GPU (borrowed only while it writes) | Qwen2.5-1.5B GGUF with llama.cpp on the CPU |

The local version, in detail:

```
                    ┌────────────────────────── FastAPI backend ───────────────────────────┐
 Browser ─► Streamlit ─HTTP─► /chat ─► language detection ─► danger-sign rules ─┬─ urgent ─► fixed referral message
 (app/)              │                                                          └─ other ──► matches a reviewed question? ─ yes ─► reviewed answer
                     │                                                                         │ no
                     │                                       Kinyarwanda: "no checked answer" + "Did you mean...?" reviewed questions
                     │                                       English:     LLM (llama.cpp, GGUF)
                     │                                                                         └► dose check, referral check
                     └──────► /meal-plan ─► targets by age (WHO/FAO) ─► greedy food selection ─► portions, coverage, tips
                                                                         (food table, 33 local foods)
```

**Design.** Every answer generator implements one interface, `ChatModel`
(`src/nutriassist/inference/base.py`): `TransformersChatModel` (GPU, training and evaluation),
`LlamaCppChatModel` (CPU, local app), `ZeroGPUChatModel` (borrows a GPU only while writing, online
app, `app/gradio_app.py`) and `ScriptedChatModel` (tests and demo mode). The
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

**Fine-tuned model vs. its base model** on the held-out test set (78 questions, English and Kinyarwanda),
from notebook section 6. Model: Qwen2.5-1.5B, experiment `exp3_lr_5e-4` (the model of the local app).

| Metric (test set) | Base model | Fine-tuned | Change |
|---|---|---|---|
| ROUGE-L | 9.2 | 27.5 | +200% |
| chrF | 24.4 | 34.5 | +42% |
| BLEU | 1.0 | 11.8 | ×12 |
| Perplexity (lower is better) | 53.8 | 9.9 | −82% |
| Referral F1 (medical questions sent to a health worker) | 37.5% | 63.3% | +69% |
| Referral recall | 28.1% | 59.4% | +111% |
| Language match (answer in the question's language) | 84.6% | 98.7% | +17% |

_Gemma-3-4B (`exp9`, the model of the live app): results to be added from the notebook._

The app adds rule-based safety on top of the model: urgent danger signs never reach the model, and
Kinyarwanda answers come only from native-speaker-reviewed pairs ([why](docs/kinyarwanda.md)).

**Safety referrals** (`python scripts/safety_report.py`): does the caregiver get sent to a health worker
when the reviewed reference answer says they should? Same 78 test questions, 12 of them with danger signs.

| | Danger questions referred | Referral recall | Precision | F1 |
|---|---|---|---|---|
| Base model | 2/12 | 28.1% | 56.2% | 37.5% |
| Fine-tuned model alone | 7/12 | 59.4% | 67.9% | 63.3% |
| **App: safety rules + fine-tuned model** | **8/12** | **62.5%** | **69.0%** | **65.6%** |

Recall is below the proposal's 90% target: many test questions describe complications of severe
malnutrition in general terms rather than a named danger sign, and the rules only fire on named signs.

**Performance** ([details](docs/performance.md)): a model answer takes a median of **4.6 s** on the live
ZeroGPU Space (Gemma-3-4B) and **8.1 s** on a 4-core laptop CPU (Qwen2.5-1.5B, 1.5 GB of RAM);
safety-rule answers take **3.5 ms** and a 7-day meal plan **7.5 ms** in the API.

## Repository structure

```
├── app/                         web interfaces
│   ├── gradio_app.py            online app (Hugging Face ZeroGPU Space)
│   ├── streamlit_app.py         local app: entry point, sidebar, navigation
│   ├── api_client.py            HTTP client for the backend
│   ├── texts.py                 English and Kinyarwanda interface text (shared)
│   ├── i18n.py                  language selection for the Streamlit app
│   └── views/                   chat, meal planner and how-to pages (Streamlit)
├── src/nutriassist/             Python package (installable)
│   ├── api/                     FastAPI app, request/response schemas, settings
│   ├── assistant.py             chat pipeline: language → safety rules → reviewed answers → model → output checks
│   ├── knowledge.py             matching questions to the reviewed answers, "Did you mean...?" suggestions
│   ├── terms.py                 bilingual foods, illnesses and health terms (matching check, translation)
│   ├── translation.py           NLLB-200 translation through English (evaluated, off in the app)
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
├── tests/                       281 tests (unit, integration, end-to-end)
├── docs/                        data, cleaning, dataset, Kinyarwanda, performance and deployment documentation
├── .github/workflows/           GitHub Actions: tests on Linux, Windows and macOS
├── deploy/hf-zerogpu/          Hugging Face ZeroGPU Space files (the online app)
├── deploy/hf-space/             Docker Space build files (needs a paid plan)
├── scripts/                     local launcher, benchmark, container start script
├── Dockerfile                   API + app in one container (optional)
└── pyproject.toml               package metadata and dependencies
```

## Technical requirements

| | Version used | Notes |
|---|---|---|
| Python | 3.12 (3.10+ supported) | |
| Online app | Gradio 6.31, Hugging Face `spaces` (ZeroGPU), PyTorch 2.13, Transformers 5.x, PEFT 0.21 | free Hugging Face account; ZeroGPU needs an account older than 30 days |
| Local app | Streamlit 1.66, FastAPI 0.150, Uvicorn | |
| Local inference | llama-cpp-python 0.3.36 | CPU only; about 2 GB of free RAM for the 4-bit model |
| Models | Gemma-3-4B-it (online), Qwen2.5-1.5B-Instruct (local), with LoRA adapters | adapter on [Hugging Face Hub](https://huggingface.co/pauline-ish/NutritionAssistant_RW) |
| Training | PyTorch 2.x, Transformers 5.x, PEFT 0.21, bitsandbytes | Google Colab GPU (T4 16 GB; A100 for Gemma-3-4B) |
| Evaluation | sacrebleu, rouge-score | |
| Optional | Docker 24+ | to run the local app in one container |

Tested on Windows 11, macOS and Linux (GitHub Actions), Google Colab, Docker and Hugging Face Spaces.

## Installation and running

**No installation:** use the [live app](https://huggingface.co/spaces/pauline-ish/nutriAssist_Rw).

**On your own computer:**

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

**With Docker (optional),** instead of the steps above:

```bash
docker build -t nutriassist .
docker run -p 7860:7860 -p 8000:8000 -v "${PWD}/models:/home/user/app/models" nutriassist
```

Then open http://localhost:7860.

Without the model file the app starts in **demo mode**: safety rules and the meal planner work; chat
answers are placeholders.

**Using the app.** Read the disclaimer and press *I understand, continue*. Choose English or Kinyarwanda in the sidebar. On *Ask a question*, type a question or
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
pytest                        # all 281 tests
pytest -m "not integration"   # fast unit tests only
python scripts/benchmark.py --model models/nutriassist-rw-q4_k_m.gguf --threads 1 2 4 8   # performance
```

GitHub Actions runs the tests on every push, on Linux, Windows and macOS (Python 3.12) and on Linux with
Python 3.10.

| Strategy | What is tested | Files |
|---|---|---|
| Unit | metrics, encoders, planner rules, safety rules, language detection, data cleaning | `test_evaluation.py`, `test_planner.py`, `test_safety.py`, … |
| Data validation | no train/test leakage; safety rules and language detector checked against every dataset question | `test_qa_dataset.py`, `test_safety.py`, `test_language.py` |
| Integration | real QLoRA training, adapter reload, generation and perplexity with a tiny Qwen2 model on CPU; HTTP API with validation and error cases | `test_integration_training.py`, `test_api.py` |
| End-to-end | Streamlit pages driven against a live API server: disclaimer, chat, urgent alert, language switch, 7-day plan; the Gradio app with a scripted model, and its model-loading path with a tiny model | `test_frontend.py`, `test_gradio_app.py` |
| Compatibility | the whole suite on three operating systems and two Python versions | `.github/workflows/tests.yml` |
| Performance | model speed by CPU thread count (low-end vs high-end), memory, API response times, live Space timings | `scripts/benchmark.py`, [`docs/performance.md`](docs/performance.md) |

Testing led to fixes: a model answer said honey is safe from 1 month, so honey questions now get a fixed
answer; "my child … won't drink" and "very sleepy" were not caught, so the danger-sign rules were widened.

## Deployment

Online, the app runs on a free Hugging Face **ZeroGPU** Space: a Gradio version of the app
(`app/gradio_app.py`) with the same safety rules, reviewed answers and meal planner, and the fine-tuned
model on a borrowed GPU (about 2–5 s per model answer). Hugging Face only gives free GPUs to Gradio apps,
and Docker Spaces now need a paid plan. Locally, the app runs as one Docker container (FastAPI + Streamlit,
model on the CPU with llama.cpp).
Step-by-step instructions for local, Docker and Spaces deployment are in **[docs/deployment.md](docs/deployment.md)**.

## Documentation

- [Data inspection](docs/data_inspection.md) and [nutrient cleaning](docs/nutrient_cleaning.md)
- [QA dataset design](docs/qa_dataset.md) and [dataset report](data/QA_data/processed/qa_report.md)
- [Why Kinyarwanda answers come from reviewed pairs](docs/kinyarwanda.md)
- [Performance and compatibility](docs/performance.md)
- [Deployment guide](docs/deployment.md)

## Author

Pauline Ishimwe — BSc Software Engineering capstone, African Leadership University. Supervisor: Junior Turatsinze.
