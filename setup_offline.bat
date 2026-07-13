@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "AEROONE_DRY_RUN_REQUESTED="
for %%A in (%*) do if /I "%%~A"=="--dry-run" set "AEROONE_DRY_RUN_REQUESTED=1"
if /I not "%AEROONE_MAINTENANCE_GATE_HELD%"=="1" if not defined AEROONE_DRY_RUN_REQUESTED (
  if "%~1"=="" (
    powershell -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%ROOT%\scripts\windows\invoke_with_maintenance_gate.ps1" -WorkspaceRoot "%ROOT%" -BatchPath "%~f0"
  ) else (
    powershell -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%ROOT%\scripts\windows\invoke_with_maintenance_gate.ps1" -WorkspaceRoot "%ROOT%" -BatchPath "%~f0" -RawBatchArguments "%*"
  )
  exit /b !errorlevel!
)
set "AEROONE_MAINTENANCE_GATE_HELD="
set "ROOT_FWD=%ROOT:\=/%"
set "BACKEND_DIR=%ROOT%\backend"
set "FRONTEND_DIR=%ROOT%\frontend"
set "BACKEND_DIR_FWD=%BACKEND_DIR:\=/%"
set "BACKEND_ENV=%BACKEND_DIR%\.env"
set "FRONTEND_ENV=%FRONTEND_DIR%\.env.local"
set "BACKEND_VENV=%BACKEND_DIR%\.venv"
set "WHEEL_DIR=%ROOT%\offline_assets\python-wheels"
set "DRY_RUN="
set "NO_PAUSE="
set "LOCAL_ONLY="
set "ALLOW_HOST=%AEROONE_ALLOW_HOST%"

:parse_args
if "%~1"=="" goto :parse_done
if /I "%~1"=="--dry-run" (set "DRY_RUN=1" & shift & goto :parse_args)
if /I "%~1"=="--no-pause" (set "NO_PAUSE=1" & shift & goto :parse_args)
if /I "%~1"=="--local" (set "LOCAL_ONLY=1" & shift & goto :parse_args)
if /I "%~1"=="--help" goto :help
if /I "%~1"=="--allow-host" (shift & goto :capture_host)
echo %~1 | findstr /B /I /C:"--allow-host=" >nul
if not errorlevel 1 (
  for /F "tokens=2 delims==" %%V in ("%~1") do set "ALLOW_HOST=%%V"
  shift
  goto :parse_args
)
shift
goto :parse_args

:capture_host
if "%~1"=="" (
  echo [ERROR] --allow-host requires a host argument ^(IP or hostname^).
  exit /b 1
)
set "ALLOW_HOST=%~1"
shift
goto :parse_args

:parse_done

REM 기본 동작 = LAN(IP). 옵션이 없으면 LAN IPv4 를 자동 감지해 .env 를 LAN 기준으로 쓴다.
REM 이 PC 에서만 쓰려면 --local, 특정 IP 는 --allow-host=<IP>. 감지 실패 시 localhost 폴백.
if not defined LOCAL_ONLY if not defined ALLOW_HOST set "ALLOW_HOST=auto"
if /I "%ALLOW_HOST%"=="auto" call :resolve_auto_host

if defined ALLOW_HOST (
  set "EFFECTIVE_BACKEND_BASE=http://%ALLOW_HOST%:18437"
  set "EFFECTIVE_CORS=http://localhost:29501,http://%ALLOW_HOST%:29501"
) else (
  set "EFFECTIVE_BACKEND_BASE=http://localhost:18437"
  set "EFFECTIVE_CORS=http://localhost:29501"
)

if "%DRY_RUN%"=="1" goto :run_dry_branch
goto :install_real

