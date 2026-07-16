@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
REM Delayed expansion stays OFF: passwords/values may contain '!' and cmd would
REM silently strip it (documented default DB/admin passwords can end with '!').
REM ==========================================================================
REM AeroOne Leantime co-deploy stack — day-to-day START (portable PHP+MariaDB).
REM Starts MariaDB (if not already up) and the Leantime PHP web server.
REM Run setup-leantime-stack.bat once before the first start.
REM
REM LAN access: the web server binds 0.0.0.0 and LEAN_APP_URL defaults to the
REM auto-detected LAN IPv4 (fallback localhost) so pages opened from another PC
REM do not reference the visitor's own localhost. Override with LEANTIME_APP_URL.
REM ==========================================================================

REM 더블클릭(탐색기) 실행 감지 — 오류/완료 시 창이 즉시 닫히지 않게 pause 한다.
REM 자동화에서 pause 를 막으려면 AEROONE_LT_NO_PAUSE=1 을 설정한다.
set "AEROONE_LT_INTERACTIVE="
echo "%cmdcmdline%" | find /i "%~nx0" >nul && set "AEROONE_LT_INTERACTIVE=1"
if defined AEROONE_LT_NO_PAUSE set "AEROONE_LT_INTERACTIVE="

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
  goto :fail
)
if not exist "%PHPINI%" (
  echo [LEANTIME][ERROR] php.ini missing. Run setup-leantime-stack.bat first.
  goto :fail
)

REM LEAN_APP_URL 결정: 명시 override > LAN IPv4 자동 감지 > localhost 폴백.
REM localhost 로 두면 다른 PC 브라우저가 자기 자신을 가리켜 자산/리다이렉트가 깨진다.
if defined LEANTIME_APP_URL (
  set "LT_APP_URL=%LEANTIME_APP_URL%"
  goto :app_url_done
)
set "LT_LAN_IP="
for /f "usebackq delims=" %%I in (`powershell -NoLogo -NoProfile -Command "$ErrorActionPreference='SilentlyContinue';$ip=$null;$gw=Get-NetIPConfiguration|Where-Object{$_.NetAdapter -and $_.NetAdapter.Status -eq 'Up' -and $_.IPv4DefaultGateway}|Select-Object -First 1;if($gw -and $gw.IPv4Address){$ip=@($gw.IPv4Address)[0].IPAddress};if(-not $ip){$c=Get-NetIPAddress -AddressFamily IPv4|Where-Object{$_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' -and ($_.IPAddress -like '192.168.*' -or $_.IPAddress -like '10.*' -or $_.IPAddress -match '^172\.(1[6-9]|2[0-9]|3[0-1])\.')}|Select-Object -First 1;if($c){$ip=$c.IPAddress}};if($ip){Write-Output $ip}"`) do set "LT_LAN_IP=%%I"
if defined LT_LAN_IP (
  set "LT_APP_URL=http://%LT_LAN_IP%:%LEANTIME_PORT%"
) else (
  set "LT_APP_URL=http://localhost:%LEANTIME_PORT%"
)
:app_url_done

netstat -ano | findstr /c:":%LEANTIME_DB_PORT% " | findstr LISTENING >nul 2>&1
if errorlevel 1 (
  echo [LEANTIME][INFO ] starting MariaDB on 127.0.0.1:%LEANTIME_DB_PORT% ...
  start "aeroone-leantime-mariadbd" "%MARIADB%\mariadbd.exe" --datadir="%DATA%" --port=%LEANTIME_DB_PORT% --skip-name-resolve --bind-address=127.0.0.1
  call :wait_tcp %LEANTIME_DB_PORT% 30
  if errorlevel 1 (
    echo [LEANTIME][ERROR] MariaDB did not start within 30s.
    goto :fail
  )
) else (
  echo [LEANTIME][INFO ] MariaDB already running on %LEANTIME_DB_PORT%.
)

netstat -ano | findstr /c:":%LEANTIME_PORT% " | findstr LISTENING >nul 2>&1
if errorlevel 1 (
  echo [LEANTIME][INFO ] starting Leantime web on 0.0.0.0:%LEANTIME_PORT% ^(APP_URL %LT_APP_URL%^) ...
  set "LEAN_DB_HOST=127.0.0.1"
  set "LEAN_DB_USER=leantime"
  set "LEAN_DB_PASSWORD=%LEANTIME_DB_PASSWORD%"
  set "LEAN_DB_DATABASE=leantime"
  set "LEAN_DB_PORT=%LEANTIME_DB_PORT%"
  set "LEAN_USE_REDIS=false"
  set "LEAN_NEWS_ENABLED=false"
  set "LEAN_APP_URL=%LT_APP_URL%"
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

echo [LEANTIME][READY] Leantime available at %LT_APP_URL%/ ^(this PC: http://localhost:%LEANTIME_PORT%/^)
if defined AEROONE_LT_INTERACTIVE pause
exit /b 0

:fail
echo [LEANTIME][ERROR] start did not complete. Review the messages above.
if defined AEROONE_LT_INTERACTIVE pause
exit /b 1

:wait_tcp
set "WT_PORT=%~1"
powershell -NoLogo -NoProfile -Command "$p=%WT_PORT%;$t=%~2;for($i=0;$i -lt $t;$i++){try{$c=New-Object Net.Sockets.TcpClient;$c.Connect('127.0.0.1',$p);$c.Close();exit 0}catch{Start-Sleep 1}};exit 1"
exit /b %errorlevel%

:wait_http
REM 리다이렉트를 따라간 최종 응답(로그인 페이지 200)도 '기동됨'으로 본다.
REM HTTP 오류 응답(4xx/5xx)도 웹 서버 자체는 떠 있는 것이므로 ready 로 취급한다.
set "WH_PORT=%~1"
powershell -NoLogo -NoProfile -Command "$ErrorActionPreference='Stop';$u='http://127.0.0.1:%WH_PORT%/';$t=%~2;for($i=0;$i -lt $t;$i++){try{$null=Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 $u; exit 0}catch{ if($_.Exception.Response){exit 0}; Start-Sleep 1}};exit 1"
exit /b %errorlevel%
