@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "DRY_RUN="
if /I "%~1"=="--dry-run" set "DRY_RUN=1"
if /I "%~1"=="--help" goto :help

set "BACKEND_DIR=%ROOT%\backend"
set "FRONTEND_DIR=%ROOT%\frontend"
set "BACKEND_CMD=cd /d \"%BACKEND_DIR%\" && call .venv\Scripts\activate.bat && set PYTHONPATH=. && uvicorn app.main:app --host 0.0.0.0 --port 8000"
set "FRONTEND_CMD=cd /d \"%FRONTEND_DIR%\" && npx next start -H 0.0.0.0 -p 3000"

if defined DRY_RUN (
  echo [DRY-RUN] offline backend window will start in %BACKEND_DIR%
  echo [DRY-RUN] offline frontend window will start in %FRONTEND_DIR%
  exit /b 0
)

start "AeroOne Backend Offline" cmd /k "%BACKEND_CMD%"
start "AeroOne Frontend Offline" cmd /k "%FRONTEND_CMD%"

echo [OK] Offline backend:  http://localhost:8000
echo [OK] Offline frontend: http://localhost:3000
exit /b 0

:help
echo Usage: start_offline.bat [--dry-run]
echo.
echo Starts the offline-installed backend and frontend in production mode.
exit /b 0
