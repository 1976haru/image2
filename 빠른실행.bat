@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [CHILI LAB] First run requires 실행_설치.bat
  pause
  exit /b 1
)
".venv\Scripts\python.exe" run_studio.py
if errorlevel 1 pause
