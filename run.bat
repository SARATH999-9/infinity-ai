@echo off
title INFINITY AI
cd /d "%~dp0backend"
if not exist .venv (
  echo Creating virtual environment...
  python -m venv .venv
  if errorlevel 1 (
    echo Python was not found. Install Python 3.10 or newer from python.org and tick Add Python to PATH, then run this again.
    pause
    exit /b 1
  )
)
call .venv\Scripts\activate.bat
echo Installing packages, please wait...
python -m pip install -q -r requirements.txt
if errorlevel 1 (
  echo Package install failed. Check your internet connection and run this again.
  pause
  exit /b 1
)
if not exist .env (
  copy .env.example .env >nul
  echo.
  echo A settings file was created. Paste at least ONE AI key after GROQ_API_KEY= or GEMINI_API_KEY=
  echo Save with Ctrl+S, close Notepad, then come back here.
  notepad .env
)
echo.
python check_key.py
echo.
echo Starting INFINITY AI on http://localhost:8000   (press Ctrl+C to stop)
start "" cmd /c "timeout /t 4 >nul & start http://localhost:8000"
python -m uvicorn main:app --reload
pause
