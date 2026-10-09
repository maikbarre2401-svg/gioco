@echo off
rem Crea MaikSubs.apk e lo installa sul telefono collegato via USB (debug USB attivo)
cd /d "%~dp0"
call crea_apk.bat --installa
