@echo off
setlocal
title Weltrade Trading Terminal - Launcher
color 0B

cd /d "%~dp0"

echo ============================================================================
echo    STARTING WELTRADE SYNTHETICS TRADING TERMINAL
echo ============================================================================
echo.

if not exist "%~dp0frontend\node_modules" (
    echo [INFO] Frontend dependencies not found. Running install.bat first...
    call "%~dp0install.bat"
)

echo [1/2] Starting FastAPI + MT5 Backend Server on http://127.0.0.1:8000 ...
start "Weltrade Backend (Port 8000)" cmd /k "cd /d "%~dp0backend" && python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload"

timeout /t 3 /nobreak >nul

echo [2/2] Starting React + Vite Frontend on http://localhost:5173 ...
start "Weltrade Frontend (Port 5173)" cmd /k "cd /d "%~dp0frontend" && npm.cmd run dev"

timeout /t 3 /nobreak >nul

echo Opening http://localhost:5173 in your browser...
start http://localhost:5173

echo.
echo Both servers are running in their own windows!
echo Close those windows when you want to stop the terminal.
timeout /t 4 >nul