:run_dry_branch
echo [DRY-RUN] 미리보기 모드 - 실제 설치는 하지 않습니다. 설치하려면 --dry-run 옵션을 빼고 다시 실행하세요.
echo [DRY-RUN] offline wheelhouse expected at %WHEEL_DIR%
echo [DRY-RUN] backend env will be written to %BACKEND_ENV%
echo [DRY-RUN] frontend env will be written to %FRONTEND_ENV%
echo [DRY-RUN] backend venv will be created at %BACKEND_VENV%
echo [DRY-RUN] backend migration and seed will run
echo [DRY-RUN] frontend production build: skip if .next prebuild exists, else npm run build (1.0.6+)
if not defined ALLOW_HOST goto :dry_loopback
echo [DRY-RUN] LAN host = %ALLOW_HOST%
echo [DRY-RUN] CORS_ORIGINS = %EFFECTIVE_CORS%
echo [DRY-RUN] NEXT_PUBLIC_API_BASE_URL = %EFFECTIVE_BACKEND_BASE%
goto :success

:dry_loopback
echo [DRY-RUN] LAN host = ^(localhost only: --local or LAN IPv4 not detected^)
goto :success

:install_real
echo ==================================================
echo [INSTALL] setup_offline.bat 실제 설치를 시작합니다.
echo           미리보기만 원하시면 Ctrl+C 로 중단하고 --dry-run 옵션을 추가해 다시 실행하세요.
echo ==================================================
echo [PRE  ] Python / Node / npm 사전 요건 점검
where py >nul 2>&1
set "HAVE_PY=%ERRORLEVEL%"
where python >nul 2>&1
set "HAVE_PYTHON=%ERRORLEVEL%"
if not "%HAVE_PY%"=="0" if not "%HAVE_PYTHON%"=="0" (
  echo [ERROR] Python ^(py 또는 python^)을 찾을 수 없습니다.
  echo [INFO ] 폐쇄망 PC에 Python 3.12 가 설치되어 있어야 합니다.
  echo [INFO ] ZIP 안에 동봉된 설치 파일이 있다면 먼저 실행하세요:
  echo [INFO ]   offline_assets\installers\python-*.exe
  goto :fail
)
where node >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Node.js 를 찾을 수 없습니다.
  echo [INFO ] 폐쇄망 PC에 Node.js LTS 가 설치되어 있어야 합니다.
  echo [INFO ] ZIP 안에 동봉된 설치 파일이 있다면 먼저 실행하세요:
  echo [INFO ]   offline_assets\installers\node-*.msi
  goto :fail
)
where npm >nul 2>&1
if errorlevel 1 (
  echo [ERROR] npm 을 찾을 수 없습니다.
  echo [INFO ] Node.js 재설치 또는 PATH 점검 후 다시 실행하세요.
  goto :fail
)
echo [OK   ] 사전 요건 점검 통과

if not exist "%WHEEL_DIR%" (
  echo [ERROR] offline wheelhouse not found: %WHEEL_DIR%
  goto :fail
)

for /f "delims=" %%S in ('powershell -NoLogo -NoProfile -Command "$bytes=[byte[]]::new(32); $rng=[Security.Cryptography.RandomNumberGenerator]::Create(); try{$rng.GetBytes($bytes)}finally{$rng.Dispose()}; [BitConverter]::ToString($bytes).Replace('-','').ToLowerInvariant()"') do set "JWT_SECRET_KEY=%%S"
for /f "delims=" %%S in ('powershell -NoLogo -NoProfile -Command "$bytes=[byte[]]::new(24); $rng=[Security.Cryptography.RandomNumberGenerator]::Create(); try{$rng.GetBytes($bytes)}finally{$rng.Dispose()}; [BitConverter]::ToString($bytes).Replace('-','').ToLowerInvariant()"') do set "ADMIN_PASSWORD=%%S"
if not defined JWT_SECRET_KEY goto :fail
if not defined ADMIN_PASSWORD goto :fail

