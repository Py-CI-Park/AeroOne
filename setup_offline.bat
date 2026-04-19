@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
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
if /I "%~1"=="--dry-run" set "DRY_RUN=1"
if /I "%~1"=="--no-pause" set "NO_PAUSE=1"
if /I "%~1"=="--help" goto :help
if /I "%~2"=="--no-pause" set "NO_PAUSE=1"

if defined DRY_RUN (
  echo [DRY-RUN] offline wheelhouse expected at %WHEEL_DIR%
  echo [DRY-RUN] backend env will be written to %BACKEND_ENV%
  echo [DRY-RUN] frontend env will be written to %FRONTEND_ENV%
  echo [DRY-RUN] backend venv will be created at %BACKEND_VENV%
  echo [DRY-RUN] backend migration and seed will run
  echo [DRY-RUN] frontend production build will run
  goto :success
)

if not exist "%WHEEL_DIR%" (
  echo [ERROR] offline wheelhouse not found: %WHEEL_DIR%
  goto :fail
)

for /f "delims=" %%S in ('powershell -NoLogo -NoProfile -Command "$bytes=[byte[]]::new(32); [Security.Cryptography.RandomNumberGenerator]::Fill($bytes); [BitConverter]::ToString($bytes).Replace('-','').ToLowerInvariant()"') do set "JWT_SECRET_KEY=%%S"
for /f "delims=" %%S in ('powershell -NoLogo -NoProfile -Command "$bytes=[byte[]]::new(24); [Security.Cryptography.RandomNumberGenerator]::Fill($bytes); [BitConverter]::ToString($bytes).Replace('-','').ToLowerInvariant()"') do set "ADMIN_PASSWORD=%%S"
if not defined JWT_SECRET_KEY goto :fail
if not defined ADMIN_PASSWORD goto :fail

if exist "%BACKEND_ENV%" copy /y "%BACKEND_ENV%" "%BACKEND_ENV%.bak" >nul
>"%BACKEND_ENV%" echo APP_ENV=development
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
>>"%BACKEND_ENV%" echo NEWSLETTER_IMPORT_ROOT_CONTAINER=%ROOT_FWD%/Newsletter/output
>>"%BACKEND_ENV%" echo STORAGE_ROOT=%ROOT_FWD%/storage
>>"%BACKEND_ENV%" echo THUMBNAILS_DIR_NAME=thumbnails
>>"%BACKEND_ENV%" echo ATTACHMENTS_DIR_NAME=attachments
>>"%BACKEND_ENV%" echo MARKDOWN_DIR_NAME=markdown
>>"%BACKEND_ENV%" echo CORS_ORIGINS=http://localhost:29501
>>"%BACKEND_ENV%" echo NEXT_PUBLIC_API_BASE_URL=http://localhost:18437
>>"%BACKEND_ENV%" echo SERVER_API_BASE_URL=http://localhost:18437

if exist "%FRONTEND_ENV%" copy /y "%FRONTEND_ENV%" "%FRONTEND_ENV%.bak" >nul
>"%FRONTEND_ENV%" echo NEXT_PUBLIC_API_BASE_URL=http://localhost:18437
>>"%FRONTEND_ENV%" echo SERVER_API_BASE_URL=http://localhost:18437
>>"%FRONTEND_ENV%" echo NEXT_PUBLIC_CSRF_COOKIE_NAME=csrf_token

if not exist "%BACKEND_VENV%\Scripts\python.exe" (
  py -3.12 -m venv "%BACKEND_VENV%" || py -3 -m venv "%BACKEND_VENV%" || python -m venv "%BACKEND_VENV%" || goto :fail
)

if not exist "%BACKEND_DIR%\data" mkdir "%BACKEND_DIR%\data"
if not exist "%ROOT%\Newsletter\output" mkdir "%ROOT%\Newsletter\output"

call "%BACKEND_VENV%\Scripts\activate.bat" || goto :fail
pushd "%BACKEND_DIR%"
call pip install --no-index --find-links "%WHEEL_DIR%" -r requirements-dev.txt || goto :fail_from_backend
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
call npm run build || goto :fail_from_frontend
popd

echo [OK] setup_offline.bat completed successfully.
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

:help
echo Usage: setup_offline.bat [--dry-run] [--no-pause]
echo.
echo Installs the packaged offline bundle on an offline Windows PC.
echo - Rewrites backend\.env with offline-local absolute paths ^(backup: .env.bak^)
echo - Rewrites frontend\.env.local ^(backup: .env.local.bak^)
echo - Uses Python wheelhouse from offline_assets\python-wheels
echo - Runs Alembic migration or stamps an existing DB when tables already exist
echo.
echo Use --no-pause when launching from an existing terminal and you do not want the window to wait at the end.
exit /b 0
