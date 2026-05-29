@echo off
chcp 65001 >nul
echo =========================================
echo    Xianyu Auto Reply Bot
echo =========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found, please install Python first
    pause
    exit /b 1
)

echo [OK] Python installed

REM Check virtual environment
if not exist "venv" (
    echo.
    echo [INFO] Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install dependencies
echo.
echo [INFO] Checking dependencies...
pip install websockets flask flask-cors requests aiohttp openai pydantic python-dotenv -q

REM Check activation status
echo.
echo [INFO] Checking activation status...
python -c "from activation import is_activated; exit(0 if is_activated() else 1)"
if errorlevel 1 (
    echo [INFO] Not activated
    python activation.py
    if errorlevel 1 (
        pause
        exit /b 1
    )
    echo [OK] Activation successful
) else (
    echo [OK] Already activated
)

REM Check .env file
if not exist ".env" (
    echo.
    echo [INFO] Creating config file...
    copy .env.example .env >nul
    echo.
    echo [WARN] Please configure parameters in Web interface!
)

echo.
echo [INFO] Starting service...
echo.
echo [INFO] Web interface: http://localhost:8080
echo [INFO] Tip: Configure Cookie and API Key in Web interface first time
echo.
echo Press Ctrl+C to stop
echo =========================================
echo.

python main.py
pause
