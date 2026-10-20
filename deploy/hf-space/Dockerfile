# Hugging Face Space build: clones the GitHub repository and runs the API + web app.
# Set the Space variable NUTRIASSIST_HF_REPO to the Hugging Face repo that holds the GGUF model.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends git build-essential cmake \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    NUTRIASSIST_API_URL=http://localhost:8000

ARG REPO_URL=https://github.com/pauline12ish34/NutriAssist_Capstone.git
ARG REPO_REF=main
RUN git clone --depth 1 --branch ${REPO_REF} ${REPO_URL} /home/user/app
WORKDIR /home/user/app
RUN pip install --user --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu ".[serve,app]" \
    && mkdir -p models

EXPOSE 7860
CMD ["bash", "scripts/start_container.sh"]
