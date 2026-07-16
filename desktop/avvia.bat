@echo off
rem ============================================
rem  Avvia Zeph sul desktop (Windows)
rem  Requisito: Node.js installato (nodejs.org)
rem ============================================
cd /d "%~dp0"

where node >nul 2>nul
if errorlevel 1 (
  echo.
  echo  Serve Node.js per avviare Zeph.
  echo  Scaricalo gratis da:  https://nodejs.org  ^(versione LTS^)
  echo  Poi riapri questo file.
  echo.
  pause
  exit /b 1
)

if not exist node_modules (
  echo Prima installazione: scarico i componenti, attendi un minuto...
  call npm install --no-audit --no-fund
)

echo Avvio Zeph... ^(icona vicino all'orologio per i comandi^)
call npx electron .
