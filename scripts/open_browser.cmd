@echo off
setlocal EnableExtensions

set "URL=%~1"
if "%URL%"=="" set "URL=http://localhost:29501/"

timeout /t 6 /nobreak >nul
start "" "%URL%"
exit /b 0
