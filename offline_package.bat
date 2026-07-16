@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0"
set "BUILDER=%ROOT%scripts\build_offline_package.ps1"

if /I "%~1"=="--help" (
  if not "%~2"=="" goto :invalid_args
  powershell -NoProfile -ExecutionPolicy Bypass -File "%BUILDER%" -Help
  exit /b !ERRORLEVEL!
)

if /I "%~1"=="--dry-run" (
  if not "%~2"=="" goto :invalid_args
  powershell -NoProfile -ExecutionPolicy Bypass -File "%BUILDER%" -Version 1.16.3 -DryRun
  exit /b !ERRORLEVEL!
)

if not "%~1"=="" goto :invalid_args

powershell -NoProfile -ExecutionPolicy Bypass -File "%BUILDER%" -Version 1.16.3
exit /b %ERRORLEVEL%

:invalid_args
echo [ERROR] Usage: offline_package.bat [--dry-run^|--help]
exit /b 2
