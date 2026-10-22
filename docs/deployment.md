# Deployment guide

NutriAssist-RW has two parts that run together:

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

## Option 3: publish online on Hugging Face Spaces (free)

A free Space has 2 CPU cores and 16 GB of RAM, enough for the model. The Space builds from the GitHub
repository, and the model is downloaded from Hugging Face Hub when the Space starts, so the large file is
never uploaded from your computer.

### Step 1: publish the model to Hugging Face Hub (from Colab)

1. Create a free account at https://huggingface.co and a **write** token at *Settings → Access Tokens*.
2. In the training notebook, section 8.3, set `HF_REPO = "your-username/nutriassist-rw"` and run the
   cell. Paste the token when asked. The adapter and the GGUF file are uploaded from Google's network,
   which is much faster than uploading from your own connection.

### Step 2: create the Space

1. On Hugging Face: *New → Space*. Name: `nutriassist-rw`. SDK: **Docker** (*Blank* template).
   Hardware: **CPU basic (free)**. Visibility: Public.
2. In the Space, open *Files → Add file → Upload files* and upload the two files from this repository's
   `deploy/hf-space/` folder: `Dockerfile` and `README.md` (replace the existing README).
3. *Settings → Variables and secrets → New variable*:
   - `NUTRIASSIST_HF_REPO` = `your-username/nutriassist-rw`
   - optional: `NUTRIASSIST_MAX_NEW_TOKENS` = `256` (shorter answers come back faster on the free CPU)
   If the model repo is private, also add a **secret** `HF_TOKEN` with a read token.

### Step 3: wait for the build, then test

The *Logs* tab shows the build (about 5–15 minutes the first time) and then the model download. When
the status turns **Running**, open the Space. Check:

- the sidebar says *Assistant is online* and **not** *Demo mode*;
- a normal question gets an answer;
- "My child is having a seizure" gets the urgent safety message immediately;
- the meal planner makes a 7-day plan.

The public address is `https://huggingface.co/spaces/your-username/nutriassist-rw`. Put it in the README.

### Updating the Space

The Space copies the GitHub repository when it is built. After pushing new code to GitHub, open the
Space's *Settings* and click **Factory rebuild**.

---

## Configuration

| Environment variable | Default | Meaning |
|---|---|---|
| `NUTRIASSIST_MODEL_PATH` | `models/nutriassist-rw-q4_k_m.gguf`, else `models/nutriassist-rw-q8_0.gguf` | GGUF model file |
| `NUTRIASSIST_HF_REPO` | none | Hugging Face repo to download the model from if the file is missing |
| `NUTRIASSIST_HF_FILE` | `nutriassist-rw-q4_k_m.gguf` | file name in that repo (set `nutriassist-rw-q8_0.gguf` for the larger model) |
| `NUTRIASSIST_BACKEND` | `auto` | `auto` (model if found, else demo), `llamacpp` (fail without a model), `demo` |
| `NUTRIASSIST_MAX_NEW_TOKENS` | `320` | longest answer, in tokens; lower is faster |
| `NUTRIASSIST_THREADS` | all cores | CPU threads for llama.cpp |
| `NUTRIASSIST_API_URL` | `http://localhost:8000` | where the Streamlit app finds the API |

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Sidebar says *Assistant is offline* | The API is not running or `NUTRIASSIST_API_URL` is wrong. Start it with `uvicorn nutriassist.api.app:app`. |
| Sidebar says *Demo mode* | No model file. Check `models/` or `NUTRIASSIST_HF_REPO`; the API log says which model it loaded. |
| `pip` tries to compile llama-cpp-python | Add `--extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu`, or install the C++ build tools. |
| Answers are slow | Normal on a CPU: a long answer takes 20–60 s on 2 cores. Lower `NUTRIASSIST_MAX_NEW_TOKENS`, or use a machine with more cores. |
| Space build fails | Read the *Logs* tab; most failures are a typo in the variable names above. |
| Space sleeps | Free Spaces pause after 48 hours without visitors; the first visit wakes them (about a minute). |
