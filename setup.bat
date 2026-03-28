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
set "DRY_RUN="
set "NO_PAUSE="
if /I "%~1"=="--dry-run" set "DRY_RUN=1"
if /I "%~1"=="--no-pause" set "NO_PAUSE=1"
if /I "%~1"=="--help" goto :help
if /I "%~2"=="--no-pause" set "NO_PAUSE=1"

if not exist "%BACKEND_DIR%" (
  echo [ERROR] backend directory not found: %BACKEND_DIR%
  goto :fail
)
if not exist "%FRONTEND_DIR%" (
  echo [ERROR] frontend directory not found: %FRONTEND_DIR%
  goto :fail
)

if defined DRY_RUN (
  echo [DRY-RUN] backend env will be written to %BACKEND_ENV%
  echo [DRY-RUN] frontend env will be written to %FRONTEND_ENV%
  echo [DRY-RUN] create venv at %BACKEND_VENV%
  echo [DRY-RUN] install backend requirements
  echo [DRY-RUN] inspect existing database state and run Alembic upgrade or stamp
  echo [DRY-RUN] run seed script
  echo [DRY-RUN] npm install in frontend
  goto :success
)

if exist "%BACKEND_ENV%" copy /y "%BACKEND_ENV%" "%BACKEND_ENV%.bak" >nul
>"%BACKEND_ENV%" echo APP_ENV=development
>>"%BACKEND_ENV%" echo APP_NAME=AeroOne Newsletter Platform
>>"%BACKEND_ENV%" echo BACKEND_PORT=18437
>>"%BACKEND_ENV%" echo FRONTEND_PORT=29501
>>"%BACKEND_ENV%" echo DATABASE_URL=sqlite:///%BACKEND_DIR_FWD%/data/aeroone.db
>>"%BACKEND_ENV%" echo JWT_SECRET_KEY=change-me
>>"%BACKEND_ENV%" echo ADMIN_SESSION_COOKIE_NAME=admin_session
>>"%BACKEND_ENV%" echo ACCESS_TOKEN_TTL_MINUTES=30
>>"%BACKEND_ENV%" echo ADMIN_USERNAME=admin
>>"%BACKEND_ENV%" echo ADMIN_PASSWORD=change-me
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

if not exist "%BACKEND_VENV%\Scripts\python.exe" (
  py -3.12 -m venv "%BACKEND_VENV%" || py -3 -m venv "%BACKEND_VENV%" || python -m venv "%BACKEND_VENV%"
  if errorlevel 1 goto :fail
)

if not exist "%BACKEND_DIR%\data" mkdir "%BACKEND_DIR%\data"

call "%BACKEND_VENV%\Scripts\activate.bat"
if errorlevel 1 goto :fail
pushd "%BACKEND_DIR%"
pip install -r requirements-dev.txt || goto :fail_from_backend
set "PYTHONPATH=."
python scripts\ensure_db_state.py data\aeroone.db
set "MIGRATION_MODE=%ERRORLEVEL%"
if "%MIGRATION_MODE%"=="3" (
  echo [INFO] Existing database detected without Alembic metadata. Stamping head.
  alembic stamp head || goto :fail_from_backend
) else (
  alembic upgrade head || goto :fail_from_backend
)
python scripts\seed.py || goto :fail_from_backend
popd

pushd "%FRONTEND_DIR%"
call npm install || goto :fail_from_frontend
popd

echo [OK] setup.bat completed successfully.
goto :success

:fail_from_backend
popd
goto :fail

:fail_from_frontend
popd
goto :fail

:fail
echo [FAILED] setup.bat did not complete successfully.
if not defined NO_PAUSE pause
exit /b 1

:success
if not defined NO_PAUSE pause
exit /b 0

:help
echo Usage: setup.bat [--dry-run] [--no-pause]
echo.
echo Installs backend/frontend dependencies for an online Windows PC.
echo - Rewrites backend\.env with Windows-local absolute paths ^(backup: .env.bak^)
echo - Rewrites frontend\.env.local ^(backup: .env.local.bak^)
echo - Creates backend\.venv and installs Python packages
echo - Runs Alembic migration or stamps an existing DB when tables already exist
echo - Runs seed script and npm install for frontend
echo.
echo Use --no-pause when launching from an existing terminal and you do not want the window to wait at the end.
exit /b 0
