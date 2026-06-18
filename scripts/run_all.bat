@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM AeroOne + Open Notebook 폐쇄망 공동 기동 (staggered, 무상태 래퍼).
REM AeroOne 를 먼저 띄우고 backend health 200 을 확인한 뒤 Open Notebook 번들을 기동한다.
REM 두 스택은 별도 프로세스 군 / 별도 빌드 / 별도 DB·세션·포트 — 이 스크립트는 호출만 위임한다.
REM Open Notebook 번들이 없으면 명확히 알리고 AeroOne 단독으로 둔다(폴백).

set "SCRIPTS_DIR=%~dp0"
if "%SCRIPTS_DIR:~-1%"=="\" set "SCRIPTS_DIR=%SCRIPTS_DIR:~0,-1%"
set "ROOT=%SCRIPTS_DIR%\.."
pushd "%ROOT%" & set "ROOT=%CD%" & popd

set "ON_BUNDLE=%AEROONE_ON_BUNDLE%"
set "DRY_RUN="
set "PASSTHRU="
set "ON_PASSTHRU="

:parse
if "%~1"=="" goto :parsed
if /I "%~1"=="--dry-run" (set "DRY_RUN=1" & shift & goto :parse)
if /I "%~1"=="--on-bundle" (set "ON_BUNDLE=%~2" & shift & shift & goto :parse)
if /I "%~1"=="--help" goto :help
if /I "%~1"=="--local" (set "PASSTHRU=%PASSTHRU% %~1" & set "ON_PASSTHRU=%ON_PASSTHRU% %~1" & shift & goto :parse)
if /I "%~1"=="--allow-host" (set "PASSTHRU=%PASSTHRU% %~1 %~2" & set "ON_PASSTHRU=%ON_PASSTHRU% %~1 %~2" & shift & shift & goto :parse)
set "ARG=%~1"
if /I "!ARG:~0,13!"=="--allow-host=" (set "PASSTHRU=%PASSTHRU% %~1" & set "ON_PASSTHRU=%ON_PASSTHRU% %~1" & shift & goto :parse)
set "PASSTHRU=%PASSTHRU% %~1"
shift
goto :parse
:parsed

REM Open Notebook 번들 경로: --on-bundle <path> 또는 env AEROONE_ON_BUNDLE, 기본 = AeroOne 형제 폴더 ..\AeroOne-bundle
if not defined ON_BUNDLE set "ON_BUNDLE=%ROOT%\..\AeroOne-bundle"
set "ON_RUN=%ON_BUNDLE%\3-run.bat"

set "BACKEND_PORT=18437"
set "FRONTEND_PORT=29501"
set "ON_DB_PORT=8000"
set "ON_API_PORT=5055"
set "ON_FE_PORT=8502"
set "ON_TIMEOUT=90"

echo ==================================================
echo [RUN-ALL] AeroOne + Open Notebook staggered launcher
echo [RUN-ALL] AeroOne root : %ROOT%
echo [RUN-ALL] ON bundle    : %ON_BUNDLE%
echo ==================================================

if "%DRY_RUN%"=="1" goto :dry

REM 1) 포트 preflight 5종 (AeroOne 포트 점유 시 중단, Open Notebook 포트는 경고만)
call :probe_port %BACKEND_PORT%  "AeroOne backend"        strict
if errorlevel 1 goto :abort
call :probe_port %FRONTEND_PORT% "AeroOne frontend"       strict
if errorlevel 1 goto :abort
call :probe_port %ON_DB_PORT%    "Open Notebook SurrealDB" warn
call :probe_port %ON_API_PORT%   "Open Notebook API"       warn
call :probe_port %ON_FE_PORT%    "Open Notebook Frontend"  warn

REM 2) AeroOne 기동 (extra args 는 start_offline.bat 으로 통과)
echo [RUN-ALL] starting AeroOne...
call "%ROOT%\start_offline.bat" --no-pause%PASSTHRU%
if errorlevel 1 (
  echo [RUN-ALL][ERROR] AeroOne failed to start. aborting before Open Notebook.
  goto :abort
)

REM 3) backend health 대기 (최대 30s) — staggered 의 핵심: ON cold-load 전에 AeroOne 안정화
echo [RUN-ALL] waiting for AeroOne backend health...
call :wait_health "http://127.0.0.1:%BACKEND_PORT%/api/v1/health" 30
if errorlevel 1 (
  echo [RUN-ALL][ERROR] AeroOne backend health not reached in 30s.
  goto :abort
)
echo [RUN-ALL] AeroOne backend healthy.

REM 4) Open Notebook 기동 (있으면), 없으면 단독 폴백
if not exist "%ON_RUN%" (
  echo [RUN-ALL][WARN ] Open Notebook bundle launcher not found:
  echo [RUN-ALL][WARN ]   %ON_RUN%
  echo [RUN-ALL][INFO ] AeroOne is running standalone ^(fallback^). Place the Open Notebook
  echo [RUN-ALL][INFO ] airgap bundle beside AeroOne ^(default ..\AeroOne-bundle^) or pass
  echo [RUN-ALL][INFO ] --on-bundle ^<path^>, then rerun run_all.bat.
  exit /b 0
)
echo [RUN-ALL] starting Open Notebook bundle...
pushd "%ON_BUNDLE%"
call "%ON_RUN%"%ON_PASSTHRU%
set "ON_EXIT=!errorlevel!"
popd
if not "!ON_EXIT!"=="0" (
  echo [RUN-ALL][WARN ] Open Notebook launcher returned !ON_EXIT!. AeroOne remains up.
  exit /b !ON_EXIT!
)

