@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "DRY_RUN="
set "OPEN_BROWSER="
set "LOCAL_ONLY="
set "ALLOW_HOST=%AEROONE_ALLOW_HOST%"

:parse_args
if "%~1"=="" goto :parse_done
if /I "%~1"=="--dry-run" (set "DRY_RUN=1" & shift & goto :parse_args)
if /I "%~1"=="--open-browser" (set "OPEN_BROWSER=1" & shift & goto :parse_args)
if /I "%~1"=="--local" (set "LOCAL_ONLY=1" & shift & goto :parse_args)
if /I "%~1"=="--help" goto :help
if /I "%~1"=="--allow-host" (shift & goto :capture_host)
echo %~1 | findstr /B /I /C:"--allow-host=" >nul
if not errorlevel 1 (
  for /F "tokens=2 delims==" %%V in ("%~1") do set "ALLOW_HOST=%%V"
  shift
  goto :parse_args
)
shift
goto :parse_args

:capture_host
if "%~1"=="" (
  echo [ERROR] --allow-host requires a host argument ^(IP or hostname^).
  exit /b 1
)
set "ALLOW_HOST=%~1"
shift
goto :parse_args

:parse_done

set "BACKEND_DIR=%ROOT%\backend"
set "FRONTEND_DIR=%ROOT%\frontend"
set "SCRIPTS_DIR=%ROOT%\scripts"
set "BACKEND_PORT=18437"
set "FRONTEND_PORT=29501"
REM 기본 동작 = LAN(IP). 옵션이 없으면 이 PC 의 LAN IPv4 를 자동 감지해 0.0.0.0 으로 띄운다.
REM 이 PC 에서만 쓰려면 --local, 특정 IP 는 --allow-host=<IP>. 감지 실패 시 loopback 폴백.
if not defined LOCAL_ONLY if not defined ALLOW_HOST set "ALLOW_HOST=auto"
if /I "%ALLOW_HOST%"=="auto" call :resolve_auto_host
if defined ALLOW_HOST (
  set "BACKEND_HOST=0.0.0.0"
  set "BACKEND_URL=http://%ALLOW_HOST%:18437"
  set "FRONTEND_URL=http://%ALLOW_HOST%:29501/"
) else (
  set "BACKEND_HOST=127.0.0.1"
  set "BACKEND_URL=http://localhost:18437"
  set "FRONTEND_URL=http://localhost:29501/"
)
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

if "%DRY_RUN%"=="1" goto :dry_run_emit
goto :real_run

:dry_run_emit
echo [DRY-RUN] offline backend window command:
echo cmd /k "title AeroOne Backend Offline ^&^& chcp 65001 ^>nul ^&^& color 0A ^&^& echo ================================================== ^&^& echo [BACKEND][BOOT ] AeroOne API Server ^&^& echo URL  : %BACKEND_URL% ^&^& echo MODE : OFFLINE ^&^& echo ROOT : %BACKEND_DIR% ^&^& echo CMD  : uvicorn app.main:app --host %BACKEND_HOST% --port %BACKEND_PORT% ^&^& echo ================================================== ^&^& echo. ^&^& cd /d ""%BACKEND_DIR%"" ^&^& call .venv\Scripts\activate.bat ^&^& set PYTHONPATH=. ^&^& uvicorn app.main:app --host %BACKEND_HOST% --port %BACKEND_PORT%"
echo [DRY-RUN] offline frontend window command:
echo cmd /k "title AeroOne Frontend Offline ^&^& chcp 65001 ^>nul ^&^& color 0B ^&^& echo ================================================== ^&^& echo [FRONTEND][BOOT] AeroOne Web UI ^&^& echo URL  : %FRONTEND_URL% ^&^& echo MODE : OFFLINE ^&^& echo ROOT : %FRONTEND_DIR% ^&^& echo CMD  : scripts\start_frontend_offline.cmd ^&^& echo ================================================== ^&^& echo. ^&^& cd /d ""%SCRIPTS_DIR%"" ^&^& call start_frontend_offline.cmd"
echo [DRY-RUN] browser readiness command:
echo call "%SCRIPTS_DIR%\open_browser.cmd" "%FRONTEND_URL%" %BACKEND_PORT% %FRONTEND_PORT% %BACKEND_TIMEOUT% %FRONTEND_TIMEOUT%
if not defined ALLOW_HOST goto :dry_loopback
echo [DRY-RUN] LAN host = %ALLOW_HOST% ^(backend / frontend bind 0.0.0.0^)
exit /b 0

