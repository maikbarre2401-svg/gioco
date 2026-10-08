@echo off
REM ==========================================================
REM  Crea RickAndMorty.exe sul tuo PC Windows
REM  (serve Python installato: https://www.python.org/downloads/
REM   durante l'installazione spunta "Add Python to PATH")
REM ==========================================================
cd /d "%~dp0"
echo Installo pygame, pyinstaller e pillow...
python -m pip install --upgrade pygame pyinstaller pillow
if errorlevel 1 goto errore

echo Creo l'icona...
python tools\make_icon.py

echo Creo l'eseguibile (ci vuole circa un minuto)...
python -m PyInstaller --noconfirm --onefile --windowed --name RickAndMorty --icon icon.ico rick_and_morty.py
if errorlevel 1 goto errore

echo.
echo ==========================================================
echo  FATTO!  Il gioco e' qui:  dist\RickAndMorty.exe
echo ==========================================================
start "" "dist"
pause
exit /b 0

:errore
echo.
echo Qualcosa e' andato storto. Controlla di avere Python installato.
pause
exit /b 1
