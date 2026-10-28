@echo off
rem Launch HaizFlow from this source checkout using the project virtual environment.
rem Do not use the system "python" - it must be Python 3.13 from .venv.
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo [HaizFlow] Project environment is missing.
    echo Run: powershell -ExecutionPolicy Bypass -File scripts\install-desktop-env.ps1
    pause
    exit /b 1
)

set PYTHONUTF8=1
start "" ".venv\Scripts\pythonw.exe" "haizflow_desktop.py" %*
