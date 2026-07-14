@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
REM ==========================================================================
REM AeroOne Leantime co-deploy stack — day-to-day START (portable PHP+MariaDB).
REM Starts MariaDB (if not already up) and the Leantime PHP web server.
REM Run setup-leantime-stack.bat once before the first start.
REM ==========================================================================

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
if not defined LEANTIME_DB_PORT set "LEANTIME_DB_PORT=3307"
if not defined LEANTIME_PORT set "LEANTIME_PORT=8081"
if not defined LEANTIME_DB_PASSWORD set "LEANTIME_DB_PASSWORD=lean_local_pw"

set "PHP=%ROOT%\php\php.exe"
set "PHPINI=%ROOT%\php\php.ini"
set "MARIADB=%ROOT%\mariadb\bin"
set "DATA=%ROOT%\data"

if not exist "%DATA%\mysql" (
  echo [LEANTIME][ERROR] stack not set up yet. Run setup-leantime-stack.bat first.
  exit /b 1
)
if not exist "%PHPINI%" (
  echo [LEANTIME][ERROR] php.ini missing. Run setup-leantime-stack.bat first.
  exit /b 1
)

netstat -ano | findstr :%LEANTIME_DB_PORT% | findstr LISTENING >nul 2>&1
if errorlevel 1 (
  echo [LEANTIME][INFO ] starting MariaDB on 127.0.0.1:%LEANTIME_DB_PORT% ...
  start "aeroone-leantime-mariadbd" "%MARIADB%\mariadbd.exe" --datadir="%DATA%" --port=%LEANTIME_DB_PORT% --skip-name-resolve --bind-address=127.0.0.1
  call :wait_tcp %LEANTIME_DB_PORT% 30
  if errorlevel 1 (
    echo [LEANTIME][ERROR] MariaDB did not start within 30s.
    exit /b 1
  )
) else (
  echo [LEANTIME][INFO ] MariaDB already running on %LEANTIME_DB_PORT%.
)

netstat -ano | findstr :%LEANTIME_PORT% | findstr LISTENING >nul 2>&1
if errorlevel 1 (
  echo [LEANTIME][INFO ] starting Leantime web on 0.0.0.0:%LEANTIME_PORT% ...
  set "LEAN_DB_HOST=127.0.0.1"
  set "LEAN_DB_USER=leantime"
  set "LEAN_DB_PASSWORD=%LEANTIME_DB_PASSWORD%"
  set "LEAN_DB_DATABASE=leantime"
  set "LEAN_DB_PORT=%LEANTIME_DB_PORT%"
  set "LEAN_USE_REDIS=false"
  set "LEAN_NEWS_ENABLED=false"
  set "LEAN_APP_URL=http://localhost:%LEANTIME_PORT%"
  pushd "%ROOT%\leantime"
  start "aeroone-leantime-web" "%PHP%" -c "%PHPINI%" -S 0.0.0.0:%LEANTIME_PORT% -t public
  popd
  call :wait_http %LEANTIME_PORT% 40
  if errorlevel 1 (
    echo [LEANTIME][WARN ] Leantime web port %LEANTIME_PORT% not ready within 40s ^(may still be booting^).
  )
) else (
  echo [LEANTIME][INFO ] Leantime web already running on %LEANTIME_PORT%.
)

echo [LEANTIME][READY] Leantime available at http://localhost:%LEANTIME_PORT%/
exit /b 0

:wait_tcp
set "WT_PORT=%~1"
powershell -NoLogo -NoProfile -Command "$p=%WT_PORT%;$t=%~2;for($i=0;$i -lt $t;$i++){try{$c=New-Object Net.Sockets.TcpClient;$c.Connect('127.0.0.1',$p);$c.Close();exit 0}catch{Start-Sleep 1}};exit 1"
exit /b %errorlevel%

:wait_http
set "WH_PORT=%~1"
powershell -NoLogo -NoProfile -Command "$u='http://127.0.0.1:%WH_PORT%/';$t=%~2;for($i=0;$i -lt $t;$i++){try{$r=Invoke-WebRequest -UseBasicParsing -MaximumRedirection 0 -TimeoutSec 3 $u; exit 0}catch{ if($_.Exception.Response){exit 0}; Start-Sleep 1}};exit 1"
exit /b %errorlevel%
