@echo off
setlocal EnableExtensions
chcp 65001 >nul
REM ==========================================================================
REM AeroOne Leantime co-deploy stack — STOP.
REM Stops the Leantime PHP web server and the portable MariaDB started by this
REM stack, addressing them by the window titles the start script assigns so
REM unrelated php.exe / mariadbd.exe processes are not touched.
REM ==========================================================================
echo [LEANTIME][INFO ] stopping Leantime web ...
taskkill /F /FI "WINDOWTITLE eq aeroone-leantime-web*" >nul 2>&1
echo [LEANTIME][INFO ] stopping MariaDB ...
taskkill /F /FI "WINDOWTITLE eq aeroone-leantime-mariadbd*" >nul 2>&1
echo [LEANTIME][READY] Leantime stack stopped.
exit /b 0
