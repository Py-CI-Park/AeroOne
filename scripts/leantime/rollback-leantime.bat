@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

REM ==========================================================================
REM Leantime 동거(co-deploy) 롤백 얇은 래퍼 — AeroOne 측 참조 launcher.
REM
REM Leantime 은 PHP, MariaDB, IIS 완제품(AGPL) - official unmodified release,
REM no plugin patch, no core patch 이라 AeroOne 로 흡수하지 않고 '동거'한다.
REM 이 배치는 얇은 위임 래퍼일 뿐, 실제 롤백 로직 - 현재 설치를 이전에 검증된
REM 핀 버전 번들로 재지정, bundle swap + verify-bundle.bat 재검증 + 서비스
REM 재기동 - 은 운영자가 설치한 Leantime 스택의 Rollback-All.ps1 에 위임한다.
REM Rollback-All.ps1 이 없으면 no-op 으로 안내만 하고 성공 코드로 끝난다.
REM 이 스크립트는 AeroOne 수명주기(run_all.bat/start.bat 등)에서 호출되지
REM 않으므로 실패해도 AeroOne 을 막을 일이 없다(운영자가 직접 실행).
REM
REM 사용법: rollback-leantime.bat [previous_bundle_dir]
REM   previous_bundle_dir 는 선택 인자로, Rollback-All.ps1 에 -PreviousBundleDir
REM   로 그대로 전달된다(이전에 verify-bundle.bat 로 검증된 핀 버전 번들 경로).
REM
REM 로그 계약: [LEANTIME][INFO|WARN|ERROR] message
REM 종료 코드: 0 = 롤백 성공 또는 Rollback-All.ps1 부재(선택적 no-op) /
REM   2 = 위임했으나 Rollback-All.ps1 이 실패 / 1 = 사용법/경로 오류.
REM 환경변수: AEROONE_LEANTIME_SCRIPTS(Rollback-All.ps1 위치, 기본 ..\Leantime\scripts).
REM ==========================================================================

set "PREVIOUS_BUNDLE_DIR=%~1"

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "AEROONE_ROOT=%SCRIPT_DIR%\..\.."
pushd "%AEROONE_ROOT%" & set "AEROONE_ROOT=%CD%" & popd

if not defined AEROONE_LEANTIME_SCRIPTS set "AEROONE_LEANTIME_SCRIPTS=%AEROONE_ROOT%\..\Leantime\scripts"

set "ROLLBACK_PS1=%AEROONE_LEANTIME_SCRIPTS%\Rollback-All.ps1"

echo [LEANTIME][INFO ] rollback wrapper
echo [LEANTIME][INFO ] stack scripts : %AEROONE_LEANTIME_SCRIPTS%
if defined PREVIOUS_BUNDLE_DIR echo [LEANTIME][INFO ] previous bundle : %PREVIOUS_BUNDLE_DIR%

if not exist "%ROLLBACK_PS1%" (
  echo [LEANTIME][INFO ] Rollback-All.ps1 not found at "%ROLLBACK_PS1%".
  echo [LEANTIME][INFO ] Leantime rollback is operator-owned and not installed on this host ^(no-op^).
  echo [LEANTIME][INFO ] Operator action: re-point the install to a previously verified pinned
  echo [LEANTIME][INFO ] bundle ^(re-run scripts\leantime\verify-bundle.bat against it first^), then
  echo [LEANTIME][INFO ] restart the stack. See docs\runbook\leantime-codeploy.md.
  exit /b 0
)

echo [LEANTIME][INFO ] delegating to Rollback-All.ps1 ...
if defined PREVIOUS_BUNDLE_DIR (
  powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%ROLLBACK_PS1%" -PreviousBundleDir "%PREVIOUS_BUNDLE_DIR%"
) else (
  powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%ROLLBACK_PS1%"
)
set "PS_EXIT=%errorlevel%"
if not "%PS_EXIT%"=="0" (
  echo [LEANTIME][ERROR] Rollback-All.ps1 returned %PS_EXIT%. Leantime rollback may be incomplete.
  exit /b 2
)
echo [LEANTIME][INFO ] Rollback-All.ps1 completed.
exit /b 0
