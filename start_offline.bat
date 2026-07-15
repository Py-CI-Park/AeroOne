@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0"
set "ENTRY_BATCH=%~f0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "DRY_RUN="
set "OPEN_BROWSER="
set "LOCAL_ONLY="
set "MAINTENANCE_PREFLIGHT="
set "ALLOW_HOST=%AEROONE_ALLOW_HOST%"
REM 비대화형(run_all 등)에서 pause 가 흐름을 막지 않도록 --no-pause / AEROONE_NO_PAUSE 지원.
set "NO_PAUSE=%AEROONE_NO_PAUSE%"

:parse_args
if "%~1"=="" goto :parse_done
if /I "%~1"=="--dry-run" (set "DRY_RUN=1" & shift & goto :parse_args)
if /I "%~1"=="--open-browser" (set "OPEN_BROWSER=1" & shift & goto :parse_args)
if /I "%~1"=="--local" (set "LOCAL_ONLY=1" & shift & goto :parse_args)
if /I "%~1"=="--no-pause" (set "NO_PAUSE=1" & shift & goto :parse_args)
if /I "%~1"=="--maintenance-preflight" (set "MAINTENANCE_PREFLIGHT=1" & shift & goto :parse_args)
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

if defined MAINTENANCE_PREFLIGHT goto :maintenance_preflight
powershell -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%ROOT%\scripts\windows\invoke_with_maintenance_gate.ps1" -WorkspaceRoot "%ROOT%" -BatchPath "%ENTRY_BATCH%" -RawBatchArguments "--maintenance-preflight"
set "GATE_EXIT=%ERRORLEVEL%"
if "%GATE_EXIT%"=="0" goto :maintenance_preflight_complete
if "%GATE_EXIT%"=="97" goto :gate_unavailable_fallback
goto :gate_preflight_failed

:gate_unavailable_fallback
echo [WARN ] Maintenance gate unavailable on this host - locked-down environment ^(no global-object privilege^) or a reparse-point in the install path.
echo [WARN ] Continuing with a direct startup preflight ^(safe: TCP port check + idempotent DB migration only; matches pre-gate behavior^).
call :run_startup_preflight
if errorlevel 1 exit /b 1
goto :maintenance_preflight_complete

:gate_preflight_failed
echo [ERROR] Startup maintenance preflight did not pass ^(exit %GATE_EXIT%^).
if "%GATE_EXIT%"=="98" echo [INFO ] Another AeroOne maintenance operation ^(e.g. credential rotation^) is holding the gate. Let it finish, then rerun start_offline.bat.
echo [INFO ] Resolve the reported cause above and rerun start_offline.bat.
if not defined NO_PAUSE pause
exit /b 1

:maintenance_preflight
if /I not "%AEROONE_MAINTENANCE_GATE_HELD%"=="1" (
  echo [ERROR] Internal maintenance preflight must run under the workspace gate.
  exit /b 1
)
call :run_startup_preflight
exit /b !errorlevel!

:run_startup_preflight
call :ensure_port_free %BACKEND_PORT% "offline backend"
if errorlevel 1 exit /b 1
call :ensure_port_free %FRONTEND_PORT% "offline frontend"
if errorlevel 1 exit /b 1
call :ensure_db_migrated
exit /b !errorlevel!

:maintenance_preflight_complete

echo [PRE  ] Provider credential store root validation ^(SID-scoped, ProgramData^)
call :validate_provider_credential_root
if errorlevel 1 exit /b 1
echo [OK   ] Provider credential store root verified for this runtime identity
if defined ALLOW_HOST (
  set "AEROONE_ALLOW_HOST=%ALLOW_HOST%"
)

