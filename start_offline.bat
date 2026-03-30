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
  echo [DRY-RUN] offline backend window command:
  echo cmd /k "title AeroOne Backend Offline ^&^& chcp 65001 ^>nul ^&^& color 0A ^&^& echo ================================================== ^&^& echo [BACKEND][BOOT ] AeroOne API Server ^&^& echo URL  : http://localhost:18437 ^&^& echo MODE : OFFLINE ^&^& echo ROOT : %BACKEND_DIR% ^&^& echo ================================================== ^&^& echo. ^&^& cd /d ""%BACKEND_DIR%"" ^&^& call .venv\Scripts\activate.bat ^&^& set PYTHONPATH=. ^&^& uvicorn app.main:app --host 0.0.0.0 --port 18437"
  echo [DRY-RUN] offline frontend window command:
  echo cmd /k "title AeroOne Frontend Offline ^&^& chcp 65001 ^>nul ^&^& color 0B ^&^& echo ================================================== ^&^& echo [FRONTEND][BOOT] AeroOne Web UI ^&^& echo URL  : http://localhost:29501 ^&^& echo MODE : OFFLINE ^&^& echo ROOT : %FRONTEND_DIR% ^&^& echo ================================================== ^&^& echo. ^&^& cd /d ""%FRONTEND_DIR%"" ^&^& npx next start -H 0.0.0.0 -p 29501"
  exit /b 0
)

start "AeroOne Backend Offline" cmd /k "title AeroOne Backend Offline && chcp 65001 >nul && color 0A && echo ================================================== && echo [BACKEND][BOOT ] AeroOne API Server && echo URL  : http://localhost:18437 && echo MODE : OFFLINE && echo ROOT : %BACKEND_DIR% && echo ================================================== && echo [BACKEND][INFO ] Python virtualenv activating... && echo. && cd /d ""%BACKEND_DIR%"" && call .venv\Scripts\activate.bat && set PYTHONPATH=. && echo [BACKEND][READY] Launching uvicorn... && uvicorn app.main:app --host 0.0.0.0 --port 18437"
start "AeroOne Frontend Offline" cmd /k "title AeroOne Frontend Offline && chcp 65001 >nul && color 0B && echo ================================================== && echo [FRONTEND][BOOT] AeroOne Web UI && echo URL  : http://localhost:29501 && echo MODE : OFFLINE && echo ROOT : %FRONTEND_DIR% && echo ================================================== && echo [FRONTEND][INFO] Starting Next.js production server... && echo. && cd /d ""%FRONTEND_DIR%"" && npx next start -H 0.0.0.0 -p 29501"

if errorlevel 1 (
  echo [FAILED] start_offline.bat could not launch backend/frontend windows.
  pause
  exit /b 1
)

echo ==================================================
echo [READY] Offline backend : http://localhost:18437
echo [READY] Offline frontend: http://localhost:29501
echo [INFO ] Separate colorized windows opened for backend/frontend.
echo ==================================================
exit /b 0

:help
echo Usage: start_offline.bat [--dry-run]
echo.
echo Starts the offline-installed backend and frontend in production mode.
exit /b 0