echo [RUN-ALL] waiting for Open Notebook API health...
call :wait_health "http://127.0.0.1:%ON_API_PORT%/health" %ON_TIMEOUT%
if errorlevel 1 (
  echo [RUN-ALL][ERROR] Open Notebook API health not reached in %ON_TIMEOUT%s. AeroOne remains up.
  goto :abort
)
echo [RUN-ALL] Open Notebook API healthy.

echo [RUN-ALL] waiting for Open Notebook frontend...
call :wait_health "http://127.0.0.1:%ON_FE_PORT%/" %ON_TIMEOUT%
if errorlevel 1 (
  echo [RUN-ALL][ERROR] Open Notebook frontend not reached in %ON_TIMEOUT%s. AeroOne remains up.
  goto :abort
)
echo [RUN-ALL] Open Notebook frontend healthy.

call :inspect_on_config "http://127.0.0.1:%ON_FE_PORT%/config"
if errorlevel 1 (
  echo [RUN-ALL][ERROR] Open Notebook runtime config was not readable. AeroOne remains up.
  goto :abort
)
echo ==================================================
echo [RUN-ALL][READY] AeroOne ^(:%FRONTEND_PORT%^) + Open Notebook ^(:%ON_FE_PORT%^) launched.
echo ==================================================
exit /b 0

:dry
echo [DRY-RUN] preflight ports: %BACKEND_PORT% %FRONTEND_PORT% %ON_DB_PORT% %ON_API_PORT% %ON_FE_PORT%
call :probe_port %BACKEND_PORT%  "AeroOne backend"        warn
call :probe_port %FRONTEND_PORT% "AeroOne frontend"       warn
call :probe_port %ON_DB_PORT%    "Open Notebook SurrealDB" warn
call :probe_port %ON_API_PORT%   "Open Notebook API"       warn
call :probe_port %ON_FE_PORT%    "Open Notebook Frontend"  warn
echo [DRY-RUN] would call "%ROOT%\start_offline.bat" --no-pause%PASSTHRU%
echo [DRY-RUN] would wait backend health http://127.0.0.1:%BACKEND_PORT%/api/v1/health ^(max 30s^)
if exist "%ON_RUN%" (
  echo [DRY-RUN] would call "%ON_RUN%"%ON_PASSTHRU%
  echo [DRY-RUN] would wait Open Notebook API health http://127.0.0.1:%ON_API_PORT%/health ^(max %ON_TIMEOUT%s^)
  echo [DRY-RUN] would wait Open Notebook frontend http://127.0.0.1:%ON_FE_PORT%/ ^(max %ON_TIMEOUT%s^)
  echo [DRY-RUN] would inspect Open Notebook runtime config http://127.0.0.1:%ON_FE_PORT%/config
) else (
  echo [DRY-RUN] ON bundle missing at "%ON_RUN%" -^> AeroOne standalone fallback
)
exit /b 0

:abort
echo [RUN-ALL][FAILED] startup aborted.
exit /b 1

:probe_port
REM %1 port, %2 label, %3 mode(strict|warn)
powershell -NoLogo -NoProfile -Command "$b=[System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()|Where-Object{$_.Port -eq %~1}; if($b){exit 1}else{exit 0}"
if errorlevel 1 (
  if /I "%~3"=="strict" (
    echo [RUN-ALL][ERROR] %~2 port %~1 already in use. release it and rerun.
    exit /b 1
  )
  echo [RUN-ALL][WARN ] %~2 port %~1 already in use ^(possible conflict^).
  exit /b 0
)
echo [RUN-ALL][INFO ] %~2 port %~1 free.
exit /b 0

:wait_health
REM %1 url, %2 timeout seconds
powershell -NoLogo -NoProfile -Command "$u='%~1';$t=%~2;$ok=$false;for($i=0;$i -lt $t;$i++){try{$r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 $u; if($r.StatusCode -eq 200){$ok=$true;break}}catch{}; Start-Sleep -Seconds 1}; if($ok){exit 0}else{exit 1}"
exit /b %errorlevel%

:inspect_on_config
REM %1 url
powershell -NoLogo -NoProfile -Command "$u='%~1'; try { $cfg=Invoke-RestMethod -TimeoutSec 5 $u; $api=[string]$cfg.apiUrl; if ([string]::IsNullOrWhiteSpace($api)) { Write-Host '[RUN-ALL][INFO ] Open Notebook browser API URL = (relative /api proxy)'; } else { Write-Host ('[RUN-ALL][INFO ] Open Notebook browser API URL = ' + $api); }; exit 0 } catch { Write-Host ('[RUN-ALL][ERROR] Open Notebook /config failed: ' + $_.Exception.Message); exit 1 }"
exit /b %errorlevel%

:help
echo Usage: run_all.bat [--dry-run] [--on-bundle ^<path^>] [start_offline passthrough args]
echo.
echo Staggered co-deploy launcher: starts AeroOne, waits for backend health, then
echo starts the Open Notebook airgap bundle. If the ON bundle is missing, AeroOne
echo runs standalone (fallback). `--local` and `--allow-host` are passed to both launchers;
echo other extra args are passed through to start_offline.bat only.
echo.
echo   --dry-run           Print the launch plan + port preflight, change nothing.
echo   --on-bundle ^<path^>  Open Notebook bundle dir (default ..\AeroOne-bundle or env AEROONE_ON_BUNDLE).
exit /b 0
