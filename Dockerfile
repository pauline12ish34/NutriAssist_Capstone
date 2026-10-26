# NutriAssist-RW: API + web app in one container (CPU only).
#   docker build -t nutriassist .
#   docker run -p 7860:7860 -v ./models:/home/user/app/models nutriassist
# Then open http://localhost:7860. Without a model file the app runs in demo mode.
FROM python:3.12-slim

# Compilers are only used if no prebuilt llama-cpp-python wheel matches this platform.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake \
    && rm -rf /var/lib/apt/lists/*

# Hugging Face Spaces run containers as user 1000.
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    NUTRIASSIST_API_URL=http://localhost:8000
WORKDIR /home/user/app

COPY --chown=user pyproject.toml README.md ./
COPY --chown=user src ./src
RUN pip install --user --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu ".[serve,app]"

COPY --chown=user app ./app
COPY --chown=user .streamlit ./.streamlit
COPY --chown=user data/reference ./data/reference
COPY --chown=user data/processed/food_nutrients.csv ./data/processed/food_nutrients.csv
COPY --chown=user data/QA_data/processed/qa_master.jsonl data/QA_data/processed/extra_wordings.jsonl \
    ./data/QA_data/processed/
COPY --chown=user scripts/start_container.sh ./scripts/start_container.sh
RUN mkdir -p models

EXPOSE 7860
CMD ["bash", "scripts/start_container.sh"]
