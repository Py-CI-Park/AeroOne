@echo off
setlocal EnableExtensions
chcp 65001 >nul

REM AeroOne LAN inbound firewall helper.
REM 폐쇄망 LAN 의 다른 PC 가 이 PC 의 backend(18437)/frontend(29501)에 접속하려면
REM Windows 방화벽 인바운드 허용 규칙이 필요하다. 같은 PC 에서 IP 로만 보는 경우는
REM 보통 필요 없다. start_offline.bat --allow-host=<IP> 와 짝으로 사용한다.

set "BACKEND_PORT=18437"
set "FRONTEND_PORT=29501"
set "RULE_BACKEND=AeroOne Backend %BACKEND_PORT%"
set "RULE_FRONTEND=AeroOne Frontend %FRONTEND_PORT%"
set "ACTION=add"

if /I "%~1"=="--help" goto :help
if /I "%~1"=="-h" goto :help
if /I "%~1"=="/?" goto :help
if /I "%~1"=="--remove" set "ACTION=remove"
if /I "%~1"=="/remove" set "ACTION=remove"

REM netsh advfirewall 은 관리자 권한이 필요하다. net session 으로 권한을 확인한다.
net session >nul 2>&1
if errorlevel 1 (
  echo [ERROR] 관리자 권한이 필요합니다. 이 스크립트를 "관리자 권한으로 실행" 하세요.
  echo [ERROR] Administrator privileges required. Re-run this script as Administrator.
  exit /b 1
)

if /I "%ACTION%"=="remove" goto :remove

echo [INFO ] Adding inbound allow rules ^(profile=any, remoteip=LocalSubnet only^).
netsh advfirewall firewall add rule name="%RULE_BACKEND%" dir=in action=allow protocol=TCP localport=%BACKEND_PORT% profile=any remoteip=LocalSubnet
if errorlevel 1 goto :fail
netsh advfirewall firewall add rule name="%RULE_FRONTEND%" dir=in action=allow protocol=TCP localport=%FRONTEND_PORT% profile=any remoteip=LocalSubnet
if errorlevel 1 goto :fail
echo [OK   ] LAN inbound allowed for %BACKEND_PORT% / %FRONTEND_PORT%.
echo [OK   ] Other PCs on the same subnet can now reach http://^<this-PC-IP^>:%FRONTEND_PORT%/
echo [INFO ] To revert: scripts\allow_lan_firewall.cmd --remove
exit /b 0

:remove
echo [INFO ] Removing AeroOne inbound firewall rules.
netsh advfirewall firewall delete rule name="%RULE_BACKEND%" >nul 2>&1
netsh advfirewall firewall delete rule name="%RULE_FRONTEND%" >nul 2>&1
echo [OK   ] Removed AeroOne inbound rules ^(if they existed^).
exit /b 0

:fail
echo [FAILED] netsh could not add the firewall rule.
echo [INFO  ] Re-run as Administrator and verify Windows Firewall is available.
exit /b 1

:help
echo Usage: allow_lan_firewall.cmd [--remove] [--help]
echo.
echo Adds Windows Firewall inbound allow rules so other PCs on the same closed LAN can
echo reach the AeroOne backend ^(%BACKEND_PORT%^) and frontend ^(%FRONTEND_PORT%^).
echo Scope: profile=any, remoteip=LocalSubnet ^(local subnet only; not exposed beyond LAN^).
echo Must be run as Administrator. Pair with: start_offline.bat --allow-host=^<IP^>.
echo.
echo   --remove   Delete the two AeroOne inbound rules created by this script.
echo   --help     Show this help.
exit /b 0
