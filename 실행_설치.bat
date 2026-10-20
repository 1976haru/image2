@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 (
  echo Python Launcher not found. Install Python 3.11 or 3.12 from python.org and enable PATH.
  pause
  exit /b 1
)
if not exist .venv\Scripts\python.exe (
  py -3 -m venv .venv
  if errorlevel 1 (echo Python virtual environment failed & pause & exit /b 1)
)
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (echo Installing dependencies failed & pause & exit /b 1)
.venv\Scripts\python.exe run_studio.py
if errorlevel 1 pause
