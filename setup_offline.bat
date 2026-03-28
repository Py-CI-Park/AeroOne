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
set "WHEEL_DIR=%ROOT%\offline_assets\python-wheels"

if defined DRY_RUN (
  echo [DRY-RUN] offline wheelhouse expected at %WHEEL_DIR%
  echo [DRY-RUN] backend env will be prepared at %BACKEND_ENV%
  echo [DRY-RUN] frontend env will be prepared at %FRONTEND_ENV%
  echo [DRY-RUN] backend venv will be created at %BACKEND_VENV%
  echo [DRY-RUN] backend migration and seed will run
  echo [DRY-RUN] frontend production build will run
  goto :success
)

if not exist "%WHEEL_DIR%" (
  echo [ERROR] offline wheelhouse not found: %WHEEL_DIR%
  goto :fail
)

if not exist "%BACKEND_ENV%" copy "%ROOT%\.env.example" "%BACKEND_ENV%" >nul
if not exist "%FRONTEND_ENV%" (
  >"%FRONTEND_ENV%" echo NEXT_PUBLIC_API_BASE_URL=http://localhost:18437
  >>"%FRONTEND_ENV%" echo SERVER_API_BASE_URL=http://localhost:18437
)

if not exist "%BACKEND_VENV%\Scripts\python.exe" (
  py -3.12 -m venv "%BACKEND_VENV%" || py -3 -m venv "%BACKEND_VENV%" || python -m venv "%BACKEND_VENV%" || goto :fail
)

call "%BACKEND_VENV%\Scripts\activate.bat" || goto :fail
pushd "%BACKEND_DIR%"
pip install --no-index --find-links "%WHEEL_DIR%" -r requirements-dev.txt || goto :fail_from_backend
set "PYTHONPATH=."
alembic upgrade head || goto :fail_from_backend
python scripts\seed.py || goto :fail_from_backend
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
echo.
echo Use --no-pause when launching from an existing terminal and you do not want the window to wait at the end.
exit /b 0
