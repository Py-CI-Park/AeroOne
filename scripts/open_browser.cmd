@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "HELPER=%SCRIPT_DIR%\windows\wait_for_services.ps1"

set "URL=%~1"
if "%URL%"=="" set "URL=http://localhost:29501/"

set "BACKEND_PORT=%~2"
if "%BACKEND_PORT%"=="" set "BACKEND_PORT=18437"

set "FRONTEND_PORT=%~3"
if "%FRONTEND_PORT%"=="" set "FRONTEND_PORT=29501"

set "BACKEND_TIMEOUT=%~4"
if "%BACKEND_TIMEOUT%"=="" set "BACKEND_TIMEOUT=20"

set "FRONTEND_TIMEOUT=%~5"
if "%FRONTEND_TIMEOUT%"=="" set "FRONTEND_TIMEOUT=60"

if not exist "%HELPER%" (
  echo [ERROR] readiness helper not found: %HELPER%
  exit /b 1
)

powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%HELPER%" ^
  -Url "%URL%" ^
  -BackendPort %BACKEND_PORT% ^
  -FrontendPort %FRONTEND_PORT% ^
  -BackendTimeoutSeconds %BACKEND_TIMEOUT% ^
  -FrontendTimeoutSeconds %FRONTEND_TIMEOUT%

exit /b %errorlevel%
