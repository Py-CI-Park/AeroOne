@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

REM ==========================================================================
REM Leantime 동거(co-deploy) 복구 얇은 래퍼 — AeroOne 측 참조 launcher.
REM
REM Leantime 은 PHP, MariaDB, IIS 완제품(AGPL) - official unmodified release,
REM no plugin patch, no core patch 이라 AeroOne 로 흡수하지 않고 '동거'한다.
REM 이 배치는 얇은 위임 래퍼일 뿐, 실제 복구 로직 - MariaDB 스키마 복원 +
REM Leantime 업로드/설정 파일 복원 - 은 운영자가 설치한 Leantime 스택의
REM Restore-All.ps1 에 위임한다. Restore-All.ps1 이 없으면 no-op 으로
REM 안내만 하고 성공 코드로 끝난다. 이 스크립트는 AeroOne 수명주기
REM (run_all.bat/start.bat 등)에서 호출되지 않으므로 실패해도 AeroOne 을
REM 막을 일이 없다(운영자가 직접 실행하는 복구 리허설/재해복구 절차).
REM
REM 로그 계약: [LEANTIME][INFO|WARN|ERROR] message
REM 종료 코드: 0 = 복구 성공 또는 Restore-All.ps1 부재(선택적 no-op) /
REM   2 = 위임했으나 Restore-All.ps1 이 실패 / 1 = 사용법/경로 오류.
REM 환경변수: AEROONE_LEANTIME_SCRIPTS(Restore-All.ps1 위치, 기본 ..\Leantime\scripts).
REM ==========================================================================

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "AEROONE_ROOT=%SCRIPT_DIR%\..\.."
pushd "%AEROONE_ROOT%" & set "AEROONE_ROOT=%CD%" & popd

if not defined AEROONE_LEANTIME_SCRIPTS set "AEROONE_LEANTIME_SCRIPTS=%AEROONE_ROOT%\..\Leantime\scripts"

set "RESTORE_PS1=%AEROONE_LEANTIME_SCRIPTS%\Restore-All.ps1"

echo [LEANTIME][INFO ] restore wrapper
echo [LEANTIME][INFO ] stack scripts : %AEROONE_LEANTIME_SCRIPTS%

if not exist "%RESTORE_PS1%" (
  echo [LEANTIME][INFO ] Restore-All.ps1 not found at "%RESTORE_PS1%".
  echo [LEANTIME][INFO ] Leantime restore is operator-owned and not installed on this host ^(no-op^).
  echo [LEANTIME][INFO ] Operator action: restore MariaDB dump ^(Leantime schema^) + Leantime
  echo [LEANTIME][INFO ] upload/config folders from access-controlled backup storage. See
  echo [LEANTIME][INFO ] docs\runbook\leantime-codeploy.md ^(sec. 5^).
  exit /b 0
)

echo [LEANTIME][INFO ] delegating to Restore-All.ps1 ...
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%RESTORE_PS1%"
set "PS_EXIT=%errorlevel%"
if not "%PS_EXIT%"=="0" (
  echo [LEANTIME][ERROR] Restore-All.ps1 returned %PS_EXIT%. Leantime restore may be incomplete.
  exit /b 2
)
echo [LEANTIME][INFO ] Restore-All.ps1 completed.
exit /b 0
