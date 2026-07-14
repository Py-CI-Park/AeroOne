@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

REM ==========================================================================
REM Leantime 동거(co-deploy) 재기동 얇은 래퍼 — AeroOne 측 참조 launcher.
REM
REM stop-leantime.bat 을 호출한 뒤 start-leantime.bat 을 호출한다(HTTP 준비 대기 포함).
REM 정지 단계의 실패는 무시하고 항상 기동을 시도한다 — Leantime 이 없어도 AeroOne 은
REM 영향받지 않는다(동거는 선택적).
REM
REM 로그 계약: [LEANTIME][INFO|READY|WARN|ERROR] message (하위 스크립트에서 방출)
REM 종료 코드: start-leantime.bat 의 종료 코드를 그대로 반환한다.
REM   0 = 스택 미설치(선택적 폴백) 또는 준비 완료 / 2 = 위임은 했으나 타임아웃 내
REM   준비 완료 확인 실패.
REM 환경변수: AEROONE_LEANTIME_SCRIPTS, LEANTIME_PORT(기본 8081),
REM   AEROONE_LEANTIME_HEALTH_URL, AEROONE_LEANTIME_READY_TIMEOUT.
REM ==========================================================================

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

echo [LEANTIME][INFO ] restart wrapper: stop then start ...

call "%SCRIPT_DIR%\stop-leantime.bat"
if errorlevel 1 (
  echo [LEANTIME][WARN ] stop-leantime.bat returned %errorlevel%. continuing to start anyway.
)

call "%SCRIPT_DIR%\start-leantime.bat"
exit /b %errorlevel%
