"""Start the API and the web app together: python scripts/run_local.py

Opens the app at http://localhost:8501 (API docs at http://localhost:8000/docs).
Stop both with Ctrl+C. Uses models/nutriassist-rw-q4_k_m.gguf (or -q8_0.gguf) if present, else demo mode;
set NUTRIASSIST_MODEL_PATH to use another GGUF file.
"""

import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_PORT, APP_PORT = 8000, 8501


def wait_for_api(timeout_s: float = 120) -> bool:
    deadline = time.time() + timeout_s   # loading a large model can take a while
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://localhost:{API_PORT}/health", timeout=2):
                return True
        except OSError:
            time.sleep(1)
    return False


def main() -> int:
    env = {**os.environ, "NUTRIASSIST_API_URL": f"http://localhost:{API_PORT}"}
    api = subprocess.Popen([sys.executable, "-m", "uvicorn", "nutriassist.api.app:app", "--port", str(API_PORT)],
                           cwd=ROOT, env=env)
    print("Starting the API (loading the model)...")
    if not wait_for_api():
        api.terminate()
        print("The API did not start. See the messages above.")
        return 1
    app = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app/streamlit_app.py",
                            "--server.port", str(APP_PORT)], cwd=ROOT, env=env)
    print(f"\nNutriAssist-RW is running: http://localhost:{APP_PORT}  (API docs: http://localhost:{API_PORT}/docs)\n")
    try:
        app.wait()
    except KeyboardInterrupt:
        pass
    finally:
        for process in (app, api):
            process.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
