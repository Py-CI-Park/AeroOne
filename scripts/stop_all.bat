@echo off
setlocal EnableExtensions

REM AeroOne + Open Notebook 공동 정지. run_all.bat 의 역(逆) — 먼저 Open Notebook 번들을
REM (있으면) 정지하고, 그 다음 AeroOne 의 backend/frontend 창을 종료한다.

set "SCRIPTS_DIR=%~dp0"
if "%SCRIPTS_DIR:~-1%"=="\" set "SCRIPTS_DIR=%SCRIPTS_DIR:~0,-1%"
set "ROOT=%SCRIPTS_DIR%\.."
pushd "%ROOT%" & set "ROOT=%CD%" & popd

set "ON_BUNDLE=%AEROONE_ON_BUNDLE%"
if /I "%~1"=="--on-bundle" set "ON_BUNDLE=%~2"
if /I "%~1"=="--help" goto :help
if not defined ON_BUNDLE set "ON_BUNDLE=%ROOT%\..\AeroOne-bundle"
set "ON_STOP=%ON_BUNDLE%\stop.bat"

echo [STOP-ALL] stopping Open Notebook bundle (if present)...
if exist "%ON_STOP%" (
  pushd "%ON_BUNDLE%"
  call "%ON_STOP%"
  popd
) else (
  echo [STOP-ALL][INFO ] ON stop script not found: %ON_STOP% ^(skipping^)
)

echo [STOP-ALL] stopping AeroOne windows...
taskkill /FI "WINDOWTITLE eq AeroOne Backend Offline*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq AeroOne Frontend Offline*" /T /F >nul 2>&1
echo [STOP-ALL] done.
exit /b 0

:help
echo Usage: stop_all.bat [--on-bundle ^<path^>]
echo.
echo Stops the Open Notebook airgap bundle (via its stop.bat) and then the AeroOne
echo backend/frontend windows opened by start_offline.bat / run_all.bat.
echo   --on-bundle ^<path^>  Open Notebook bundle dir (default ..\AeroOne-bundle or env AEROONE_ON_BUNDLE).
exit /b 0
