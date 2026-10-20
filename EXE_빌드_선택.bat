@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo First run 실행_설치.bat to create the Python environment.
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m pip install pyinstaller
if errorlevel 1 (echo PyInstaller installation failed & pause & exit /b 1)
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name CHILI_LAB_Story_Image_Studio run_studio.py
if errorlevel 1 (echo Build failed & pause & exit /b 1)
echo Build completed: dist\CHILI_LAB_Story_Image_Studio.exe
pause
