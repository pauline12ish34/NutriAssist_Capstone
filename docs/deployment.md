# Deployment guide

On your computer and in Docker (options 1 and 2), NutriAssist-RW has two parts that run together:

| Part | Technology | Port | What it does |
|---|---|---|---|
| Backend | FastAPI + llama.cpp | 8000 | `/chat` (safety rules + model), `/meal-plan`, `/foods`, `/health`; Swagger UI at `/docs` |
| Frontend | Streamlit | 8501 locally, 7860 in Docker | Chat, meal planner and how-to pages in English and Kinyarwanda |

The model is the fine-tuned Qwen2.5-1.5B, merged and exported as a GGUF file by section 8 of the training
notebook, in two sizes: `nutriassist-rw-q4_k_m.gguf` (about 1 GB, 4-bit, recommended for laptops) and
`nutriassist-rw-q8_0.gguf` (about 1.6 GB, 8-bit, highest quality). llama.cpp runs it on an ordinary CPU, so
no GPU is needed for deployment. When no path is configured the API uses the 4-bit file if it is in
`models/`, otherwise the 8-bit file. Without the file, the API starts in **demo mode**: the
safety rules and meal planner work, and chat answers are placeholders.

```
Browser ──► Streamlit app ──HTTP──► FastAPI ──► safety rules ──► llama.cpp (GGUF model)
                                        └──────► meal planner (food table)
```

---

## Option 1: run on your own computer

**Needs:** Python 3.10–3.12, Git, about 4 GB of free RAM for the model.

```bash
git clone https://github.com/pauline12ish34/NutriAssist_Capstone.git
cd NutriAssist_Capstone
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu -e ".[serve,app]"
```

The extra index gives a prebuilt llama.cpp, so no C++ compiler is needed.

**Get the model** (skip this to try the app in demo mode). Either:
- download `nutriassist-rw-q4_k_m.gguf` from Google Drive (`MyDrive/NutriAssist-RW/outputs/`) into the `models/`
  folder (notebook section 8.4 shows how; Git ignores this folder because the file is too large for GitHub), or
- if you published it to Hugging Face Hub (notebook section 8.3), set the repo name and the API downloads it on first start:
  `set NUTRIASSIST_HF_REPO=your-username/nutriassist-rw` (Windows) or `export NUTRIASSIST_HF_REPO=...` (macOS/Linux).

**Start everything with one command:**

```bash
python scripts/run_local.py
```

Open http://localhost:8501 for the app and http://localhost:8000/docs for the API documentation.
Stop with Ctrl+C.

To run the two parts separately (for example to watch the API logs):

```bash
uvicorn nutriassist.api.app:app --port 8000          # terminal 1
streamlit run app/streamlit_app.py                    # terminal 2
```

---

## Option 2: run with Docker

```bash
docker build -t nutriassist .
docker run -p 7860:7860 -v "$(pwd)/models:/home/user/app/models" nutriassist
```

On Windows PowerShell use `-v "${PWD}/models:/home/user/app/models"`. Open http://localhost:7860.
The `models` folder is mounted into the container so the model file is not copied into the image.

---

## Option 3: publish online on a Hugging Face ZeroGPU Space (free GPU)

Hugging Face now requires a paid plan (PRO) to create Docker or Streamlit Spaces. The free option is a
**Gradio Space on ZeroGPU**, which lends the app a large NVIDIA GPU (48 GB) only while the model writes an
answer. That is also much faster than the free CPU: about 2–5 seconds per model answer instead of 15–25,
and it can serve the 4B Gemma model, which would take about a minute per answer on a CPU.

So the online app is a Gradio version of the same app, `app/gradio_app.py`. It has the same three pages
(chat, meal planner, how to use) in English and Kinyarwanda, and runs the same code behind them: safety
rules, reviewed answers and meal planner. The differences from the Docker app:

| | Docker app (options 1–2) | ZeroGPU Space (option 3) |
|---|---|---|
| Interface | Streamlit, talking to FastAPI over HTTP (Swagger at `/docs`) | Gradio, assistant in the same process (ZeroGPU only lends GPUs to Gradio apps) |
| Model | GGUF file with llama.cpp on the CPU | base model + LoRA adapter with Transformers on the GPU |
| Model answer | 7–11 s on a laptop | about 2–5 s, plus a short wait when the GPU queue is busy |

```
Browser ──► Gradio app ──► safety rules / reviewed answers   (no GPU, under 0.2 s)
                 └───────► @spaces.GPU ──► Transformers model on a borrowed GPU
                 └───────► meal planner (food table)
```

Limits of the free tier: a free account can host 2 ZeroGPU Spaces (verified email, account older than 30
days). Each **visitor** gets a daily GPU allowance: 5 minutes when logged in to Hugging Face, 2 minutes
otherwise, which is dozens of model answers. Reviewed answers, safety messages and meal plans use no GPU.

### Step 1: publish the model to Hugging Face Hub (from Colab)

1. Create a free account at https://huggingface.co and a **write** token at *Settings → Access Tokens*.
2. In the training notebook, section 8.5, set `HF_REPO` and run the cell. Paste the token when asked. It
   uploads the adapter of the best experiment into the repo's `adapter/` folder.

### Step 2: create the Space

1. On Hugging Face: *New → Space*. Name: `nutriassist-rw`. SDK: **Gradio** (*Blank* template).
   Hardware: **ZeroGPU**. Visibility: Public.
2. In the Space, open *Files → Add file → Upload files* and upload the three files from this repository's
   `deploy/hf-zerogpu/` folder: `app.py`, `requirements.txt` and `README.md` (replace the existing README).
