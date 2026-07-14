@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

REM ==========================================================================
REM Leantime 동거(co-deploy) 백업 얇은 래퍼 — AeroOne 측 참조 launcher.
REM
REM Leantime 은 PHP, MariaDB, IIS 완제품(AGPL) - official unmodified release,
REM no plugin patch, no core patch 이라 AeroOne 로 흡수하지 않고 '동거'한다.
REM 이 배치는 얇은 위임 래퍼일 뿐, 실제 백업 로직 - MariaDB dump + Leantime
REM 업로드/설정 파일 백업 - 은 운영자가 설치한 Leantime 스택의 Backup-All.ps1
REM 에 위임한다. Backup-All.ps1 이 없으면 no-op 으로 안내만 하고 성공 코드로
REM 끝난다. 이 스크립트는 AeroOne 수명주기(run_all.bat/start.bat 등)에서
REM 호출되지 않으므로 실패해도 AeroOne 을 막을 일이 없다(운영자가 직접 실행).
REM
REM 로그 계약: [LEANTIME][INFO|WARN|ERROR] message
REM 종료 코드: 0 = 백업 성공 또는 Backup-All.ps1 부재(선택적 no-op) /
REM   2 = 위임했으나 Backup-All.ps1 이 실패 / 1 = 사용법/경로 오류.
REM 환경변수: AEROONE_LEANTIME_SCRIPTS(Backup-All.ps1 위치, 기본 ..\Leantime\scripts).
REM ==========================================================================

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "AEROONE_ROOT=%SCRIPT_DIR%\..\.."
pushd "%AEROONE_ROOT%" & set "AEROONE_ROOT=%CD%" & popd

if not defined AEROONE_LEANTIME_SCRIPTS set "AEROONE_LEANTIME_SCRIPTS=%AEROONE_ROOT%\..\Leantime\scripts"

set "BACKUP_PS1=%AEROONE_LEANTIME_SCRIPTS%\Backup-All.ps1"

echo [LEANTIME][INFO ] backup wrapper
echo [LEANTIME][INFO ] stack scripts : %AEROONE_LEANTIME_SCRIPTS%

if not exist "%BACKUP_PS1%" (
  echo [LEANTIME][INFO ] Backup-All.ps1 not found at "%BACKUP_PS1%".
  echo [LEANTIME][INFO ] Leantime backup is operator-owned and not installed on this host ^(no-op^).
  echo [LEANTIME][INFO ] Operator action: dump MariaDB ^(Leantime schema^) + copy Leantime upload/config
  echo [LEANTIME][INFO ] folders to access-controlled storage. See docs\runbook\leantime-codeploy.md ^(sec. 5^).
  exit /b 0
)

echo [LEANTIME][INFO ] delegating to Backup-All.ps1 ...
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%BACKUP_PS1%"
set "PS_EXIT=%errorlevel%"
if not "%PS_EXIT%"=="0" (
  echo [LEANTIME][ERROR] Backup-All.ps1 returned %PS_EXIT%. Leantime backup may be incomplete.
  exit /b 2
)
echo [LEANTIME][INFO ] Backup-All.ps1 completed.
exit /b 0
