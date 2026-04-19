@echo off
setlocal EnableExtensions

set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
set "FRONTEND_DIR=%ROOT%\frontend"

title AeroOne Frontend
chcp 65001 >nul
color 0B
echo ==================================================
echo [FRONTEND][BOOT] AeroOne Web UI
echo URL  : http://localhost:29501/
echo ROOT : %FRONTEND_DIR%
echo CMD  : scripts\start_frontend_dev.cmd
echo ==================================================
echo [FRONTEND][INFO] Starting Next.js development server...
echo.

call "%~dp0start_frontend_dev.cmd"
exit /b %errorlevel%