3. *Settings → Variables and secrets → New variable*, only if the defaults are not what you want:
   - `NUTRIASSIST_BASE_MODEL` (default `unsloth/gemma-3-4b-it`): the base model the adapter was trained on.
     For an experiment trained after continued pre-training, upload that merged model and put its repo here.
   - `NUTRIASSIST_ADAPTER_REPO` (default `pauline-ish/NutritionAssistant_RW`) and
     `NUTRIASSIST_ADAPTER_FOLDER` (default `adapter`): where the LoRA adapter is.
   - `NUTRIASSIST_MAX_NEW_TOKENS` (default `320`).

   If the model repo is private, also add a **secret** `HF_TOKEN` with a read token.

### Step 3: wait for the build, then test

The *Logs* tab shows the build (about 5–10 minutes the first time) and then the model download (about
8 GB for Gemma-3-4B). When the status turns **Running**, open the Space and check:

- a normal English question gets an answer from the model, and the line under it names the model;
- "Is it safe to give honey to my 4 month old baby?" gets the fixed honey message immediately;
- "My child is having a seizure" gets the urgent safety message immediately;
- a Kinyarwanda question gets a reviewed answer or "Did you mean...?" questions;
- the meal planner makes a 7-day plan, in both languages.

The public address is `https://huggingface.co/spaces/<your-username>/<space-name>` (this project: https://huggingface.co/spaces/pauline-ish/nutriAssist_Rw). Put it in the README.

### Updating the Space

`app.py` copies the GitHub repository each time the Space starts. After pushing new code to GitHub, open
the Space's *Settings* and click **Restart Space**. To switch the model, change the variables in step 2.3.

The free Space sleeps after 48 hours without visitors; the first visit after that takes a few minutes, so
open it before a demonstration.

### Paid alternative: the Docker Space

With a PRO account, the Docker app can run as it is: create a Space with SDK **Docker**, upload
`deploy/hf-space/Dockerfile` and `deploy/hf-space/README.md`, and set `NUTRIASSIST_HF_REPO` to a repo
holding the GGUF file. It runs on the CPU, so model answers take 15–25 seconds.

---

## Configuration

| Environment variable | Default | Meaning |
|---|---|---|
| `NUTRIASSIST_MODEL_PATH` | `models/nutriassist-rw-q4_k_m.gguf`, else `models/nutriassist-rw-q8_0.gguf` | GGUF model file |
| `NUTRIASSIST_HF_REPO` | none | Hugging Face repo to download the model from if the file is missing |
| `NUTRIASSIST_HF_FILE` | `nutriassist-rw-q4_k_m.gguf` | file name in that repo (set `nutriassist-rw-q8_0.gguf` for the larger model) |
| `NUTRIASSIST_BACKEND` | `auto` | `auto` (model if found, else demo), `llamacpp` (fail without a model), `demo` |
| `NUTRIASSIST_MAX_NEW_TOKENS` | `320` | longest answer, in tokens; lower is faster |
| `NUTRIASSIST_REPETITION_PENALTY` | `1.05` | discourages repeated phrases; set it to the value the notebook chose (section 5.3) |
| `NUTRIASSIST_THREADS` | all cores | CPU threads for llama.cpp |
| `NUTRIASSIST_API_URL` | `http://localhost:8000` | where the Streamlit app finds the API |
| `NUTRIASSIST_KNOWLEDGE` | `data/QA_data/processed/qa_master.jsonl` | reviewed answers returned for matching questions; `off` to turn off |
| `NUTRIASSIST_MATCH_THRESHOLD` | `0.75` | similarity needed to return a reviewed answer (chosen on the validation split) |
| `NUTRIASSIST_KINYARWANDA` | `reviewed` | how a Kinyarwanda question with no reviewed answer is handled. `reviewed`: a fixed "no checked answer" message with up to three "Did you mean...?" reviewed questions (the model never writes Kinyarwanda). `translate`: answered in English and machine-translated with NLLB-200 (needs the `translate` extra and a 2.4 GB download; judged not good enough by a native speaker). `model`: the model writes Kinyarwanda itself (unreliable) |
| `NUTRIASSIST_UNANSWERED_LOG` | `logs/unanswered.jsonl` | Kinyarwanda questions with no reviewed answer (question text, language and time only), so reviewers can write answers for the common ones; `off` to turn off |
| `NUTRIASSIST_EMBEDDINGS` | `off` | `on` adds LaBSE embeddings to matching (needs the `embeddings` extra; measured no better) |

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Sidebar says *Assistant is offline* | The API is not running or `NUTRIASSIST_API_URL` is wrong. Start it with `uvicorn nutriassist.api.app:app`. |
| Sidebar says *Demo mode* | No model file. Check `models/` or `NUTRIASSIST_HF_REPO`; the API log says which model it loaded. |
| `pip` tries to compile llama-cpp-python | Add `--extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu`, or install the C++ build tools. |
| Answers are slow | Normal on a CPU: a long answer takes 20–60 s on 2 cores. Lower `NUTRIASSIST_MAX_NEW_TOKENS`, or use a machine with more cores. |
| A Kinyarwanda question gets "no checked answer" | Expected when no reviewed question is close enough. Tap a suggestion, or add the question to the reviewed pairs (see `docs/kinyarwanda.md`, "How to make Kinyarwanda better over time"). The question is kept in `logs/unanswered.jsonl`. |
| Space build fails | Read the *Logs* tab; most failures are a typo in the variable names above. |
| Space sleeps | Free Spaces pause after 48 hours without visitors; the first visit wakes them (about a minute). |
