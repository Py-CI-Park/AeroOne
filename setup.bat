@echo off
setlocal EnableExtensions

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
set "CURRENT_STEP=초기화"

if /I "%~1"=="--help" goto :help
if /I "%~1"=="--dry-run" set "DRY_RUN=1"
if /I "%~1"=="--no-pause" set "NO_PAUSE=1"
if /I "%~2"=="--no-pause" set "NO_PAUSE=1"

call :banner

set "CURRENT_STEP=필수 디렉터리 확인"
echo [1/7] %CURRENT_STEP%
if not exist "%BACKEND_DIR%" (
  echo [ERROR] backend directory not found: %BACKEND_DIR%
  goto :fail
)
if not exist "%FRONTEND_DIR%" (
  echo [ERROR] frontend directory not found: %FRONTEND_DIR%
  goto :fail
)
echo [OK] 디렉터리 확인 완료

if defined DRY_RUN goto :dryrun

set "CURRENT_STEP=backend env 작성"
echo [2/7] %CURRENT_STEP%
call :write_backend_env || goto :fail
echo [OK] backend .env 작성 완료

set "CURRENT_STEP=frontend env 작성"
echo [3/7] %CURRENT_STEP%
call :write_frontend_env || goto :fail
echo [OK] frontend .env.local 작성 완료

set "CURRENT_STEP=Python 가상환경 준비"
echo [4/7] %CURRENT_STEP%
if not exist "%BACKEND_VENV%\Scripts\python.exe" (
  py -3.12 -m venv "%BACKEND_VENV%" || py -3 -m venv "%BACKEND_VENV%" || python -m venv "%BACKEND_VENV%"
  if errorlevel 1 goto :fail
  echo [OK] backend .venv 생성 완료
) else (
  echo [INFO] 기존 backend .venv 재사용
)
if not exist "%BACKEND_DIR%\data" mkdir "%BACKEND_DIR%\data"

set "CURRENT_STEP=백엔드 설치 및 DB 준비"
echo [5/7] %CURRENT_STEP%
call "%BACKEND_VENV%\Scripts\activate.bat" || goto :fail
pushd "%BACKEND_DIR%"
pip install -r requirements-dev.txt || goto :fail_from_backend
set "PYTHONPATH=."
python scripts\ensure_db_state.py data\aeroone.db
set "MIGRATION_MODE=%ERRORLEVEL%"
if "%MIGRATION_MODE%"=="3" (
  echo [INFO] 기존 DB를 감지했습니다. Alembic head stamp를 수행합니다.
  alembic stamp head || goto :fail_from_backend
) else (
  echo [INFO] Alembic upgrade head 실행
  alembic upgrade head || goto :fail_from_backend
)
python scripts\seed.py || goto :fail_from_backend
popd
echo [OK] backend 설치 및 DB 준비 완료

set "CURRENT_STEP=프론트엔드 의존성 설치"
echo [6/7] %CURRENT_STEP%
pushd "%FRONTEND_DIR%"
call npm install || goto :fail_from_frontend
popd
echo [OK] frontend 의존성 설치 완료

set "CURRENT_STEP=최종 안내"
echo [7/7] %CURRENT_STEP%
goto :success

:dryrun
echo [DRY-RUN] backend env 경로: %BACKEND_ENV%
echo [DRY-RUN] frontend env 경로: %FRONTEND_ENV%
echo [DRY-RUN] backend venv 경로: %BACKEND_VENV%
echo [DRY-RUN] 다음 순서로 실행됩니다:
echo           1. env 파일 작성
echo           2. venv 생성 또는 재사용
echo           3. pip install
echo           4. alembic upgrade 또는 stamp
echo           5. seed 실행
echo           6. npm install
goto :success

:write_backend_env
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
exit /b 0

:write_frontend_env
if exist "%FRONTEND_ENV%" copy /y "%FRONTEND_ENV%" "%FRONTEND_ENV%.bak" >nul
>"%FRONTEND_ENV%" echo NEXT_PUBLIC_API_BASE_URL=http://localhost:18437
>>"%FRONTEND_ENV%" echo SERVER_API_BASE_URL=http://localhost:18437
exit /b 0

:fail_from_backend
popd
goto :fail

:fail_from_frontend
popd
goto :fail

:fail
echo.
echo ========================================
echo [FAILED] setup.bat 실패
echo 실패 단계: %CURRENT_STEP%
echo 확인 권장:
echo   1. Python 또는 py 명령 사용 가능 여부
echo   2. 인터넷 연결 상태
echo   3. backend 폴더 쓰기 권한
echo ========================================
if not defined NO_PAUSE pause
exit /b 1

:success
echo.
echo ========================================
echo [OK] setup.bat 완료
echo 다음 단계:
echo   1. start.bat 실행
echo   2. 브라우저에서 http://localhost:29501/newsletters 접속
echo   3. 관리자 로그인: http://localhost:29501/login
echo   4. 백엔드 상태 확인: http://localhost:18437/api/v1/health
echo ========================================
if not defined NO_PAUSE pause
exit /b 0

:help
echo Usage: setup.bat [--dry-run] [--no-pause]
echo.
echo 인터넷 가능한 Windows PC에서 초기 설치를 수행합니다.
echo - backend .env 작성
echo - frontend .env.local 작성
echo - backend .venv 생성 또는 재사용
echo - pip install
 echo - alembic upgrade 또는 stamp
 echo - seed 실행
 echo - frontend npm install
exit /b 0

:banner
echo ========================================
echo AeroOne Windows Setup
echo Root: %ROOT%
echo Backend Port : 18437
echo Frontend Port: 29501
echo ========================================
exit /b 0
