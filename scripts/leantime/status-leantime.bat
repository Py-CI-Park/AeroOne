@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

REM ==========================================================================
REM Leantime 동거(co-deploy) 상태 조회 얇은 래퍼 — AeroOne 측 참조 launcher.
REM
REM 대상 host:port 로 단발 HTTP 프로브를 수행해 한 줄로 상태를 출력한다. AeroOne
REM 백엔드의 GET /api/v1/leantime/health 와 같은 판정 축(ready/starting/unhealthy/
REM absent/error)을 쓰지만, 이 스크립트는 운영자가 커맨드라인에서 빠르게 확인하기
REM 위한 독립 도구이며 AeroOne 백엔드 API 를 호출하지 않는다(직접 프로브).
REM
REM 로그 계약: [LEANTIME][STATUS] <status> target=<host:port>  (한 줄만 출력)
REM 종료 코드: 0 = ready / 3 = starting|unhealthy|absent(준비 안 됨) / 1 = error(프로브 자체 실패)
REM 환경변수: LEANTIME_PORT(기본 8081), AEROONE_LEANTIME_HEALTH_URL(기본
REM   http://127.0.0.1:%LEANTIME_PORT%).
REM ==========================================================================

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "AEROONE_ROOT=%SCRIPT_DIR%\..\.."
pushd "%AEROONE_ROOT%" & set "AEROONE_ROOT=%CD%" & popd

if not defined AEROONE_LEANTIME_SCRIPTS set "AEROONE_LEANTIME_SCRIPTS=%AEROONE_ROOT%\..\Leantime\scripts"
if not defined LEANTIME_PORT set "LEANTIME_PORT=8081"

if not defined AEROONE_LEANTIME_HEALTH_URL (
  set "HEALTH_URL=http://127.0.0.1:%LEANTIME_PORT%"
) else (
  set "HEALTH_URL=%AEROONE_LEANTIME_HEALTH_URL%"
)

set "LT_STATUS="
set "LT_TARGET="
for /f "usebackq tokens=1,2 delims=|" %%A in (`powershell -NoLogo -NoProfile -Command "$u=$env:HEALTH_URL;$uri=[Uri]$u;$target=$uri.Host+':'+$uri.Port;$status='error';try{$r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 $u;$code=[int]$r.StatusCode;$body=[string]$r.Content;if($code -ge 500){$status='starting'}elseif($code -ge 400){$status='unhealthy'}elseif($body -match '(?i)leantime'){$status='ready'}else{$status='unhealthy'}}catch{$ex=$_.Exception;$resp=$null;if($ex -is [System.Net.WebException]){$resp=$ex.Response};if($resp -ne $null){$code=[int]$resp.StatusCode;if($code -ge 500){$status='starting'}else{$status='unhealthy'}}elseif($ex.Message -match 'timed out|timeout'){$status='starting'}elseif($ex.Message -match 'refused|target machine|No connection|unreachable'){$status='absent'}else{$status='absent'}};Write-Host ($status+'|'+$target)"`) do (
  set "LT_STATUS=%%A"
  set "LT_TARGET=%%B"
)

if not defined LT_STATUS set "LT_STATUS=error"
if not defined LT_TARGET set "LT_TARGET=%HEALTH_URL%"

if /I "%LT_STATUS%"=="ready" (
  set "LT_EXIT=0"
) else if /I "%LT_STATUS%"=="error" (
  set "LT_EXIT=1"
) else (
  set "LT_EXIT=3"
)

echo [LEANTIME][STATUS] %LT_STATUS% target=%LT_TARGET%
exit /b %LT_EXIT%
