@echo off
rem ========================================================
rem Startup script for Cattle Disposal System
rem ========================================================

if not exist venv python -m venv venv

if exist venv\Scripts\activate.bat call venv\Scripts\activate.bat

python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

echo Starting web server on http://127.0.0.1:3000 ...
python app.py
pause
