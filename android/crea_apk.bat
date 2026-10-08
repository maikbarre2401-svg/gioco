@echo off
rem ============================================
rem  Crea Zeph.apk per Android (Windows)
rem  Requisito: Python 3 (python.org)
rem  Per metterci il tuo avatar: trascina il file .glb su questo .bat
rem ============================================
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  where python >nul 2>nul
  if errorlevel 1 (
    echo.
    echo  Serve Python per creare l'APK.
    echo  Scaricalo gratis da:  https://www.python.org/downloads/
    echo  ^(durante l'installazione spunta "Add python.exe to PATH"^)
    echo.
    pause
    exit /b 1
  )
  set PY=python
) else (
  set PY=py -3
)

if "%~1"=="" (
  %PY% crea_apk.py
) else (
  %PY% crea_apk.py --avatar "%~1"
)
echo.
pause
