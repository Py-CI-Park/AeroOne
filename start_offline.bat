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
set "BACKEND_PORT=18437"
set "FRONTEND_PORT=29501"
set "BACKEND_URL=http://localhost:18437"
set "FRONTEND_URL=http://localhost:29501/"
set "BACKEND_TIMEOUT=20"
set "FRONTEND_TIMEOUT=60"

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
  echo cmd /k "title AeroOne Backend Offline ^&^& chcp 65001 ^>nul ^&^& color 0A ^&^& echo ================================================== ^&^& echo [BACKEND][BOOT ] AeroOne API Server ^&^& echo URL  : %BACKEND_URL% ^&^& echo MODE : OFFLINE ^&^& echo ROOT : %BACKEND_DIR% ^&^& echo CMD  : uvicorn app.main:app --host 0.0.0.0 --port %BACKEND_PORT% ^&^& echo ================================================== ^&^& echo. ^&^& cd /d ""%BACKEND_DIR%"" ^&^& call .venv\Scripts\activate.bat ^&^& set PYTHONPATH=. ^&^& uvicorn app.main:app --host 0.0.0.0 --port %BACKEND_PORT%"
  echo [DRY-RUN] offline frontend window command:
  echo cmd /k "title AeroOne Frontend Offline ^&^& chcp 65001 ^>nul ^&^& color 0B ^&^& echo ================================================== ^&^& echo [FRONTEND][BOOT] AeroOne Web UI ^&^& echo URL  : %FRONTEND_URL% ^&^& echo MODE : OFFLINE ^&^& echo ROOT : %FRONTEND_DIR% ^&^& echo CMD  : scripts\\start_frontend_offline.cmd ^&^& echo ================================================== ^&^& echo. ^&^& call \"%SCRIPTS_DIR%\\start_frontend_offline.cmd\""
  echo [DRY-RUN] browser readiness command:
  echo call "%SCRIPTS_DIR%\open_browser.cmd" "%FRONTEND_URL%" %BACKEND_PORT% %FRONTEND_PORT% %BACKEND_TIMEOUT% %FRONTEND_TIMEOUT%
  exit /b 0
)

call :ensure_port_free %BACKEND_PORT% offline backend
if errorlevel 1 exit /b 1
call :ensure_port_free %FRONTEND_PORT% offline frontend
if errorlevel 1 exit /b 1

start "AeroOne Backend Offline" cmd /k "title AeroOne Backend Offline && chcp 65001 >nul && color 0A && echo ================================================== && echo [BACKEND][BOOT ] AeroOne API Server && echo URL  : %BACKEND_URL% && echo MODE : OFFLINE && echo ROOT : %BACKEND_DIR% && echo CMD  : uvicorn app.main:app --host 0.0.0.0 --port %BACKEND_PORT% && echo ================================================== && echo [BACKEND][INFO ] Python virtualenv activating... && echo. && cd /d ""%BACKEND_DIR%"" && call .venv\Scripts\activate.bat && set PYTHONPATH=. && echo [BACKEND][READY] Launching uvicorn... && uvicorn app.main:app --host 0.0.0.0 --port %BACKEND_PORT%"
start "AeroOne Frontend Offline" cmd /k "title AeroOne Frontend Offline && chcp 65001 >nul && color 0B && echo ================================================== && echo [FRONTEND][BOOT] AeroOne Web UI && echo URL  : %FRONTEND_URL% && echo MODE : OFFLINE && echo ROOT : %FRONTEND_DIR% && echo CMD  : scripts\\start_frontend_offline.cmd && echo ================================================== && echo [FRONTEND][INFO] Starting Next.js production server... && echo. && call \"%SCRIPTS_DIR%\\start_frontend_offline.cmd\""

call "%SCRIPTS_DIR%\open_browser.cmd" "%FRONTEND_URL%" %BACKEND_PORT% %FRONTEND_PORT% %BACKEND_TIMEOUT% %FRONTEND_TIMEOUT%
if errorlevel 1 (
  echo [FAILED] browser open aborted because backend/frontend readiness was not reached.
  pause
  exit /b 1
)

echo ==================================================
echo [READY] Offline backend : http://localhost:18437
echo [READY] Offline frontend: http://localhost:29501
echo [INFO ] Browser auto-open is enabled.
echo [INFO ] Separate colorized windows opened for backend/frontend.
echo ==================================================
exit /b 0

:ensure_port_free
powershell -NoLogo -NoProfile -Command "$busy = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners() | Where-Object { $_.Port -eq %~1 }; if ($busy) { exit 1 } else { exit 0 }"
if errorlevel 1 (
  echo [ERROR] %~2 port %~1 is already in use.
  echo [INFO ] Release the port and rerun start_offline.bat.
  pause
  exit /b 1
)
exit /b 0

:help
echo Usage: start_offline.bat [--dry-run]
echo.
echo Starts the offline-installed backend and frontend in production mode.
exit /b 0
