@echo off
echo ========================================
echo   Aim Assist - Installer
echo ========================================
echo.

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python not found in PATH. Install Python 3.11 first.
    pause
    exit /b 1
)

python --version 2>&1 | findstr /R "3\.11\." >nul
if %ERRORLEVEL% neq 0 (
    echo [WARN] Python 3.11 recommended. Detected:
    python --version
    echo.
)

echo Installing dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if %ERRORLEVEL% neq 0 (
    echo [ERROR] pip install failed.
    pause
    exit /b 1
)

echo.
echo Creating directories...
if not exist profiles mkdir profiles
if not exist logs mkdir logs

echo.
echo ========================================
echo   Installation complete!
echo   Run: run.bat
echo ========================================
pause
