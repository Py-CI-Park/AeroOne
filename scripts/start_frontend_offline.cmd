@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
set "FRONTEND_DIR=%ROOT%\frontend"

cd /d "%FRONTEND_DIR%" || exit /b 1
if not exist "node_modules\.bin\next.cmd" (
  echo [ERROR] frontend\node_modules\.bin\next.cmd 가 없습니다. setup_offline.bat 으로 의존성 복원이 필요합니다.
  exit /b 1
)
if defined AEROONE_ALLOW_HOST (
  call .\node_modules\.bin\next.cmd start -H 0.0.0.0 -p 29501
) else (
  call .\node_modules\.bin\next.cmd start -H 127.0.0.1 -p 29501
)
exit /b %errorlevel%
