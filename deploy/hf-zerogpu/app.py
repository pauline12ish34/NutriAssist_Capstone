"""Hugging Face ZeroGPU Space entry point: fetches the NutriAssist-RW code from GitHub and starts the Gradio app.

The app itself is app/gradio_app.py in the GitHub repository, so pushing to GitHub and restarting the
Space (Settings > Restart Space) is enough to update it. Set NUTRIASSIST_REPO_REF to deploy another
branch or tag.
"""

import os
import subprocess
import sys
from pathlib import Path

import spaces  # noqa: F401  ZeroGPU needs this imported before anything initialises CUDA

REPO_URL = os.environ.get("NUTRIASSIST_REPO_URL", "https://github.com/pauline12ish34/NutriAssist_Capstone.git")
REPO_REF = os.environ.get("NUTRIASSIST_REPO_REF", "main")
CODE = Path(__file__).resolve().parent / "nutriassist_code"

if not CODE.exists():
    subprocess.run(["git", "clone", "--depth", "1", "--branch", REPO_REF, REPO_URL, str(CODE)], check=True)
sys.path[:0] = [str(CODE / "src"), str(CODE / "app")]
os.chdir(CODE)  # the reviewed answers and food tables are read from data/ relative to the repository

from gradio_app import build_demo  # noqa: E402

build_demo().launch()
