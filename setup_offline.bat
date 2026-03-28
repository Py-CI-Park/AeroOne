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
set "WHEEL_DIR=%ROOT%\offline_assets\python-wheels"

if defined DRY_RUN (
  echo [DRY-RUN] offline wheelhouse expected at %WHEEL_DIR%
  echo [DRY-RUN] backend env will be prepared at %BACKEND_ENV%
  echo [DRY-RUN] frontend env will be prepared at %FRONTEND_ENV%
  echo [DRY-RUN] backend venv will be created at %BACKEND_VENV%
  echo [DRY-RUN] backend migration and seed will run
  echo [DRY-RUN] frontend production build will run
  exit /b 0
)

if not exist "%WHEEL_DIR%" (
  echo [ERROR] offline wheelhouse not found: %WHEEL_DIR%
  exit /b 1
)

if not exist "%BACKEND_ENV%" copy "%ROOT%\.env.example" "%BACKEND_ENV%" >nul
if not exist "%FRONTEND_ENV%" (
  >"%FRONTEND_ENV%" echo NEXT_PUBLIC_API_BASE_URL=http://localhost:18437
  >>"%FRONTEND_ENV%" echo SERVER_API_BASE_URL=http://localhost:18437
)

if not exist "%BACKEND_VENV%\Scripts\python.exe" (
  py -3.12 -m venv "%BACKEND_VENV%" || py -3 -m venv "%BACKEND_VENV%" || python -m venv "%BACKEND_VENV%" || exit /b 1
)

call "%BACKEND_VENV%\Scripts\activate.bat" || exit /b 1
pushd "%BACKEND_DIR%"
pip install --no-index --find-links "%WHEEL_DIR%" -r requirements-dev.txt || exit /b 1
set "PYTHONPATH=."
alembic upgrade head || exit /b 1
python scripts\seed.py || exit /b 1
popd

pushd "%FRONTEND_DIR%"
if not exist "node_modules" (
  echo [ERROR] frontend\node_modules is missing. Recreate the offline package on the online PC.
  exit /b 1
)
call npm run build || exit /b 1
popd

echo [OK] setup_offline.bat completed successfully.
exit /b 0

:help
echo Usage: setup_offline.bat [--dry-run]
echo.
echo Installs the packaged offline bundle on an offline Windows PC.
exit /b 0
