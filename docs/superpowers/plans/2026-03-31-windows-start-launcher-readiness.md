# Windows Start Launcher Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `start.bat` and `start_offline.bat` open backend and frontend windows, wait for both services to become reachable, and only then open the browser, while failing clearly on fixed-port conflicts.

**Architecture:** Keep the existing batch entrypoints and frontend launcher scripts in place. Add one shared PowerShell readiness helper under `scripts/windows/`, route `scripts/open_browser.cmd` through that helper, and update the online/offline launchers to do fixed-port preflight checks before they start any windows. Protect the flow with Windows-only regression tests in `backend/tests/unit/shared/test_windows_batch_scripts.py` and finish with a short runbook update.

**Tech Stack:** Windows batch (`.bat` / `.cmd`), PowerShell, pytest, FastAPI/uvicorn, Next.js

---

## File Structure

- `start.bat`
  - Online Windows launcher.
  - Must keep the existing backend/frontend CMD windows.
  - Needs fixed-port preflight, readiness-gated browser opening, and clearer dry-run output.
- `start_offline.bat`
  - Offline Windows launcher.
  - Must mirror the online launcher flow with offline labels and commands.
- `scripts/open_browser.cmd`
  - Thin wrapper that hands browser-opening responsibility to the PowerShell readiness helper.
- `scripts/windows/wait_for_services.ps1`
  - New shared helper.
  - Waits for backend TCP readiness, then frontend TCP readiness, then opens the browser URL.
- `backend/tests/unit/shared/test_windows_batch_scripts.py`
  - Existing Windows batch-script regression coverage.
  - Extend this file instead of introducing a new test module.
- `docs/runbook/windows-offline.md`
  - User-facing Windows launcher guide.
  - Update it to reflect readiness-gated browser opening and fixed-port failure behavior.

## Notes Before Editing

- The current worktree already has uncommitted changes in `start.bat` and `start_offline.bat`.
- Preserve any user changes already present in those files.
- Before the first edit to either launcher, inspect the current diff with:

```powershell
git diff -- start.bat start_offline.bat
```

---

### Task 1: Extend Windows Launcher Regression Coverage

**Files:**
- Modify: `backend/tests/unit/shared/test_windows_batch_scripts.py`

- [ ] **Step 1: Review the current launcher diffs before touching tests**

Run:

```powershell
git diff -- start.bat start_offline.bat
```

Expected:

- You understand the current launcher state and do not overwrite existing user changes during later tasks.

- [ ] **Step 2: Add failing regression tests for the new launcher contract**

Update `backend/tests/unit/shared/test_windows_batch_scripts.py` with these additions:

```python
def _make_powershell_stub(tmp_path: Path) -> tuple[Path, Path]:
    bin_dir = tmp_path / "powershell-bin"
    bin_dir.mkdir()
    log_file = tmp_path / "powershell.log"
    (bin_dir / "powershell.bat").write_text(
        "@echo off\r\n"
        "echo powershell %*>>\"%STUB_LOG%\"\r\n"
        "exit /b 0\r\n",
        encoding="utf-8",
    )
    return bin_dir, log_file


def test_start_dry_run_prints_readiness_wrapper_command() -> None:
    result = _run_cmd(REPO_ROOT, "start.bat", "--dry-run")

    assert result.returncode == 0, result.stdout + result.stderr
    lines = _non_empty_lines(result.stdout)
    assert any("uvicorn app.main:app" in line for line in lines)
    assert any("start_frontend_dev.cmd" in line for line in lines)
    assert any(
        "open_browser.cmd" in line and "18437" in line and "29501" in line and "20" in line and "60" in line
        for line in lines
    )


def test_start_offline_dry_run_prints_readiness_wrapper_command() -> None:
    result = _run_cmd(REPO_ROOT, "start_offline.bat", "--dry-run")

    assert result.returncode == 0, result.stdout + result.stderr
    lines = _non_empty_lines(result.stdout)
    assert any("uvicorn app.main:app" in line for line in lines)
    assert any("start_frontend_offline.cmd" in line for line in lines)
    assert any(
        "open_browser.cmd" in line and "18437" in line and "29501" in line and "20" in line and "60" in line
        for line in lines
    )


def test_open_browser_cmd_delegates_to_wait_helper(tmp_path: Path) -> None:
    bin_dir, log_file = _make_powershell_stub(tmp_path)
    env = os.environ.copy()
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    env["STUB_LOG"] = str(log_file)

    result = _run_cmd(
        REPO_ROOT,
        "scripts\\open_browser.cmd",
        "http://localhost:29501/",
        "18437",
        "29501",
        "20",
        "60",
        env=env,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    invocation = log_file.read_text(encoding="utf-8")
    assert "wait_for_services.ps1" in invocation
    assert "-BackendPort 18437" in invocation
    assert "-FrontendPort 29501" in invocation
    assert "-BackendTimeoutSeconds 20" in invocation
    assert "-FrontendTimeoutSeconds 60" in invocation
```

