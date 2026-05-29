@echo off
REM Xianyu Auto Bot Build Script (Windows)

echo =========================================
echo    Xianyu Auto Bot - Build Script
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

REM Check PyInstaller
echo.
echo Checking PyInstaller...
pyinstaller --version >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

REM Install dependencies
echo.
echo Installing dependencies...
pip install -r requirements.txt

echo.
echo Starting build...
echo.

REM Build with spec file
pyinstaller --clean --noconfirm build.spec

echo.
echo Build complete!
echo Executable location: dist\
echo.
echo =========================================
pause
