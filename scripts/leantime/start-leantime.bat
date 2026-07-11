@echo off
setlocal EnableExtensions EnableDelayedExpansion

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

set "START_PS1=%AEROONE_LEANTIME_SCRIPTS%\Start-All.ps1"

echo [LEANTIME] launcher wrapper
echo [LEANTIME] stack scripts : %AEROONE_LEANTIME_SCRIPTS%
echo [LEANTIME] expected port  : %LEANTIME_PORT%

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
REM   수 있다. 실 배포에서 권한/서비스명/AppPool 명을 실측해 확정한다.
echo [LEANTIME] delegating to Start-All.ps1 ...
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%START_PS1%"
set "PS_EXIT=%errorlevel%"
if not "%PS_EXIT%"=="0" (
  echo [LEANTIME][WARN ] Start-All.ps1 returned %PS_EXIT%. Leantime may not be up.
  echo [LEANTIME][WARN ] AeroOne remains running regardless ^(co-deploy is optional^).
)
exit /b 0
