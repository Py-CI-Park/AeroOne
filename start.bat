@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "DRY_RUN="
set "OPEN_BROWSER="
if /I "%~1"=="--dry-run" set "DRY_RUN=1"
if /I "%~1"=="--open-browser" set "OPEN_BROWSER=1"
if /I "%~1"=="--help" goto :help
if /I "%~2"=="--open-browser" set "OPEN_BROWSER=1"
if /I "%~2"=="--dry-run" set "DRY_RUN=1"

set "BACKEND_DIR=%ROOT%\backend"
set "FRONTEND_DIR=%ROOT%\frontend"
set "SCRIPTS_DIR=%ROOT%\scripts"

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
  echo cmd /k "title AeroOne Backend ^&^& chcp 65001 ^>nul ^&^& color 0A ^&^& echo ================================================== ^&^& echo [BACKEND][BOOT ] AeroOne API Server ^&^& echo URL  : http://localhost:18437 ^&^& echo ROOT : %BACKEND_DIR% ^&^& echo CMD  : uvicorn app.main:app --host 0.0.0.0 --port 18437 ^&^& echo ================================================== ^&^& echo. ^&^& cd /d ""%BACKEND_DIR%"" ^&^& call .venv\Scripts\activate.bat ^&^& set PYTHONPATH=. ^&^& uvicorn app.main:app --host 0.0.0.0 --port 18437"
  echo [DRY-RUN] frontend window command:
  echo cmd /k "title AeroOne Frontend ^&^& chcp 65001 ^>nul ^&^& color 0B ^&^& echo ================================================== ^&^& echo [FRONTEND][BOOT] AeroOne Web UI ^&^& echo URL  : http://localhost:29501 ^&^& echo ROOT : %FRONTEND_DIR% ^&^& echo CMD  : scripts\\start_frontend_dev.cmd ^&^& echo ================================================== ^&^& echo. ^&^& call \"%SCRIPTS_DIR%\\start_frontend_dev.cmd\""
  echo [DRY-RUN] browser open command:
  echo cmd /c call "%SCRIPTS_DIR%\\open_browser.cmd" "http://localhost:29501/"
  exit /b 0
)

start "AeroOne Backend" cmd /k "title AeroOne Backend && chcp 65001 >nul && color 0A && echo ================================================== && echo [BACKEND][BOOT ] AeroOne API Server && echo URL  : http://localhost:18437 && echo ROOT : %BACKEND_DIR% && echo CMD  : uvicorn app.main:app --host 0.0.0.0 --port 18437 && echo ================================================== && echo [BACKEND][INFO ] Python virtualenv activating... && echo. && cd /d ""%BACKEND_DIR%"" && call .venv\Scripts\activate.bat && set PYTHONPATH=. && echo [BACKEND][READY] Launching uvicorn... && uvicorn app.main:app --host 0.0.0.0 --port 18437"
start "AeroOne Frontend" cmd /k "title AeroOne Frontend && chcp 65001 >nul && color 0B && echo ================================================== && echo [FRONTEND][BOOT] AeroOne Web UI && echo URL  : http://localhost:29501 && echo ROOT : %FRONTEND_DIR% && echo CMD  : scripts\\start_frontend_dev.cmd && echo ================================================== && echo [FRONTEND][INFO] Starting Next.js development server... && echo. && call \"%SCRIPTS_DIR%\\start_frontend_dev.cmd\""
start "AeroOne Browser" cmd /c call "%SCRIPTS_DIR%\open_browser.cmd" "http://localhost:29501/"

if errorlevel 1 (
  echo [FAILED] start.bat could not launch backend/frontend windows.
  pause
  exit /b 1
)

echo ==================================================
echo [READY] Backend : http://localhost:18437
echo [READY] Frontend: http://localhost:29501
echo [INFO ] Browser auto-open is enabled.
echo [INFO ] Separate colorized windows opened for backend/frontend.
echo ==================================================
exit /b 0

:help
echo Usage: start.bat [--dry-run]
echo.
echo Starts backend and frontend for an online/local Windows PC.
exit /b 0