start "AeroOne Backend Offline" cmd /k "title AeroOne Backend Offline && chcp 65001 >nul && color 0A && echo ================================================== && echo [BACKEND][BOOT ] AeroOne API Server && echo URL  : %BACKEND_URL% && echo MODE : OFFLINE && echo ROOT : %BACKEND_DIR% && echo CMD  : uvicorn app.main:app --host %BACKEND_HOST% --port %BACKEND_PORT% && echo ================================================== && echo [BACKEND][INFO ] Python virtualenv activating... && echo. && cd /d ""%BACKEND_DIR%"" && call .venv\Scripts\activate.bat && set PYTHONPATH=. && echo [BACKEND][READY] Launching uvicorn... && uvicorn app.main:app --host %BACKEND_HOST% --port %BACKEND_PORT%"
start "AeroOne Frontend Offline" cmd /k "title AeroOne Frontend Offline && chcp 65001 >nul && color 0B && echo ================================================== && echo [FRONTEND][BOOT] AeroOne Web UI && echo URL  : %FRONTEND_URL% && echo MODE : OFFLINE && echo ROOT : %FRONTEND_DIR% && echo CMD  : scripts\start_frontend_offline.cmd && echo ================================================== && echo [FRONTEND][INFO] Starting Next.js production server... && echo. && cd /d ""%SCRIPTS_DIR%"" && call start_frontend_offline.cmd"

call "%SCRIPTS_DIR%\open_browser.cmd" "%FRONTEND_URL%" %BACKEND_PORT% %FRONTEND_PORT% %BACKEND_TIMEOUT% %FRONTEND_TIMEOUT%
if errorlevel 1 (
  echo [FAILED] browser open aborted because backend/frontend readiness was not reached.
  if not defined NO_PAUSE pause
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
  if not defined NO_PAUSE pause
  exit /b 1
)
if not "!PORT_PROBE_EXIT!"=="0" (
  echo [ERROR] Preflight port probe failed for %~2 port %~1.
  echo [INFO ] Verify that PowerShell is available and rerun start_offline.bat.
  if not defined NO_PAUSE pause
  exit /b 1
)
exit /b 0
:ensure_db_migrated
REM 실행 DB 가 최신 마이그레이션 이전이면(예: 코드만 갱신하고 setup_offline 재실행을 건너뛴 경우)
REM 대시보드/뉴스레터가 500 으로 죽는다. setup_offline 과 동일한 ensure_db_state 분기로
REM 시작 전에 스키마를 head 로 맞춘다. 이미 head 면 no-op 이라 안전하다.
if not exist "%BACKEND_DIR%\.venv\Scripts\activate.bat" (
  echo [WARN ] backend venv missing; run setup_offline.bat first. Skipping migration preflight.
  exit /b 0
)
REM DATABASE_URL 을 명시적으로 넘겨 .env 로딩/작업 디렉토리 차이에 흔들리지 않게 한다.
REM setlocal 로 이 변경을 서브루틴 안에만 가두어 backend/frontend 실행 창에는 새지 않게 한다.
setlocal
set "AEROONE_DB_URL_PATH=%BACKEND_DIR:\=/%/data/aeroone.db"
pushd "%BACKEND_DIR%"
call .venv\Scripts\activate.bat
set "PYTHONPATH=."
set "DATABASE_URL=sqlite:///%AEROONE_DB_URL_PATH%"
call python scripts\ensure_db_state.py data\aeroone.db
set "MIGRATION_MODE=%ERRORLEVEL%"
if "%MIGRATION_MODE%"=="3" (
  echo [INFO ] Existing database without Alembic metadata detected. Stamping head.
  call alembic stamp head || echo [WARN ] alembic stamp head failed; check DB state.
) else (
  echo [INFO ] Applying pending database migrations ^(no-op if already current^)...
  call alembic upgrade head || echo [WARN ] alembic upgrade head failed; dashboard/newsletter may error until resolved.
)
popd
endlocal
exit /b 0


