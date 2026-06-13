@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
set "FRONTEND_DIR=%ROOT%\frontend"
set "CLEAR_CACHE="

if /I "%~1"=="--clean" set "CLEAR_CACHE=1"

cd /d "%FRONTEND_DIR%" || exit /b 1

if defined CLEAR_CACHE (
  if exist ".next" (
    echo [FRONTEND][INFO] Clearing stale .next cache...
    rmdir /s /q ".next"
  )

  if exist ".turbo" (
    echo [FRONTEND][INFO] Clearing stale .turbo cache...
    rmdir /s /q ".turbo"
  )
)

REM Parent shell variables can leak from Docker/CI sessions and override .env.local.
REM Force the local Windows launcher to use the local backend endpoints.
set "NEXT_PUBLIC_API_BASE_URL=http://localhost:18437"
set "SERVER_API_BASE_URL=http://127.0.0.1:18437"
call npm run dev
exit /b %errorlevel%
