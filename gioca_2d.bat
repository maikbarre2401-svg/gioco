@echo off
REM Avvia il gioco 2D (platform) dal file .py (serve Python)
cd /d "%~dp0"
python -c "import pygame" 2>nul || python -m pip install pygame
python rick_and_morty.py
if errorlevel 1 pause
