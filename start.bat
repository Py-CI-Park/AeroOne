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
set "FRONTEND_CMD=cd /d \"%FRONTEND_DIR%\" && npm run dev"

if defined DRY_RUN (
  echo [DRY-RUN] backend window will start in %BACKEND_DIR%
  echo [DRY-RUN] frontend window will start in %FRONTEND_DIR%
  exit /b 0
)

start "AeroOne Backend" cmd /k "%BACKEND_CMD%"
start "AeroOne Frontend" cmd /k "%FRONTEND_CMD%"

echo [OK] Backend:  http://localhost:8000
echo [OK] Frontend: http://localhost:3000
exit /b 0

:help
echo Usage: start.bat [--dry-run]
echo.
echo Starts backend and frontend for an online/local Windows PC.
exit /b 0