if exist "%BACKEND_ENV%" copy /y "%BACKEND_ENV%" "%BACKEND_ENV%.bak" >nul
>"%BACKEND_ENV%" echo APP_ENV=closed_network
>>"%BACKEND_ENV%" echo APP_NAME=AeroOne Newsletter Platform
>>"%BACKEND_ENV%" echo BACKEND_PORT=18437
>>"%BACKEND_ENV%" echo FRONTEND_PORT=29501
>>"%BACKEND_ENV%" echo DATABASE_URL=sqlite:///%BACKEND_DIR_FWD%/data/aeroone.db
>>"%BACKEND_ENV%" echo JWT_SECRET_KEY=%JWT_SECRET_KEY%
>>"%BACKEND_ENV%" echo ADMIN_SESSION_COOKIE_NAME=admin_session
>>"%BACKEND_ENV%" echo ACCESS_TOKEN_TTL_MINUTES=30
>>"%BACKEND_ENV%" echo ADMIN_USERNAME=admin
>>"%BACKEND_ENV%" echo ADMIN_PASSWORD=%ADMIN_PASSWORD%
>>"%BACKEND_ENV%" echo CSRF_COOKIE_NAME=csrf_token
>>"%BACKEND_ENV%" echo NEWSLETTER_IMPORT_ROOT_CONTAINER=%ROOT_FWD%/_database/newsletter
>>"%BACKEND_ENV%" echo CIVIL_AIRCRAFT_ROOT=%ROOT_FWD%/_database/civil_aircraft
>>"%BACKEND_ENV%" echo DOCUMENT_ROOT=%ROOT_FWD%/_database/document
>>"%BACKEND_ENV%" echo NSA_ROOT=%ROOT_FWD%/_database/nsa
>>"%BACKEND_ENV%" echo STORAGE_ROOT=%ROOT_FWD%/storage
>>"%BACKEND_ENV%" echo THUMBNAILS_DIR_NAME=thumbnails
>>"%BACKEND_ENV%" echo ATTACHMENTS_DIR_NAME=attachments
>>"%BACKEND_ENV%" echo MARKDOWN_DIR_NAME=markdown
>>"%BACKEND_ENV%" echo CORS_ORIGINS=%EFFECTIVE_CORS%
>>"%BACKEND_ENV%" echo NEXT_PUBLIC_API_BASE_URL=%EFFECTIVE_BACKEND_BASE%
>>"%BACKEND_ENV%" echo SERVER_API_BASE_URL=http://127.0.0.1:18437
>>"%BACKEND_ENV%" echo AI_FEATURES_ENABLED=true
>>"%BACKEND_ENV%" echo OLLAMA_BASE_URL=http://127.0.0.1:11434
>>"%BACKEND_ENV%" echo OLLAMA_DEFAULT_MODEL=gemma4:12b
if defined ALLOW_HOST >>"%BACKEND_ENV%" echo LAN_HOST=%ALLOW_HOST%

if exist "%FRONTEND_ENV%" copy /y "%FRONTEND_ENV%" "%FRONTEND_ENV%.bak" >nul
>"%FRONTEND_ENV%" echo NEXT_PUBLIC_API_BASE_URL=%EFFECTIVE_BACKEND_BASE%
>>"%FRONTEND_ENV%" echo SERVER_API_BASE_URL=http://127.0.0.1:18437
>>"%FRONTEND_ENV%" echo NEXT_PUBLIC_CSRF_COOKIE_NAME=csrf_token

if not exist "%BACKEND_VENV%\Scripts\python.exe" (
  py -3.12 -m venv "%BACKEND_VENV%" || py -3 -m venv "%BACKEND_VENV%" || python -m venv "%BACKEND_VENV%" || goto :fail
)

if not exist "%BACKEND_DIR%\data" mkdir "%BACKEND_DIR%\data"
if not exist "%ROOT%\_database\newsletter" mkdir "%ROOT%\_database\newsletter"
if not exist "%ROOT%\_database\civil_aircraft" mkdir "%ROOT%\_database\civil_aircraft"
if not exist "%ROOT%\_database\document" mkdir "%ROOT%\_database\document"
if not exist "%ROOT%\_database\nsa" mkdir "%ROOT%\_database\nsa"