:dry_loopback
echo [DRY-RUN] LAN host = ^(localhost only: --local or LAN IPv4 not detected^)
exit /b 0

:real_run

call :ensure_port_free %BACKEND_PORT% "offline backend"
if errorlevel 1 exit /b 1
call :ensure_port_free %FRONTEND_PORT% "offline frontend"
if errorlevel 1 exit /b 1

if defined ALLOW_HOST (
  set "AEROONE_ALLOW_HOST=%ALLOW_HOST%"
)

start "AeroOne Backend Offline" cmd /k "title AeroOne Backend Offline && chcp 65001 >nul && color 0A && echo ================================================== && echo [BACKEND][BOOT ] AeroOne API Server && echo URL  : %BACKEND_URL% && echo MODE : OFFLINE && echo ROOT : %BACKEND_DIR% && echo CMD  : uvicorn app.main:app --host %BACKEND_HOST% --port %BACKEND_PORT% && echo ================================================== && echo [BACKEND][INFO ] Python virtualenv activating... && echo. && cd /d ""%BACKEND_DIR%"" && call .venv\Scripts\activate.bat && set PYTHONPATH=. && echo [BACKEND][READY] Launching uvicorn... && uvicorn app.main:app --host %BACKEND_HOST% --port %BACKEND_PORT%"
start "AeroOne Frontend Offline" cmd /k "title AeroOne Frontend Offline && chcp 65001 >nul && color 0B && echo ================================================== && echo [FRONTEND][BOOT] AeroOne Web UI && echo URL  : %FRONTEND_URL% && echo MODE : OFFLINE && echo ROOT : %FRONTEND_DIR% && echo CMD  : scripts\start_frontend_offline.cmd && echo ================================================== && echo [FRONTEND][INFO] Starting Next.js production server... && echo. && cd /d ""%SCRIPTS_DIR%"" && call start_frontend_offline.cmd"

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
if not defined ALLOW_HOST echo [INFO ] Serving this PC only ^(localhost^). Omit --local to expose on the LAN.
if defined ALLOW_HOST echo [INFO ] LAN access: open http://%ALLOW_HOST%:29501/ . Other PCs may need scripts\allow_lan_firewall.cmd ^(Administrator^).
exit /b 0

:ensure_port_free
powershell -NoLogo -NoProfile -Command "$busy = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners() | Where-Object { $_.Port -eq %~1 }; if ($busy) { exit 1 } else { exit 0 }"
set "PORT_PROBE_EXIT=!errorlevel!"
if "!PORT_PROBE_EXIT!"=="1" (
  echo [ERROR] %~2 port %~1 is already in use.
  echo [INFO ] Release the port and rerun start_offline.bat.
  pause
  exit /b 1
)
if not "!PORT_PROBE_EXIT!"=="0" (
  echo [ERROR] Preflight port probe failed for %~2 port %~1.
  echo [INFO ] Verify that PowerShell is available and rerun start_offline.bat.
  pause
  exit /b 1
)
exit /b 0

:resolve_auto_host
echo [INFO ] Detecting this PC's LAN IPv4 for LAN access...
set "ALLOW_HOST="
for /f "usebackq delims=" %%I in (`powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\windows\detect_lan_ip.ps1"`) do set "ALLOW_HOST=%%I"
if not defined ALLOW_HOST (
  echo [WARN ] LAN IPv4 not detected. Serving this PC only ^(localhost^). Use --allow-host=^<IP^> to force.
  goto :eof
)
echo [INFO ] LAN IPv4 = !ALLOW_HOST! ^(serving on 0.0.0.0^)
goto :eof

:help
echo Usage: start_offline.bat [--dry-run] [--open-browser] [--local] [--allow-host=^<host^>]
echo.
echo Starts the offline-installed backend and frontend in production mode.
echo By default it serves on the LAN: this PC's LAN IPv4 is auto-detected and both
echo services bind 0.0.0.0 ^(reachable from other devices at http://^<IP^>:29501/^).
echo If no LAN IPv4 is found it falls back to localhost only.
echo.
echo --local             Serve on this PC only ^(127.0.0.1 / localhost^). No LAN exposure.
echo --allow-host=^<host^>  Force a specific LAN host/IP instead of auto-detection.
echo                     Example: --allow-host=192.168.1.10
echo --allow-host=auto   Explicitly auto-detect this PC's LAN IPv4 ^(same as default^).
echo                     Environment fallback: AEROONE_ALLOW_HOST.
exit /b 0
