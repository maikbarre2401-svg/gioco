@echo off
REM ==========================================================
REM  Crea gli eseguibili sul tuo PC Windows
REM  (serve Python installato: https://www.python.org/downloads/
REM   durante l'installazione spunta "Add Python to PATH")
REM ==========================================================
cd /d "%~dp0"
echo Installo le librerie...
python -m pip install --upgrade panda3d numpy pygame pyinstaller pillow
if errorlevel 1 goto errore

echo Creo l'icona...
python tools\make_icon.py

echo Creo RickAndMorty3D.exe (gioco 3D, ci vuole circa un minuto)...
python -m PyInstaller --noconfirm --onefile --windowed --name RickAndMorty3D --icon icon.ico --collect-binaries panda3d --hidden-import panda3d.core rick_morty_3d.py
if errorlevel 1 goto errore

echo Creo RickAndMorty2D.exe (gioco 2D)...
python -m PyInstaller --noconfirm --onefile --windowed --name RickAndMorty2D --icon icon.ico rick_and_morty.py
if errorlevel 1 goto errore

echo.
echo ==========================================================
echo  FATTO!  I giochi sono nella cartella dist:
echo     dist\RickAndMorty3D.exe   (open world 3D)
echo     dist\RickAndMorty2D.exe   (platform 2D)
echo ==========================================================
start "" "dist"
pause
exit /b 0

:errore
echo.
echo Qualcosa e' andato storto. Controlla di avere Python installato.
pause
exit /b 1
