@echo off
setlocal EnableExtensions
chcp 65001 >nul

REM Leantime LAN inbound firewall helper.
REM 폐쇄망 LAN 의 다른 PC 가 이 PC 의 Leantime(8081 기본)에 접속하려면 Windows
REM 방화벽 인바운드 허용 규칙이 필요하다. 같은 PC 에서만 접속하는 경우는 보통
REM 필요 없다. AeroOne 의 scripts\allow_lan_firewall.cmd(18437/29501 전용)와는
REM 별개 규칙이다. MariaDB(3307)는 이 스크립트로 열지 않는다(로컬 전용 유지).
REM
REM 로그 계약: [LEANTIME][INFO|OK|ERROR|FAILED] message
REM 종료 코드: 0 = 성공(규칙 추가/제거) / 1 = 관리자 권한 없음 또는 netsh 실패.

if not defined LEANTIME_PORT set "LEANTIME_PORT=8081"
set "RULE_LEANTIME=AeroOne Leantime %LEANTIME_PORT%"
set "ACTION=add"

if /I "%~1"=="--help" goto :help
if /I "%~1"=="-h" goto :help
if /I "%~1"=="/?" goto :help
if /I "%~1"=="--remove" set "ACTION=remove"
if /I "%~1"=="/remove" set "ACTION=remove"

REM netsh advfirewall 은 관리자 권한이 필요하다. net session 으로 권한을 확인한다.
net session >nul 2>&1
if errorlevel 1 (
  echo [LEANTIME][ERROR] 관리자 권한이 필요합니다. 이 스크립트를 "관리자 권한으로 실행" 하세요.
  echo [LEANTIME][ERROR] Administrator privileges required. Re-run this script as Administrator.
  exit /b 1
)

if /I "%ACTION%"=="remove" goto :remove

echo [LEANTIME][INFO ] Adding inbound allow rule ^(profile=any, remoteip=LocalSubnet only^).
netsh advfirewall firewall add rule name="%RULE_LEANTIME%" dir=in action=allow protocol=TCP localport=%LEANTIME_PORT% profile=any remoteip=LocalSubnet
if errorlevel 1 goto :fail
echo [LEANTIME][OK   ] LAN inbound allowed for %LEANTIME_PORT%.
echo [LEANTIME][OK   ] Other PCs on the same subnet can now reach http://^<this-PC-IP^>:%LEANTIME_PORT%/
echo [LEANTIME][INFO ] MariaDB ^(3307^) is NOT opened by this script ^(stays local-only^).
echo [LEANTIME][INFO ] To revert: scripts\leantime\allow-leantime-firewall.cmd --remove
exit /b 0

:remove
echo [LEANTIME][INFO ] Removing Leantime inbound firewall rule.
netsh advfirewall firewall delete rule name="%RULE_LEANTIME%" >nul 2>&1
echo [LEANTIME][OK   ] Removed Leantime inbound rule ^(if it existed^).
exit /b 0

:fail
echo [LEANTIME][FAILED] netsh could not add the firewall rule.
echo [LEANTIME][INFO  ] Re-run as Administrator and verify Windows Firewall is available.
exit /b 1

:help
echo Usage: allow-leantime-firewall.cmd [--remove] [--help]
echo.
echo Adds a Windows Firewall inbound allow rule so other PCs on the same closed
echo LAN can reach the Leantime co-deploy stack ^(default port %LEANTIME_PORT%; override with LEANTIME_PORT^).
echo Scope: profile=any, remoteip=LocalSubnet ^(local subnet only; not exposed beyond LAN^).
echo Must be run as Administrator. MariaDB ^(3307^) is never opened by this script.
echo.
echo   --remove   Delete the Leantime inbound rule created by this script.
echo   --help     Show this help.
exit /b 0
