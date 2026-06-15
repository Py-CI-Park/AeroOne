@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM Open Notebook vendored fork 의 'core diff 0' 게이트 (ralplan DECISION-1 / ADR-6).
REM vendored 애플리케이션 소스(airgap/ adapter 제외)가 핀된 upstream tag 대비 단 한 줄도
REM 바뀌지 않았는지 git diff --quiet 의 exit-code 로 판정한다. --quiet 는 --exit-code 를 함의하므로
REM --stat(변경 유무와 무관히 exit 0)과 달리 기계 게이트로 신뢰할 수 있다.
REM   exit 0 = core diff 0  (핀 승격 가능)
REM   exit 1 = core 오염     (핀 승격 차단)
REM   exit 2 = 사용 오류 / submodule 부재 / tag 부재 / git 실패

if /I "%~1"=="--help" goto :help

set "SCRIPTS_DIR=%~dp0"
if "%SCRIPTS_DIR:~-1%"=="\" set "SCRIPTS_DIR=%SCRIPTS_DIR:~0,-1%"
set "ROOT=%SCRIPTS_DIR%\.."
pushd "%ROOT%" & set "ROOT=%CD%" & popd

set "VENDOR=%ROOT%\vendor\open-notebook"
set "UPSTREAM_TAG=%~1"
if "%UPSTREAM_TAG%"=="" set "UPSTREAM_TAG=v1.9.0"

REM adapter 경로 = docs\runbook\open-notebook-airgap.md §1.1 동결 목록.
REM adapter 가 늘면 여기 EXCLUDES 와 런북 §1.1 표를 동시에 갱신해야 게이트가 정확하다.
set "EXCLUDES=:(exclude)airgap"

echo [CORE-DIFF] vendor  : %VENDOR%
echo [CORE-DIFF] tag     : %UPSTREAM_TAG%
echo [CORE-DIFF] exclude : %EXCLUDES%

if not exist "%VENDOR%\" (
  echo [CORE-DIFF][ERROR] vendored submodule not present: %VENDOR%
  echo [CORE-DIFF][INFO ] vendoring is operator gate OP-1 ^(.gitmodules + fork aeroone/airgap pin^).
  echo [CORE-DIFF][INFO ] run: git submodule update --init vendor/open-notebook, then rerun this gate.
  exit /b 2
)

git -C "%VENDOR%" rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
  echo [CORE-DIFF][ERROR] %VENDOR% is not a git work tree.
  exit /b 2
)

git -C "%VENDOR%" rev-parse --verify --quiet "%UPSTREAM_TAG%^{commit}" >nul 2>&1
if errorlevel 1 (
  echo [CORE-DIFF][ERROR] upstream tag '%UPSTREAM_TAG%' not found in %VENDOR%.
  echo [CORE-DIFF][INFO ] fetch it first: git -C vendor/open-notebook fetch --tags upstream
  exit /b 2
)

git -C "%VENDOR%" diff --quiet "%UPSTREAM_TAG%..HEAD" -- . "%EXCLUDES%"
set "DIFF_EXIT=!errorlevel!"

if "!DIFF_EXIT!"=="0" (
  echo [CORE-DIFF][OK] core diff 0 — vendored core unchanged vs %UPSTREAM_TAG% ^(adapter %EXCLUDES% excluded^). pin promotion allowed.
  exit /b 0
)
if "!DIFF_EXIT!"=="1" (
  echo [CORE-DIFF][FAIL] core polluted — vendored source differs from %UPSTREAM_TAG% OUTSIDE adapter. pin promotion BLOCKED.
  echo [CORE-DIFF][INFO ] offending files:
  git -C "%VENDOR%" diff --name-only "%UPSTREAM_TAG%..HEAD" -- . "%EXCLUDES%"
  exit /b 1
)
echo [CORE-DIFF][ERROR] git diff failed ^(exit !DIFF_EXIT!^).
exit /b 2

:help
echo Usage: check_open_notebook_core_diff.cmd [^<upstream-tag^>]
echo.
echo Gate: vendored Open Notebook core (excluding the airgap/ adapter) must equal the
echo pinned upstream tag exactly. Uses git diff --quiet (--exit-code), not --stat.
echo   ^<upstream-tag^>   upstream tag baseline (default v1.9.0)
echo Exit: 0 = core diff 0 (pin OK) ^| 1 = core polluted (pin BLOCKED) ^| 2 = usage/submodule/tag/git error
exit /b 0
