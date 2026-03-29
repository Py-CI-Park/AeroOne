@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "DRY_RUN="
if /I "%~1"=="--dry-run" set "DRY_RUN=1"
if /I "%~1"=="--help" goto :help

set "BACKEND_DIR=%ROOT%\backend"
set "FRONTEND_DIR=%ROOT%\frontend"

if not exist "%BACKEND_DIR%" (
  echo [ERROR] backend directory not found: %BACKEND_DIR%
  exit /b 1
)

if not exist "%FRONTEND_DIR%" (
  echo [ERROR] frontend directory not found: %FRONTEND_DIR%
  exit /b 1
)

if defined DRY_RUN (
  echo [DRY-RUN] backend window command:
  echo cmd /k "cd /d ""%BACKEND_DIR%"" ^&^& call .venv\Scripts\activate.bat ^&^& set PYTHONPATH=. ^&^& uvicorn app.main:app --host 0.0.0.0 --port 18437"
  echo [DRY-RUN] frontend window command:
  echo cmd /k "cd /d ""%FRONTEND_DIR%"" ^&^& npm run dev"
  exit /b 0
)

start "AeroOne Backend" cmd /k "cd /d ""%BACKEND_DIR%"" && call .venv\Scripts\activate.bat && set PYTHONPATH=. && uvicorn app.main:app --host 0.0.0.0 --port 18437"
start "AeroOne Frontend" cmd /k "cd /d ""%FRONTEND_DIR%"" && npm run dev"

if errorlevel 1 (
  echo [FAILED] start.bat could not launch backend/frontend windows.
  pause
  exit /b 1
)

echo [OK] Backend:  http://localhost:18437
echo [OK] Frontend: http://localhost:29501
exit /b 0

:help
echo Usage: start.bat [--dry-run]
echo.
echo Starts backend and frontend for an online/local Windows PC.
exit /b 0
