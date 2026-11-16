@echo off
setlocal
title Weltrade Trading Terminal - Dependency Installer
color 0B

echo ============================================================================
echo    WELTRADE SYNTHETICS TRADING TERMINAL - FULL DEPENDENCY INSTALLER
echo ============================================================================
echo.

cd /d "%~dp0"

echo [1/4] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Python is not installed or not in your system PATH!
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    pause
    exit /b 1
)
python --version

echo.
echo [2/4] Checking Node.js / npm installation...
call npm.cmd --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Node.js / npm is not installed or not in your system PATH!
    echo Please install Node.js LTS from https://nodejs.org/
    pause
    exit /b 1
)
call npm.cmd --version

echo.
echo [3/4] Installing Backend Python dependencies (MT5, FastAPI, Uvicorn, Playwright)...
cd /d "%~dp0backend"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Failed to install Python dependencies!
    pause
    exit /b 1
)

echo.
echo [3b/4] Installing Playwright Chromium browser for Weltrade Safe Vault Bridge...
python -m playwright install chromium

echo.
echo [4/4] Installing Frontend Node.js dependencies (React, Lightweight Charts, Lucide, Vite)...
cd /d "%~dp0frontend"
call npm.cmd install
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Failed to install Frontend Node.js dependencies!
    pause
    exit /b 1
)

echo.
echo [4b/4] Verifying Frontend Production Build...
call npm.cmd run build
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Frontend build verification failed!
    pause
    exit /b 1
)

color 0A
echo.
echo ============================================================================
echo    INSTALLATION COMPLETE!
echo    Run "start.bat" anytime to launch the Weltrade Trading Terminal.
echo ============================================================================
echo.
pause
