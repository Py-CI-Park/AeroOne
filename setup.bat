@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "DRY_RUN="
set "NO_PAUSE="
if /I "%~1"=="--dry-run" set "DRY_RUN=1"
if /I "%~1"=="--no-pause" set "NO_PAUSE=1"
if /I "%~1"=="--help" goto :help
if /I "%~2"=="--no-pause" set "NO_PAUSE=1"

set "BACKEND_DIR=%ROOT%\backend"
set "FRONTEND_DIR=%ROOT%\frontend"
set "BACKEND_ENV=%BACKEND_DIR%\.env"
set "FRONTEND_ENV=%FRONTEND_DIR%\.env.local"
set "BACKEND_VENV=%BACKEND_DIR%\.venv"

if not exist "%BACKEND_DIR%" (
  echo [ERROR] backend directory not found: %BACKEND_DIR%
  goto :fail
)
if not exist "%FRONTEND_DIR%" (
  echo [ERROR] frontend directory not found: %FRONTEND_DIR%
  goto :fail
)

if defined DRY_RUN (
  echo [DRY-RUN] copy .env.example to backend\.env if missing
) else (
  if not exist "%BACKEND_ENV%" copy "%ROOT%\.env.example" "%BACKEND_ENV%" >nul
)

if defined DRY_RUN (
  echo [DRY-RUN] create frontend\.env.local if missing
) else (
  if not exist "%FRONTEND_ENV%" (
    >"%FRONTEND_ENV%" echo NEXT_PUBLIC_API_BASE_URL=http://localhost:18437
    >>"%FRONTEND_ENV%" echo SERVER_API_BASE_URL=http://localhost:18437
  )
)

if defined DRY_RUN (
  echo [DRY-RUN] create venv at %BACKEND_VENV%
) else (
  if not exist "%BACKEND_VENV%\Scripts\python.exe" (
    py -3.12 -m venv "%BACKEND_VENV%" || py -3 -m venv "%BACKEND_VENV%" || python -m venv "%BACKEND_VENV%"
    if errorlevel 1 goto :fail
  )
)

if defined DRY_RUN (
  echo [DRY-RUN] install backend requirements
  echo [DRY-RUN] run alembic upgrade head
  echo [DRY-RUN] run seed script
  echo [DRY-RUN] npm install in frontend
  echo [DRY-RUN] done
  goto :success
)

call "%BACKEND_VENV%\Scripts\activate.bat"
if errorlevel 1 goto :fail
pushd "%BACKEND_DIR%"
pip install -r requirements-dev.txt || goto :fail_from_backend
set "PYTHONPATH=."
alembic upgrade head || goto :fail_from_backend
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
echo - Creates backend\.env from .env.example if missing
echo - Creates frontend\.env.local if missing
echo - Creates backend\.venv and installs Python packages
echo - Runs Alembic migration and seed script
echo - Runs npm install for frontend
echo.
echo Use --no-pause when launching from an existing terminal and you do not want the window to wait at the end.
exit /b 0
