@echo off
REM Always run relative to this file's folder, even if launched from elsewhere
cd /d "%~dp0"

echo =======================================
echo     Starting MT5 Trading Web App
echo =======================================
echo.

REM Free port 8000 if an old backend is still running (prevents "address already in use")
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
    echo Stopping old backend process %%p on port 8000...
    taskkill /PID %%p /F >nul 2>&1
)

echo [1/3] Starting Python Backend (FastAPI)...
REM No --reload: reloading restarts the MT5 session on every file save.
REM Bound to 127.0.0.1 only so nothing outside this PC can reach it.
set LIVE_TRADING_ENABLED=true
start "MT5 Backend Server" cmd /k "cd /d "%~dp0webapp\backend" && python -m uvicorn main:app --host 127.0.0.1 --port 8000"

echo [2/3] Starting Frontend (Vite React)...
start "MT5 Frontend Server" cmd /k "cd /d "%~dp0webapp\frontend" && npm.cmd run dev"

echo [3/3] Waiting for backend to be ready...
set /a tries=0
:waitloop
set /a tries+=1
curl.exe -s -o nul http://127.0.0.1:8000/docs && goto ready
if %tries% GEQ 20 goto timeout
timeout /t 1 /nobreak >nul
goto waitloop

:timeout
echo WARNING: Backend did not respond after 20 seconds. Check the "MT5 Backend Server" window.
goto openbrowser

:ready
echo Backend is up.

:openbrowser
echo Opening browser to http://localhost:5173
start http://localhost:5173

echo.
echo All systems go! Keep the two terminal windows open to keep the servers running.
echo To stop the system, just close the terminal windows.
pause
