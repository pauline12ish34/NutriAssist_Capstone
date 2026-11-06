@echo off
REM Start NutriAssist-RW locally (API + Streamlit app). Double-click or run: scripts\run_local.bat
REM App: http://localhost:8501   API docs: http://localhost:8000/docs   Stop with Ctrl+C.
setlocal
cd /d "%~dp0.."

if exist ".venv312\Scripts\python.exe" (
    set "PY=.venv312\Scripts\python.exe"
) else if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
) else (
    set "PY=python"
)

if not exist "models\nutriassist-rw-q4_k_m.gguf" if not exist "models\nutriassist-rw-q8_0.gguf" (
    echo No model in models\ - the app will run in demo mode. See README step 2 to download it.
)

echo Using %PY%
"%PY%" scripts\run_local.py
pause
