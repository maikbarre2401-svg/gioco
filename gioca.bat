@echo off
REM Avvia il gioco 3D direttamente dal file .py (serve Python)
cd /d "%~dp0"
python -c "import panda3d, numpy" 2>nul || python -m pip install panda3d numpy
python rick_morty_3d.py
if errorlevel 1 pause
