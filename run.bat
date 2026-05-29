@echo off
REM Xianyu Auto Bot - Quick Start (Windows)

echo =========================================
echo    Xianyu Auto Bot - Quick Start
echo =========================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found
    echo Please install Python from https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Check virtual environment
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat

REM Install dependencies
echo.
echo Installing dependencies...
pip install -r requirements.txt

echo.
echo Starting Xianyu Auto Bot...
echo.
echo Web server will start at http://localhost:5000
echo.

REM Run the program
python main.py

pause
