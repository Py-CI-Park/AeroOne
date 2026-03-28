@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "DRY_RUN="
if /I "%~1"=="--dry-run" set "DRY_RUN=1"
if /I "%~1"=="--help" goto :help

set "BACKEND_DIR=%ROOT%\backend"
set "FRONTEND_DIR=%ROOT%\frontend"
set "BACKEND_ENV=%BACKEND_DIR%\.env"
set "FRONTEND_ENV=%FRONTEND_DIR%\.env.local"
set "BACKEND_VENV=%BACKEND_DIR%\.venv"

if not exist "%BACKEND_DIR%" (
  echo [ERROR] backend directory not found: %BACKEND_DIR%
  exit /b 1
)
if not exist "%FRONTEND_DIR%" (
  echo [ERROR] frontend directory not found: %FRONTEND_DIR%
  exit /b 1
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
    if errorlevel 1 exit /b 1
  )
)

if defined DRY_RUN (
  echo [DRY-RUN] install backend requirements
  echo [DRY-RUN] run alembic upgrade head
  echo [DRY-RUN] run seed script
  echo [DRY-RUN] npm install in frontend
  echo [DRY-RUN] done
  exit /b 0
)

call "%BACKEND_VENV%\Scripts\activate.bat"
if errorlevel 1 exit /b 1
pushd "%BACKEND_DIR%"
pip install -r requirements-dev.txt || exit /b 1
set "PYTHONPATH=."
alembic upgrade head || exit /b 1
python scripts\seed.py || exit /b 1
popd

pushd "%FRONTEND_DIR%"
call npm install || exit /b 1
popd

echo [OK] setup.bat completed successfully.
exit /b 0

:help
echo Usage: setup.bat [--dry-run]
echo.
echo Installs backend/frontend dependencies for an online Windows PC.
echo - Creates backend\.env from .env.example if missing
echo - Creates frontend\.env.local if missing
echo - Creates backend\.venv and installs Python packages
echo - Runs Alembic migration and seed script
echo - Runs npm install for frontend
exit /b 0
