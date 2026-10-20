@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist .venv\Scripts\python.exe (
  .venv\Scripts\python.exe -m pip install -r requirements-dev.txt
  .venv\Scripts\python.exe -m pytest -q
) else (
  py -3 -m pip install -r requirements-dev.txt
  py -3 -m pytest -q
)
pause
