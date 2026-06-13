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

REM next.cmd invokes node via PATH. If Node is installed but PATH was not
REM refreshed in this window (common with Explorer double-click), prepend the
REM standard install dir so node resolves. Harmless when node is already found.
if exist "%ProgramFiles%\nodejs\node.exe" set "PATH=%ProgramFiles%\nodejs;%PATH%"
if exist "%LOCALAPPDATA%\Programs\nodejs\node.exe" set "PATH=%LOCALAPPDATA%\Programs\nodejs;%PATH%"

REM Parent shell variables can leak from Docker/CI sessions and override generated .env.local.
REM Keep Next.js server-side proxy traffic on this machine's IPv4 loopback.
set "SERVER_API_BASE_URL=http://127.0.0.1:18437"
if defined AEROONE_ALLOW_HOST (
  call .\node_modules\.bin\next.cmd start -H 0.0.0.0 -p 29501
) else (
  call .\node_modules\.bin\next.cmd start -H 127.0.0.1 -p 29501
)
exit /b %errorlevel%
