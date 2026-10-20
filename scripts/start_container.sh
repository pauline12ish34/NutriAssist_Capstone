#!/usr/bin/env bash
# Container entry point: the API on port 8000 (internal), the web app on $PORT (default 7860).
set -euo pipefail

PORT="${PORT:-7860}"

uvicorn nutriassist.api.app:app --host 0.0.0.0 --port 8000 &
API_PID=$!

# Downloading and loading the model can take a few minutes on first start.
echo "Waiting for the API..."
for _ in $(seq 1 300); do
    if python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2)" 2>/dev/null; then
        break
    fi
    if ! kill -0 "$API_PID" 2>/dev/null; then
        echo "The API stopped during start-up." >&2
        exit 1
    fi
    sleep 2
done

exec streamlit run app/streamlit_app.py --server.port "$PORT" --server.address 0.0.0.0 --server.headless true
