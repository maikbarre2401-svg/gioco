@echo off
echo Starting Aim Assist...
python aimbot_gui.py %*
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Application exited with errors.
    pause
)
