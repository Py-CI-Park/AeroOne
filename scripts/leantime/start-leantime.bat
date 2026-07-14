@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

REM ==========================================================================
REM Leantime 동거(co-deploy) 기동 얇은 래퍼 — AeroOne 측 참조 launcher.
REM
REM Leantime 은 PHP + MariaDB + IIS 완제품(AGPL)이라 AeroOne 로 흡수하지 않고 '동거'한다.
REM 이 배치는 AeroOne 이 소유하는 얇은 위임 래퍼일 뿐, 실제 기동 로직(IIS AppPool/Website
REM start, MariaDB 서비스 start)은 운영자가 설치한 Leantime 스택 스크립트에 위임한다.
REM run_all.bat 이 AEROONE_LEANTIME_LAUNCHER 로 이 파일(또는 운영자 커스텀)을 호출한다.
REM
REM ⚠ 운영자 검증 필요: IIS/PHP/MariaDB 실제 설치·기동은 이 저장소 환경에서 검증 불가.
REM   아래 위임 경로/서비스명/AppPool 명은 운영자 환경에 맞게 실측 후 확정해야 한다.
REM   설치 절차: docs/runbook/leantime-codeploy.md 참조.
REM
REM 로그 계약: [LEANTIME][INFO|READY|WARN|ERROR] message
REM 종료 코드: 0 = 스택 미설치(선택적 폴백) 또는 준비 완료 / 2 = 위임은 했으나 타임아웃 내
REM   준비 완료 확인 실패(AeroOne 은 계속 진행한다).
REM 환경변수: AEROONE_LEANTIME_SCRIPTS(Start-All.ps1 위치), LEANTIME_PORT(기본 8081),
REM   AEROONE_LEANTIME_HEALTH_URL(기본 http://127.0.0.1:%LEANTIME_PORT%),
REM   AEROONE_LEANTIME_READY_TIMEOUT(초, 기본 60).
REM ==========================================================================

REM Leantime 스택 스크립트 위치: 환경변수 우선, 없으면 AeroOne 형제 폴더 ..\Leantime.
REM 운영자는 SaaS Kit(saas-kit-v2.0.0/scripts/Start-All.ps1) 을 이 경로에 배치하거나
REM AEROONE_LEANTIME_SCRIPTS 로 실제 경로를 가리킨다.
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "AEROONE_ROOT=%SCRIPT_DIR%\..\.."
pushd "%AEROONE_ROOT%" & set "AEROONE_ROOT=%CD%" & popd

if not defined AEROONE_LEANTIME_SCRIPTS set "AEROONE_LEANTIME_SCRIPTS=%AEROONE_ROOT%\..\Leantime\scripts"
if not defined LEANTIME_PORT set "LEANTIME_PORT=8081"

REM 포터블 동거 스택(별도 반입물 AeroOne-Leantime-Stack) 우선 감지 — 있으면 이쪽으로 위임.
if not defined AEROONE_LEANTIME_STACK set "AEROONE_LEANTIME_STACK=%AEROONE_ROOT%\..\AeroOne-Leantime-Stack"
if exist "%AEROONE_LEANTIME_STACK%\start-leantime-stack.bat" (
  echo [LEANTIME][INFO ] portable stack detected: %AEROONE_LEANTIME_STACK%
  call "%AEROONE_LEANTIME_STACK%\start-leantime-stack.bat"
  set "AEROONE_LEANTIME_HEALTH_URL=http://127.0.0.1:%LEANTIME_PORT%"
  goto :readiness
)

set "START_PS1=%AEROONE_LEANTIME_SCRIPTS%\Start-All.ps1"

echo [LEANTIME][INFO ] launcher wrapper
echo [LEANTIME][INFO ] stack scripts : %AEROONE_LEANTIME_SCRIPTS%
echo [LEANTIME][INFO ] expected port  : %LEANTIME_PORT%

if not exist "%START_PS1%" (
  echo [LEANTIME][INFO ] Start-All.ps1 not found at "%START_PS1%".
  echo [LEANTIME][INFO ] Leantime co-deploy stack is not installed on this host.
  echo [LEANTIME][INFO ] AeroOne dashboard still shows the Leantime link card ^(integration
  echo [LEANTIME][INFO ] surface^), but the target app must be installed by the operator.
  echo [LEANTIME][INFO ] See docs\runbook\leantime-codeploy.md ^(operator install required^).
  REM 폴백: AeroOne 기동을 막지 않도록 성공 코드로 종료(동거는 선택적).
  exit /b 0
)

REM ⚠ 운영자 검증 필요: Start-All.ps1 은 IIS/MariaDB 서비스를 켜므로 관리자 권한이 필요할
REM   수 있다(이 배치 자체는 관리자 권한을 요구하지 않는다). 실 배포에서 권한/서비스명/
REM   AppPool 명을 실측해 확정한다.
echo [LEANTIME][INFO ] delegating to Start-All.ps1 ...
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%START_PS1%"
set "PS_EXIT=%errorlevel%"
if not "%PS_EXIT%"=="0" (
  echo [LEANTIME][WARN ] Start-All.ps1 returned %PS_EXIT%. Leantime may not be up.
  echo [LEANTIME][WARN ] AeroOne remains running regardless ^(co-deploy is optional^).
)

:readiness
REM HTTP 준비 대기: run_all.bat 의 :wait_health 와 동일한 Invoke-WebRequest 폴링 패턴.
REM 대상은 AEROONE_LEANTIME_HEALTH_URL 우선, 없으면 http://127.0.0.1:%LEANTIME_PORT%.
if not defined AEROONE_LEANTIME_HEALTH_URL (
  set "HEALTH_URL=http://127.0.0.1:%LEANTIME_PORT%"
) else (
  set "HEALTH_URL=%AEROONE_LEANTIME_HEALTH_URL%"
)
if not defined AEROONE_LEANTIME_READY_TIMEOUT set "AEROONE_LEANTIME_READY_TIMEOUT=60"

echo [LEANTIME][INFO ] waiting for readiness at %HEALTH_URL% ^(max %AEROONE_LEANTIME_READY_TIMEOUT%s^)...
call :wait_ready "%HEALTH_URL%" %AEROONE_LEANTIME_READY_TIMEOUT%
if errorlevel 1 (
  echo [LEANTIME][WARN ] Leantime did not become ready within %AEROONE_LEANTIME_READY_TIMEOUT%s at %HEALTH_URL%.
  echo [LEANTIME][WARN ] IIS AppPool/Website 또는 MariaDB 서비스가 아직 기동 중일 수 있다
  echo [LEANTIME][WARN ] ^(관리자 권한으로 재확인 필요할 수 있음^). AeroOne 은 계속 진행한다.
  exit /b 2
)
echo [LEANTIME][READY] Leantime responded at %HEALTH_URL%.
exit /b 0

:wait_ready
REM %1 url, %2 timeout seconds — run_all.bat 의 :wait_health 와 동일한 폴링 패턴.
REM URL 은 문자열 보간 대신 환경변수로 넘겨 따옴표/세미콜론 등이 명령을 깨지 않게 한다.
set "LT_WAIT_URL=%~1"
powershell -NoLogo -NoProfile -Command "$u=$env:LT_WAIT_URL;$t=%~2;$ok=$false;for($i=0;$i -lt $t;$i++){try{$r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 $u; if($r.StatusCode -eq 200){$ok=$true;break}}catch{}; Start-Sleep -Seconds 1}; if($ok){exit 0}else{exit 1}"
set "LT_WAIT_EXIT=%errorlevel%"
set "LT_WAIT_URL="
exit /b %LT_WAIT_EXIT%
