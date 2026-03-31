@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
set "FRONTEND_DIR=%ROOT%\frontend"

cd /d "%FRONTEND_DIR%" || exit /b 1
call npx next start -H 0.0.0.0 -p 29501
exit /b %errorlevel%
