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

call npm run dev
exit /b %errorlevel%