:validate_provider_credential_root
REM Validate-only preflight: start_offline.bat never creates, imports, or generates
REM a provider credential root or key. It confirms the SID-scoped ProgramData root
REM that setup_offline.bat provisioned still matches this runtime's current process
REM SID: exact owner, protected (non-inherited) DACL restricted to that SID plus
REM SYSTEM, no reparse-point components, and no unexpected hardlink on the root.
REM Fails closed with a generic exit code; never prints secret or path material.
set "PCV_SCRIPT=%TEMP%\aeroone_pcv_%RANDOM%%RANDOM%.ps1"
if exist "%PCV_SCRIPT%" del /f /q "%PCV_SCRIPT%" >nul 2>&1
>"%PCV_SCRIPT%" echo Set-StrictMode -Version Latest
>>"%PCV_SCRIPT%" echo $ErrorActionPreference = 'Stop'
>>"%PCV_SCRIPT%" echo try {
>>"%PCV_SCRIPT%" echo     $moduleRoot = Join-Path $env:AEROONE_ROOT 'scripts\credential_rotation'
>>"%PCV_SCRIPT%" echo     Import-Module (Join-Path $moduleRoot 'Rotation.PathSecurity.psm1') -Force -DisableNameChecking
>>"%PCV_SCRIPT%" echo     $currentSid = [Security.Principal.WindowsIdentity]::GetCurrent().User
>>"%PCV_SCRIPT%" echo     $systemSid = New-Object Security.Principal.SecurityIdentifier('S-1-5-18')
>>"%PCV_SCRIPT%" echo     $programData = [Environment]::GetFolderPath('CommonApplicationData')
>>"%PCV_SCRIPT%" echo     $vendorRoot = Join-Path $programData 'AeroOne'
>>"%PCV_SCRIPT%" echo     $familyRoot = Join-Path $vendorRoot 'provider-credentials'
>>"%PCV_SCRIPT%" echo     $sidRoot = Join-Path $familyRoot $currentSid.Value
>>"%PCV_SCRIPT%" echo     if (-not (Test-Path -LiteralPath $sidRoot -PathType Container)) {
>>"%PCV_SCRIPT%" echo         throw 'provider-credential-root-missing'
>>"%PCV_SCRIPT%" echo     }
>>"%PCV_SCRIPT%" echo     Assert-NoReparseComponents -Path $sidRoot
>>"%PCV_SCRIPT%" echo     $identity = Get-PhysicalPathIdentity -Path $sidRoot
>>"%PCV_SCRIPT%" echo     if (-not $identity.IsDirectory) {
>>"%PCV_SCRIPT%" echo         throw 'provider-credential-root-not-directory'
>>"%PCV_SCRIPT%" echo     }
>>"%PCV_SCRIPT%" echo     if ($identity.LinkCount -ne 1) {
>>"%PCV_SCRIPT%" echo         throw 'provider-credential-root-unexpected-hardlink'
>>"%PCV_SCRIPT%" echo     }
>>"%PCV_SCRIPT%" echo     $acl = Get-Acl -LiteralPath $sidRoot
>>"%PCV_SCRIPT%" echo     if (-not $acl.AreAccessRulesProtected) {
>>"%PCV_SCRIPT%" echo         throw 'provider-credential-root-unprotected-acl'
>>"%PCV_SCRIPT%" echo     }
>>"%PCV_SCRIPT%" echo     $ownerValue = $acl.Owner
>>"%PCV_SCRIPT%" echo     if ($ownerValue -notmatch '^^S-') {
>>"%PCV_SCRIPT%" echo         $ownerValue = (New-Object Security.Principal.NTAccount($ownerValue)).Translate([Security.Principal.SecurityIdentifier]).Value
>>"%PCV_SCRIPT%" echo     }
>>"%PCV_SCRIPT%" echo     if ($ownerValue -ne $currentSid.Value) {
>>"%PCV_SCRIPT%" echo         throw 'provider-credential-root-owner-mismatch'
>>"%PCV_SCRIPT%" echo     }
>>"%PCV_SCRIPT%" echo     $rules = @($acl.GetAccessRules($true, $false, [Security.Principal.SecurityIdentifier]))
>>"%PCV_SCRIPT%" echo     $expectedSids = @($currentSid.Value, $systemSid.Value) ^| Sort-Object
>>"%PCV_SCRIPT%" echo     $actualSids = @($rules ^| ForEach-Object { $_.IdentityReference.Value }) ^| Sort-Object
>>"%PCV_SCRIPT%" echo     if ($rules.Count -ne 2 -or @(Compare-Object $actualSids $expectedSids).Count -ne 0) {
>>"%PCV_SCRIPT%" echo         throw 'provider-credential-root-unexpected-dacl'
>>"%PCV_SCRIPT%" echo     }
>>"%PCV_SCRIPT%" echo     $propagation = [Security.AccessControl.PropagationFlags]::None
>>"%PCV_SCRIPT%" echo     $allow = [Security.AccessControl.AccessControlType]::Allow
>>"%PCV_SCRIPT%" echo     foreach ($rule in $rules) {
>>"%PCV_SCRIPT%" echo         if ($rule.AccessControlType -ne $allow) {
>>"%PCV_SCRIPT%" echo             throw 'provider-credential-root-unexpected-dacl'
>>"%PCV_SCRIPT%" echo         }
>>"%PCV_SCRIPT%" echo         if ($rule.PropagationFlags -ne $propagation) {
>>"%PCV_SCRIPT%" echo             throw 'provider-credential-root-unexpected-dacl'
>>"%PCV_SCRIPT%" echo         }
>>"%PCV_SCRIPT%" echo         $hasFullControl = ($rule.FileSystemRights -band [Security.AccessControl.FileSystemRights]::FullControl) -eq [Security.AccessControl.FileSystemRights]::FullControl
>>"%PCV_SCRIPT%" echo         if (-not $hasFullControl) {
>>"%PCV_SCRIPT%" echo             throw 'provider-credential-root-unexpected-dacl'
>>"%PCV_SCRIPT%" echo         }
>>"%PCV_SCRIPT%" echo     }
>>"%PCV_SCRIPT%" echo     Write-Output 'provider-credential-root-ok'
>>"%PCV_SCRIPT%" echo     exit 0
>>"%PCV_SCRIPT%" echo } catch {
>>"%PCV_SCRIPT%" echo     $code = $_.Exception.Message
>>"%PCV_SCRIPT%" echo     if ($code -notmatch '^^[a-z0-9-]+$') {
>>"%PCV_SCRIPT%" echo         $code = 'provider-credential-root-check-failed'
>>"%PCV_SCRIPT%" echo     }
>>"%PCV_SCRIPT%" echo     [Console]::Error.WriteLine("status=error code=$code")
>>"%PCV_SCRIPT%" echo     exit 1
>>"%PCV_SCRIPT%" echo }
set "AEROONE_ROOT=%ROOT%"
powershell -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%PCV_SCRIPT%"
set "PCV_EXIT=%ERRORLEVEL%"
set "AEROONE_ROOT="
del /f /q "%PCV_SCRIPT%" >nul 2>&1
if not "%PCV_EXIT%"=="0" (
  echo [ERROR] Provider credential store root failed identity/DACL/reparse/hardlink validation ^(fail-closed^).
  echo [INFO ] No provider key was created, read, written, or printed by this check.
  echo [INFO ] Re-run setup_offline.bat to re-provision the SID-scoped credential store, then rerun start_offline.bat.
  if not defined NO_PAUSE pause
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
echo Usage: start_offline.bat [--dry-run] [--open-browser] [--local] [--allow-host=^<host^>] [--no-pause]
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
echo --no-pause          Never wait on a pause prompt (non-interactive). Used by scripts\run_all.bat.
echo                     Environment fallback: AEROONE_NO_PAUSE.
exit /b 0