call "%BACKEND_VENV%\Scripts\activate.bat" || goto :fail
pushd "%BACKEND_DIR%"
call pip install --no-index --find-links "%WHEEL_DIR%" -r requirements.txt || goto :fail_from_backend
set "PYTHONPATH=."
call python scripts\ensure_db_state.py data\aeroone.db
set "MIGRATION_MODE=%ERRORLEVEL%"
if "%MIGRATION_MODE%"=="3" (
  echo [INFO] Existing database detected without Alembic metadata. Stamping head.
  call alembic stamp head || goto :fail_from_backend
) else (
  call alembic upgrade head || goto :fail_from_backend
)
call python scripts\seed.py || goto :fail_from_backend
popd

pushd "%FRONTEND_DIR%"
if not exist "node_modules" (
  echo [ERROR] frontend\node_modules is missing. Recreate the offline package on the online PC.
  goto :fail_from_frontend
)
if exist ".next\BUILD_ID" (
  echo [INFO] frontend\.next prebuild detected — skipping npm run build on offline PC
) else (
  echo [WARN] frontend\.next prebuild not found. Falling back to npm run build on offline PC.
  echo [WARN] If webpack fails here, repackage the ZIP on the online PC with the latest offline_package.bat.
  call npm run build || goto :fail_from_frontend
)
popd

echo.
echo ==================================================
echo [OK] setup_offline.bat 완료
echo ==================================================
echo 다음 단계:
echo   1. start_offline.bat 실행
echo   2. backend\.env 에서 ADMIN_PASSWORD 확인 ^(랜덤 생성됨^)
echo   3. 브라우저: http://localhost:29501/newsletters
echo   4. 관리자 로그인: http://localhost:29501/login
echo.
echo [DATA] _database/newsletter 폴더에 newsletter_YYYYMMDD.html 원본을 추가한 뒤
echo        관리자 페이지의 Import / Sync 버튼으로 동기화하세요.
echo [DATA] _database/document 폴더에 HTML 문서를 넣으면 Document 탭에서 바로 보입니다
echo        ^(하위 폴더로 분류하면 폴더 트리로 구분, 재시작 불필요^).
echo [DATA] _database/nsa 폴더의 HTML 은 NSA 탭 잠금 해제 뒤 표시됩니다.
echo ==================================================
goto :success

:fail_from_backend
popd
goto :fail

:fail_from_frontend
popd
goto :fail

:fail
echo [FAILED] setup_offline.bat did not complete successfully.
if not defined NO_PAUSE pause
exit /b 1

:success
if not defined NO_PAUSE pause
exit /b 0

:resolve_auto_host
echo [INFO ] Detecting this PC's LAN IPv4 for LAN access...
set "ALLOW_HOST="
for /f "usebackq delims=" %%I in (`powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\windows\detect_lan_ip.ps1"`) do set "ALLOW_HOST=%%I"
if not defined ALLOW_HOST (
  echo [WARN ] LAN IPv4 not detected. Writing localhost-only .env. Use --allow-host=^<IP^> to force.
  goto :eof
)
echo [INFO ] LAN IPv4 = !ALLOW_HOST!
goto :eof

:help
echo Usage: setup_offline.bat [--dry-run] [--no-pause] [--local] [--allow-host=^<host^>]
echo.
echo Installs the packaged offline bundle on an offline Windows PC.
echo - Rewrites backend\.env with offline-local absolute paths ^(backup: .env.bak^)
echo - Rewrites frontend\.env.local ^(backup: .env.local.bak^)
echo - Uses Python wheelhouse from offline_assets\python-wheels
echo - Runs Alembic migration or stamps an existing DB when tables already exist
echo.
echo By default writes a LAN .env: this PC's LAN IPv4 is auto-detected and put into
echo CORS_ORIGINS / NEXT_PUBLIC_API_BASE_URL. If no LAN IPv4 is found it falls back to localhost.
echo.
echo --local             Write a localhost-only .env ^(no LAN exposure^).
echo --allow-host=^<host^>  Force a specific LAN host/IP instead of auto-detection.
echo                     Example: --allow-host=192.168.1.10
echo --allow-host=auto   Explicitly auto-detect this PC's LAN IPv4 ^(same as default^).
echo                     Environment fallback: AEROONE_ALLOW_HOST.
echo.
echo Use --no-pause when launching from an existing terminal and you do not want the window to wait at the end.
exit /b 0
