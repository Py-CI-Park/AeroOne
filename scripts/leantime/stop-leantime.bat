@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

REM ==========================================================================
REM Leantime 동거(co-deploy) 정지 얇은 래퍼 — AeroOne 측 참조 launcher.
REM
REM start-leantime.bat 의 대칭 스크립트. 실제 정지 로직(IIS AppPool/Website stop,
REM MariaDB 서비스 stop)은 운영자가 설치한 Leantime 스택의 Stop-All.ps1 에 위임한다.
REM 이 스크립트가 없거나 실패해도 AeroOne 은 영향받지 않는다(동거는 선택적).
REM
REM 로그 계약: [LEANTIME][INFO|WARN|ERROR] message
REM 종료 코드: 항상 0 (정지 훅은 참고용이며 AeroOne/호출자를 막지 않는다).
REM 환경변수: AEROONE_LEANTIME_SCRIPTS(Stop-All.ps1 위치), LEANTIME_PORT(기본 8081).
REM ==========================================================================

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "AEROONE_ROOT=%SCRIPT_DIR%\..\.."
pushd "%AEROONE_ROOT%" & set "AEROONE_ROOT=%CD%" & popd

if not defined AEROONE_LEANTIME_SCRIPTS set "AEROONE_LEANTIME_SCRIPTS=%AEROONE_ROOT%\..\Leantime\scripts"
if not defined LEANTIME_PORT set "LEANTIME_PORT=8081"

set "STOP_PS1=%AEROONE_LEANTIME_SCRIPTS%\Stop-All.ps1"

echo [LEANTIME][INFO ] stopper wrapper
echo [LEANTIME][INFO ] stack scripts : %AEROONE_LEANTIME_SCRIPTS%

if not exist "%STOP_PS1%" (
  echo [LEANTIME][INFO ] Stop-All.ps1 not found at "%STOP_PS1%".
  echo [LEANTIME][INFO ] Leantime co-deploy stack is not installed on this host ^(no-op^).
  exit /b 0
)

echo [LEANTIME][INFO ] delegating to Stop-All.ps1 ...
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%STOP_PS1%"
set "PS_EXIT=%errorlevel%"
if not "%PS_EXIT%"=="0" (
  echo [LEANTIME][WARN ] Stop-All.ps1 returned %PS_EXIT%. Leantime may still be running.
) else (
  echo [LEANTIME][INFO ] Stop-All.ps1 completed.
)
exit /b 0
