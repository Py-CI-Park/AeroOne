@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ==========================================================================
REM AeroOne 폐쇄망 프로세스 정리 — 이전 실행이 남긴 backend/frontend 와, 그 백엔드가
REM 쥐고 있는 유지보수 게이트 홀더(hold_maintenance_gate.ps1 powershell)를 종료한다.
REM start_offline.bat 재실행이 게이트 경합으로 5분 대기 후 exit 98 로 끝나던 상황을
REM 한 번에 푼다. 창을 닫아도 백엔드 프로세스가 살아 게이트를 계속 쥐는 경우가 흔하다.
REM ==========================================================================

set "BACKEND_PORT=18437"
set "FRONTEND_PORT=29501"

echo [STOP ] AeroOne backend/frontend 창 종료...
taskkill /FI "WINDOWTITLE eq AeroOne Backend Offline*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq AeroOne Frontend Offline*" /T /F >nul 2>&1

echo [STOP ] 포트 %BACKEND_PORT%/%FRONTEND_PORT% 를 점유(LISTEN)한 프로세스 종료...
powershell -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "foreach ($p in %BACKEND_PORT%,%FRONTEND_PORT%) { Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue } }"

echo [STOP ] 남은 유지보수 게이트 홀더(powershell) 정리...
powershell -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process -Filter \"Name='powershell.exe'\" | Where-Object { $_.CommandLine -match 'hold_maintenance_gate|invoke_with_maintenance_gate' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

echo [STOP ] 확인: 포트 점유 상태
powershell -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "$busy = @(foreach ($p in %BACKEND_PORT%,%FRONTEND_PORT%) { if (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue) { $p } }); if ($busy) { Write-Host ('[WARN ] 아직 사용 중: ' + ($busy -join ', ') + ' (관리자 권한으로 재실행하거나 재부팅 필요)') } else { Write-Host '[OK   ] 두 포트 모두 해제됨. 이제 start_offline.bat 을 실행하면 됩니다.' }"

echo [STOP ] 완료.
if /I not "%~1"=="--no-pause" pause
exit /b 0