- [ ] **Step 3: Run the new launcher tests and verify that they fail first**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/shared/test_windows_batch_scripts.py -k "readiness_wrapper_command or open_browser_cmd_delegates_to_wait_helper" -v
```

Expected:

- FAIL because the dry-run output does not yet include readiness-helper arguments.
- FAIL because `scripts/windows/wait_for_services.ps1` does not exist yet.

- [ ] **Step 4: Commit the failing-test checkpoint**

Run:

```powershell
git add backend/tests/unit/shared/test_windows_batch_scripts.py
git commit -m "test: cover windows launcher readiness flow"
```

Expected:

- A commit exists containing only the new failing regression tests.

---

### Task 2: Add the Shared Readiness Helper and Browser Wrapper

**Files:**
- Create: `scripts/windows/wait_for_services.ps1`
- Modify: `scripts/open_browser.cmd`
- Modify: `backend/tests/unit/shared/test_windows_batch_scripts.py`

- [ ] **Step 1: Add a failing timeout test for the PowerShell helper**

Append this test to `backend/tests/unit/shared/test_windows_batch_scripts.py`:

```python
def test_wait_for_services_times_out_when_backend_never_opens() -> None:
    helper = REPO_ROOT / "scripts" / "windows" / "wait_for_services.ps1"

    result = subprocess.run(
        [
            "powershell",
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(helper),
            "-Url",
            "http://localhost:29501/",
            "-BackendPort",
            "65530",
            "-FrontendPort",
            "65531",
            "-BackendTimeoutSeconds",
            "1",
            "-FrontendTimeoutSeconds",
            "1",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert result.returncode == 1
    combined = (result.stdout + result.stderr).lower()
    assert "backend" in combined
```

- [ ] **Step 2: Run the helper timeout test to verify it fails**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/shared/test_windows_batch_scripts.py::test_wait_for_services_times_out_when_backend_never_opens -v
```

Expected:

- FAIL because `scripts/windows/wait_for_services.ps1` does not exist yet.

- [ ] **Step 3: Create the shared PowerShell helper**

Create `scripts/windows/wait_for_services.ps1` with this content:

```powershell
param(
    [Parameter(Mandatory = $true)]
    [string]$Url,

    [Parameter(Mandatory = $true)]
    [int]$BackendPort,

    [Parameter(Mandatory = $true)]
    [int]$FrontendPort,

    [int]$BackendTimeoutSeconds = 20,
    [int]$FrontendTimeoutSeconds = 60,
    [string]$Host = "127.0.0.1"
)

$ErrorActionPreference = "Stop"

function Test-TcpPort {
    param(
        [string]$TargetHost,
        [int]$Port,
        [int]$ConnectTimeoutMs = 1000
    )

    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $async = $client.BeginConnect($TargetHost, $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne($ConnectTimeoutMs, $false)) {
            return $false
        }

        $client.EndConnect($async)
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Wait-PortReady {
    param(
        [string]$Label,
        [string]$TargetHost,
        [int]$Port,
        [int]$TimeoutSeconds
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-TcpPort -TargetHost $TargetHost -Port $Port) {
            Write-Host "[READY] $Label port $Port is accepting TCP connections."
            return $true
        }

        Start-Sleep -Seconds 1
    }

    Write-Host "[ERROR] $Label port $Port did not become ready within $TimeoutSeconds seconds."
    return $false
}

if (-not (Wait-PortReady -Label "Backend" -TargetHost $Host -Port $BackendPort -TimeoutSeconds $BackendTimeoutSeconds)) {
    exit 1
}

if (-not (Wait-PortReady -Label "Frontend" -TargetHost $Host -Port $FrontendPort -TimeoutSeconds $FrontendTimeoutSeconds)) {
    exit 1
}

Start-Process $Url | Out-Null
Write-Host "[READY] Opened browser: $Url"
exit 0
```

- [ ] **Step 4: Replace the fixed-delay browser wrapper**

Replace `scripts/open_browser.cmd` with this content:

```bat
@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "HELPER=%SCRIPT_DIR%\windows\wait_for_services.ps1"

set "URL=%~1"
if "%URL%"=="" set "URL=http://localhost:29501/"

set "BACKEND_PORT=%~2"
if "%BACKEND_PORT%"=="" set "BACKEND_PORT=18437"

set "FRONTEND_PORT=%~3"
if "%FRONTEND_PORT%"=="" set "FRONTEND_PORT=29501"

set "BACKEND_TIMEOUT=%~4"
if "%BACKEND_TIMEOUT%"=="" set "BACKEND_TIMEOUT=20"

set "FRONTEND_TIMEOUT=%~5"
if "%FRONTEND_TIMEOUT%"=="" set "FRONTEND_TIMEOUT=60"

if not exist "%HELPER%" (
  echo [ERROR] readiness helper not found: %HELPER%
  exit /b 1
)

powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%HELPER%" ^
  -Url "%URL%" ^
  -BackendPort %BACKEND_PORT% ^
  -FrontendPort %FRONTEND_PORT% ^
  -BackendTimeoutSeconds %BACKEND_TIMEOUT% ^
  -FrontendTimeoutSeconds %FRONTEND_TIMEOUT%

exit /b %errorlevel%
```

- [ ] **Step 5: Run the helper and wrapper tests**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/shared/test_windows_batch_scripts.py -k "open_browser_cmd_delegates_to_wait_helper or wait_for_services_times_out_when_backend_never_opens" -v
```

Expected:

- PASS for the wrapper delegation test.
- PASS for the helper timeout test.

- [ ] **Step 6: Commit the shared helper work**

Run:

```powershell
git add scripts/open_browser.cmd scripts/windows/wait_for_services.ps1 backend/tests/unit/shared/test_windows_batch_scripts.py
git commit -m "feat: add shared windows launcher readiness helper"
```

Expected:

- A commit exists containing the helper, the wrapper change, and the matching tests.

---

### Task 3: Wire Online and Offline Launchers to the Shared Flow

**Files:**
- Modify: `start.bat`
- Modify: `start_offline.bat`

- [ ] **Step 1: Update `start.bat` to preflight fixed ports and call the readiness wrapper**

In `start.bat`, make these three changes together:

1. Replace the unused browser flag state with explicit runtime constants near the top:

```bat
set "BACKEND_PORT=18437"
set "FRONTEND_PORT=29501"
set "BACKEND_URL=http://localhost:18437"
set "FRONTEND_URL=http://localhost:29501/"
set "BACKEND_TIMEOUT=20"
set "FRONTEND_TIMEOUT=60"
```

2. Replace the dry-run browser line and live browser launch with the readiness-aware form:

```bat
if defined DRY_RUN (
  echo [DRY-RUN] browser readiness command:
  echo call "%SCRIPTS_DIR%\open_browser.cmd" "%FRONTEND_URL%" %BACKEND_PORT% %FRONTEND_PORT% %BACKEND_TIMEOUT% %FRONTEND_TIMEOUT%
  exit /b 0
)

call :ensure_port_free %BACKEND_PORT% "Backend"
if errorlevel 1 goto :launch_failed

call :ensure_port_free %FRONTEND_PORT% "Frontend"
if errorlevel 1 goto :launch_failed

start "AeroOne Backend" cmd /k "title AeroOne Backend && chcp 65001 >nul && color 0A && echo ================================================== && echo [BACKEND][BOOT ] AeroOne API Server && echo URL  : %BACKEND_URL% && echo ROOT : %BACKEND_DIR% && echo CMD  : uvicorn app.main:app --host 0.0.0.0 --port %BACKEND_PORT% && echo ================================================== && echo [BACKEND][INFO ] Python virtualenv activating... && echo. && cd /d ""%BACKEND_DIR%"" && call .venv\Scripts\activate.bat && set PYTHONPATH=. && echo [BACKEND][READY] Launching uvicorn... && uvicorn app.main:app --host 0.0.0.0 --port %BACKEND_PORT%"
start "AeroOne Frontend" cmd /k "title AeroOne Frontend && chcp 65001 >nul && color 0B && echo ================================================== && echo [FRONTEND][BOOT] AeroOne Web UI && echo URL  : %FRONTEND_URL% && echo ROOT : %FRONTEND_DIR% && echo CMD  : scripts\\start_frontend_dev.cmd && echo ================================================== && echo [FRONTEND][INFO] Starting Next.js development server... && echo. && cd /d \"%SCRIPTS_DIR%\" && call start_frontend_dev.cmd"

call "%SCRIPTS_DIR%\open_browser.cmd" "%FRONTEND_URL%" %BACKEND_PORT% %FRONTEND_PORT% %BACKEND_TIMEOUT% %FRONTEND_TIMEOUT%
if errorlevel 1 (
  echo [FAILED] browser open aborted because backend/frontend readiness was not reached.
  pause
  exit /b 1
)
```

3. Add a reusable port-preflight label at the bottom of the file before `:help`:

```bat
:ensure_port_free
powershell -NoLogo -NoProfile -Command "$busy = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners() | Where-Object { $_.Port -eq %~1 }; if ($busy) { exit 1 } else { exit 0 }"
if errorlevel 1 (
  echo [ERROR] %~2 port %~1 is already in use.
  echo [INFO ] Release the port and rerun start.bat.
  pause
  exit /b 1
)
exit /b 0

:launch_failed
exit /b 1
```

- [ ] **Step 2: Mirror the same flow in `start_offline.bat`**

In `start_offline.bat`, apply the same orchestration shape with offline labels:

```bat
set "BACKEND_PORT=18437"
set "FRONTEND_PORT=29501"
set "BACKEND_URL=http://localhost:18437"
set "FRONTEND_URL=http://localhost:29501/"
set "BACKEND_TIMEOUT=20"
set "FRONTEND_TIMEOUT=60"
```

```bat
if defined DRY_RUN (
  echo [DRY-RUN] browser readiness command:
  echo call "%SCRIPTS_DIR%\open_browser.cmd" "%FRONTEND_URL%" %BACKEND_PORT% %FRONTEND_PORT% %BACKEND_TIMEOUT% %FRONTEND_TIMEOUT%
  exit /b 0
)

call :ensure_port_free %BACKEND_PORT% "Offline backend"
if errorlevel 1 goto :launch_failed

call :ensure_port_free %FRONTEND_PORT% "Offline frontend"
if errorlevel 1 goto :launch_failed

start "AeroOne Backend Offline" cmd /k "title AeroOne Backend Offline && chcp 65001 >nul && color 0A && echo ================================================== && echo [BACKEND][BOOT ] AeroOne API Server && echo URL  : %BACKEND_URL% && echo MODE : OFFLINE && echo ROOT : %BACKEND_DIR% && echo ================================================== && echo [BACKEND][INFO ] Python virtualenv activating... && echo. && cd /d ""%BACKEND_DIR%"" && call .venv\Scripts\activate.bat && set PYTHONPATH=. && echo [BACKEND][READY] Launching uvicorn... && uvicorn app.main:app --host 0.0.0.0 --port %BACKEND_PORT%"
start "AeroOne Frontend Offline" cmd /k "title AeroOne Frontend Offline && chcp 65001 >nul && color 0B && echo ================================================== && echo [FRONTEND][BOOT] AeroOne Web UI && echo URL  : %FRONTEND_URL% && echo MODE : OFFLINE && echo ROOT : %FRONTEND_DIR% && echo CMD  : scripts\\start_frontend_offline.cmd && echo ================================================== && echo [FRONTEND][INFO] Starting Next.js production server... && echo. && cd /d \"%SCRIPTS_DIR%\" && call start_frontend_offline.cmd"

call "%SCRIPTS_DIR%\open_browser.cmd" "%FRONTEND_URL%" %BACKEND_PORT% %FRONTEND_PORT% %BACKEND_TIMEOUT% %FRONTEND_TIMEOUT%
if errorlevel 1 (
  echo [FAILED] browser open aborted because backend/frontend readiness was not reached.
  pause
  exit /b 1
)
```

```bat
:ensure_port_free
powershell -NoLogo -NoProfile -Command "$busy = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners() | Where-Object { $_.Port -eq %~1 }; if ($busy) { exit 1 } else { exit 0 }"
if errorlevel 1 (
  echo [ERROR] %~2 port %~1 is already in use.
  echo [INFO ] Release the port and rerun start_offline.bat.
  pause
  exit /b 1
)
exit /b 0

:launch_failed
exit /b 1
```

- [ ] **Step 3: Run the Windows batch-script regression file**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/shared/test_windows_batch_scripts.py -v
```

Expected:

- PASS for the existing setup/start tests.
- PASS for the new online/offline dry-run and readiness-wrapper tests.

- [ ] **Step 4: Verify both dry-run entrypoints manually**

Run:

```powershell
cmd /d /c start.bat --dry-run
cmd /d /c start_offline.bat --dry-run
```

Expected:

- Both commands print backend launch, frontend launch, and readiness-wrapper commands.
- The browser command now includes `open_browser.cmd` with URL, backend port, frontend port, backend timeout, and frontend timeout.

- [ ] **Step 5: Commit the launcher wiring**

Run:

```powershell
git add start.bat start_offline.bat
git commit -m "feat: gate windows browser launch on service readiness"
```

Expected:

- A commit exists containing the online/offline launcher wiring changes.

---

### Task 4: Update the Windows Runbook and Perform Final Smoke Checks

**Files:**
- Modify: `docs/runbook/windows-offline.md`

- [ ] **Step 1: Update the runbook to describe readiness-gated browser opening**

Add this note to `docs/runbook/windows-offline.md` after the batch-file table:

```md
## 실행 시 동작
- `start.bat` 와 `start_offline.bat` 는 백엔드/프론트 CMD 창을 먼저 연 뒤, 두 포트(`18437`, `29501`)가 준비되었을 때만 브라우저를 엽니다.
- 두 포트 중 하나라도 이미 사용 중이면 브라우저를 열지 않고 즉시 오류를 출력한 뒤 멈춥니다.
- 브라우저가 열리지 않으면 launcher 창 메시지와 백엔드/프론트 CMD 로그를 함께 확인합니다.
```

- [ ] **Step 2: Re-run the automated regression file after the doc-touch commit candidate is ready**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/shared/test_windows_batch_scripts.py -v
```

Expected:

- PASS.

- [ ] **Step 3: Run the online launcher smoke test**

Run:

```powershell
start.bat
```

Expected:

- A backend CMD window opens.
- A frontend CMD window opens.
- The browser does not open immediately.
- The browser opens only after the frontend is reachable at `http://localhost:29501/`.

- [ ] **Step 4: Run the offline launcher smoke test**

Run:

```powershell
start_offline.bat
```

Expected:

- The offline backend and frontend CMD windows open.
- The browser does not open until readiness is reached.
- If the offline environment is not fully installed, the launcher still fails clearly without opening a premature browser window.

- [ ] **Step 5: Commit the runbook and final verification state**

Run:

```powershell
git add docs/runbook/windows-offline.md
git commit -m "docs: describe windows launcher readiness behavior"
```

Expected:

- A commit exists documenting the launcher behavior change.

---

## Final Verification Checklist

- [ ] `backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/shared/test_windows_batch_scripts.py -v`
- [ ] `cmd /d /c start.bat --dry-run`
- [ ] `cmd /d /c start_offline.bat --dry-run`
- [ ] `start.bat`
- [ ] `start_offline.bat`
- [ ] Confirm browser opens only after readiness.
- [ ] Confirm fixed-port conflicts stop the launcher before browser open.

