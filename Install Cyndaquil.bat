@echo off
setlocal
cd /d "%~dp0"

echo.
echo ========================================
echo       Cyndaquil Requirements Setup
echo ========================================
echo.
echo Installing packages from requirements.txt...
echo.

py -3 -m pip install -r requirements.txt
if errorlevel 1 (
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ERROR: Requirements could not be installed.
        echo Make sure Python 3.11 or newer is installed and available on PATH.
        echo.
        pause
        exit /b 1
    )
)

echo.
echo Requirements are installed.
echo Launch Cyndaquil with Cyndaquil.pyw.
echo.
pause
