@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "DRY_RUN="
if /I "%~1"=="--dry-run" set "DRY_RUN=1"
if /I "%~1"=="--help" goto :help

for /f %%I in ('powershell -NoProfile -Command "(Get-Date).ToString(\"yyyyMMdd-HHmmss\")"') do set "STAMP=%%I"
set "DIST_DIR=%ROOT%\dist"
set "STAGE_DIR=%DIST_DIR%\offline-package-%STAMP%"
set "REPO_STAGE=%STAGE_DIR%\AeroOne"
set "WHEEL_DIR=%REPO_STAGE%\offline_assets\python-wheels"
set "ZIP_PATH=%DIST_DIR%\AeroOne-offline-%STAMP%.zip"
set "INSTALLER_SRC=%ROOT%\offline_installers"

if defined DRY_RUN (
  echo [DRY-RUN] create %REPO_STAGE%
  echo [DRY-RUN] robocopy repository into stage
  echo [DRY-RUN] py -3.12 -m pip download -r backend\requirements-dev.txt -d %WHEEL_DIR%
  echo [DRY-RUN] npm install in frontend if needed
  echo [DRY-RUN] robocopy frontend\node_modules into staged frontend\node_modules
  echo [DRY-RUN] copy offline_installers if present
  echo [DRY-RUN] Compress-Archive to %ZIP_PATH%
  exit /b 0
)

if exist "%STAGE_DIR%" rmdir /s /q "%STAGE_DIR%"
mkdir "%REPO_STAGE%" || exit /b 1
mkdir "%WHEEL_DIR%" || exit /b 1
if not exist "%DIST_DIR%" mkdir "%DIST_DIR%"

robocopy "%ROOT%" "%REPO_STAGE%" /E /R:1 /W:1 /NFL /NDL /NJH /NJS /XD .git .omx .venv .python_packages dist backend\.venv frontend\node_modules frontend\.next backend\data offline_installers >nul
if errorlevel 8 exit /b 1

if not exist "%ROOT%\frontend\node_modules" (
  pushd "%ROOT%\frontend"
  call npm install || exit /b 1
  popd
) else (
  echo [INFO] frontend\node_modules already exists. Reusing current install.
)

robocopy "%ROOT%\frontend\node_modules" "%REPO_STAGE%\frontend\node_modules" /E /R:1 /W:1 /NFL /NDL /NJH /NJS >nul
if errorlevel 8 exit /b 1

py -3.12 -m pip download -r "%ROOT%\backend\requirements-dev.txt" -d "%WHEEL_DIR%" || py -3 -m pip download -r "%ROOT%\backend\requirements-dev.txt" -d "%WHEEL_DIR%" || python -m pip download -r "%ROOT%\backend\requirements-dev.txt" -d "%WHEEL_DIR%" || exit /b 1

if exist "%INSTALLER_SRC%" (
  robocopy "%INSTALLER_SRC%" "%REPO_STAGE%\offline_assets\installers" /E /R:1 /W:1 /NFL /NDL /NJH /NJS >nul
)

>"%REPO_STAGE%\offline_assets\README-OFFLINE.txt" echo 1. Run setup_offline.bat on the offline PC.
>>"%REPO_STAGE%\offline_assets\README-OFFLINE.txt" echo 2. Then run start_offline.bat.
>>"%REPO_STAGE%\offline_assets\README-OFFLINE.txt" echo 3. Optional installers can be placed in offline_installers before packaging.

if exist "%ZIP_PATH%" del /f /q "%ZIP_PATH%"
powershell -NoProfile -Command "Compress-Archive -Path '%REPO_STAGE%\*' -DestinationPath '%ZIP_PATH%' -Force" || exit /b 1

echo [OK] offline package created: %ZIP_PATH%
exit /b 0

:help
echo Usage: offline_package.bat [--dry-run]
echo.
echo Creates a ZIP bundle for offline Windows PCs.
echo Bundle includes repo source, Python wheelhouse, frontend node_modules, and optional installers.
exit /b 0
