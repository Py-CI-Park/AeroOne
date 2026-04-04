# Windows Frontend Launcher Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `start.bat` reliably launch the frontend on Windows by fixing the broken batch quoting, removing default cold-start cache deletion, widening readiness host checks, and increasing frontend startup tolerance without rewriting the launcher architecture.

**Architecture:** Keep `start.bat` as the online launcher orchestrator and preserve the existing backend launch flow. Move frontend window bootstrap into a dedicated wrapper script, make frontend cache clearing opt-in through `--clean`, and upgrade the shared PowerShell readiness helper so it can succeed across `127.0.0.1`, `::1`, and `localhost`. Protect the change with focused Windows batch-script regression tests in `backend/tests/unit/shared/test_windows_batch_scripts.py`, then finish with a direct launcher smoke test.

**Tech Stack:** Windows batch (`.bat` / `.cmd`), PowerShell, Python/pytest, Next.js development server

---

## File Structure

- `start.bat`
  - Online Windows launcher entrypoint.
  - Must remain the orchestrator only: fixed-port preflight, backend launch, frontend launch, readiness-gated browser open.
  - Needs the frontend launch command simplified to delegate to a wrapper and needs a larger frontend timeout.
- `scripts/start_frontend_window.cmd`
  - New frontend-window bootstrap wrapper.
  - Owns title, code page, color, banner output, and delegation to `start_frontend_dev.cmd`.
- `scripts/start_frontend_dev.cmd`
  - Frontend dev-server launcher.
  - Must keep responsibility limited to entering `frontend/` and launching `npm run dev`.
  - Cache deletion must become opt-in via `--clean`.
- `scripts/windows/wait_for_services.ps1`
  - Shared readiness helper used by `scripts/open_browser.cmd`.
  - Must succeed when backend/frontend ports accept TCP connections on any approved local host form.
- `backend/tests/unit/shared/test_windows_batch_scripts.py`
  - Existing Windows batch regression coverage.
  - Extend this file instead of creating a new test module so launcher behavior stays in one place.

## Notes Before Editing

- The current working tree may contain untracked runtime log files such as:
  - `frontend-run.out.log`
  - `frontend-run.err.log`
- Do not stage or commit runtime log files.
- Before the first code edit, confirm only the intended documentation and script files are tracked:

```powershell
git status --short
```

Expected:

- You can see any transient runtime log files and avoid staging them in later commit steps.

---

### Task 1: Add Failing Regression Tests For Frontend Launcher Reliability

**Files:**
- Modify: `backend/tests/unit/shared/test_windows_batch_scripts.py`

- [ ] **Step 1: Add the new helper imports and temp-repo utilities**

Update the import block at the top of `backend/tests/unit/shared/test_windows_batch_scripts.py` to include `socket`:

```python
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys

import pytest
```

Then add these helper utilities below `_make_open_browser_test_copy(...)`:

```python
def _make_frontend_launcher_repo(tmp_path: Path) -> tuple[Path, Path, Path]:
    repo_root = tmp_path / "repo"
    frontend_dir = repo_root / "frontend"
    scripts_dir = repo_root / "scripts"

    frontend_dir.mkdir(parents=True)
    scripts_dir.mkdir(parents=True)

    shutil.copy2(REPO_ROOT / "scripts" / "start_frontend_dev.cmd", scripts_dir / "start_frontend_dev.cmd")
    return repo_root, frontend_dir, scripts_dir


def _make_wait_for_services_test_copy(tmp_path: Path) -> Path:
    helper_dir = tmp_path / "scripts" / "windows"
    helper_dir.mkdir(parents=True)
    helper_path = helper_dir / "wait_for_services.ps1"

    script_text = (REPO_ROOT / "scripts" / "windows" / "wait_for_services.ps1").read_text(encoding="utf-8")
    script_text = script_text.replace(
        "Start-Process $Url | Out-Null",
        'Write-Host "[READY] Browser launch skipped in test"',
        1,
    )
    helper_path.write_text(script_text, encoding="utf-8")
    return helper_path
```

- [ ] **Step 2: Add failing launcher reliability tests**

Append these tests to `backend/tests/unit/shared/test_windows_batch_scripts.py`:

```python
def test_start_dry_run_uses_frontend_wrapper_and_extended_timeout() -> None:
    result = _run_cmd(REPO_ROOT, "start.bat", "--dry-run")

    assert result.returncode == 0, result.stdout + result.stderr
    lines = _non_empty_lines(result.stdout)
    browser_line = next((line for line in lines if "open_browser.cmd" in line), None)

    assert any("start_frontend_window.cmd" in line for line in lines)
    assert browser_line is not None
    assert " 180" in f" {browser_line}", browser_line


def test_start_frontend_window_delegates_to_dev_script(tmp_path: Path) -> None:
    repo_root, _, scripts_dir = _make_frontend_launcher_repo(tmp_path)
    shutil.copy2(REPO_ROOT / "scripts" / "start_frontend_window.cmd", scripts_dir / "start_frontend_window.cmd")
    bin_dir, log_file = _make_stub_commands(tmp_path)
    env = os.environ.copy()
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    env["STUB_LOG"] = str(log_file)

    result = _run_cmd(repo_root, r"scripts\start_frontend_window.cmd", env=env)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "[FRONTEND][BOOT] AeroOne Web UI" in result.stdout
    assert any(
        line.startswith("npm.cmd run dev")
        for line in log_file.read_text(encoding="utf-8").splitlines()
    )


def test_start_frontend_dev_preserves_caches_without_clean(tmp_path: Path) -> None:
    repo_root, frontend_dir, _ = _make_frontend_launcher_repo(tmp_path)
    bin_dir, log_file = _make_stub_commands(tmp_path)
    env = os.environ.copy()
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    env["STUB_LOG"] = str(log_file)

    (frontend_dir / ".next").mkdir()
    (frontend_dir / ".turbo").mkdir()

    result = _run_cmd(repo_root, r"scripts\start_frontend_dev.cmd", env=env)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (frontend_dir / ".next").exists()
    assert (frontend_dir / ".turbo").exists()
    assert any(
        line.startswith("npm.cmd run dev")
        for line in log_file.read_text(encoding="utf-8").splitlines()
    )


def test_start_frontend_dev_clears_caches_with_clean(tmp_path: Path) -> None:
    repo_root, frontend_dir, _ = _make_frontend_launcher_repo(tmp_path)
    bin_dir, log_file = _make_stub_commands(tmp_path)
    env = os.environ.copy()
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    env["STUB_LOG"] = str(log_file)

    (frontend_dir / ".next").mkdir()
    (frontend_dir / ".turbo").mkdir()

    result = _run_cmd(repo_root, r"scripts\start_frontend_dev.cmd", "--clean", env=env)

    assert result.returncode == 0, result.stdout + result.stderr
    assert not (frontend_dir / ".next").exists()
    assert not (frontend_dir / ".turbo").exists()
    assert any(
        line.startswith("npm.cmd run dev")
        for line in log_file.read_text(encoding="utf-8").splitlines()
    )


def test_wait_for_services_accepts_ipv6_loopback_listeners(tmp_path: Path) -> None:
    helper_path = _make_wait_for_services_test_copy(tmp_path)

    backend_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    frontend_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    for sock in (backend_socket, frontend_socket):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    backend_socket.bind(("::1", 0))
    frontend_socket.bind(("::1", 0))
    backend_socket.listen(1)
    frontend_socket.listen(1)

    backend_port = backend_socket.getsockname()[1]
    frontend_port = frontend_socket.getsockname()[1]

    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoLogo",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(helper_path),
                "-Url",
                "http://localhost:29501/",
                "-BackendPort",
                str(backend_port),
                "-FrontendPort",
                str(frontend_port),
                "-BackendTimeoutSeconds",
                "2",
                "-FrontendTimeoutSeconds",
                "2",
            ],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    finally:
        backend_socket.close()
        frontend_socket.close()

    assert result.returncode == 0, result.stdout + result.stderr
    combined = (result.stdout + result.stderr).lower()
    assert f"backend port {backend_port}" in combined
    assert f"frontend port {frontend_port}" in combined
```

- [ ] **Step 3: Run the new reliability-focused tests and verify they fail first**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/shared/test_windows_batch_scripts.py -k "frontend_wrapper_and_extended_timeout or start_frontend_window_delegates_to_dev_script or start_frontend_dev_preserves_caches_without_clean or start_frontend_dev_clears_caches_with_clean or wait_for_services_accepts_ipv6_loopback_listeners" -v
```

Expected:

- FAIL because `start_frontend_window.cmd` does not exist yet
- FAIL because `start_frontend_dev.cmd` still deletes caches by default
- FAIL because `start.bat --dry-run` still shows the old frontend command and `60` second timeout
- FAIL because `wait_for_services.ps1` only checks `127.0.0.1`

- [ ] **Step 4: Commit the failing-test checkpoint**

Run:

```powershell
git add backend/tests/unit/shared/test_windows_batch_scripts.py
git commit -m "test: cover frontend launcher reliability regressions"
```

Expected:

- A commit exists containing only the new failing regression tests.

---

### Task 2: Add The Frontend Window Wrapper And Make Cache Clearing Opt-In

**Files:**
- Create: `scripts/start_frontend_window.cmd`
- Modify: `scripts/start_frontend_dev.cmd`
- Modify: `backend/tests/unit/shared/test_windows_batch_scripts.py`

- [ ] **Step 1: Create the frontend window wrapper**

Create `scripts/start_frontend_window.cmd` with this content:

```bat
@echo off
setlocal EnableExtensions

set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
set "FRONTEND_DIR=%ROOT%\frontend"

title AeroOne Frontend
chcp 65001 >nul
color 0B
echo ==================================================
echo [FRONTEND][BOOT] AeroOne Web UI
echo URL  : http://localhost:29501/
echo ROOT : %FRONTEND_DIR%
echo CMD  : scripts\start_frontend_dev.cmd
echo ==================================================
echo [FRONTEND][INFO] Starting Next.js development server...
echo.

call "%~dp0start_frontend_dev.cmd"
exit /b %errorlevel%
```

- [ ] **Step 2: Make `start_frontend_dev.cmd` preserve caches by default**

Replace `scripts/start_frontend_dev.cmd` with this content:

```bat
@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
set "FRONTEND_DIR=%ROOT%\frontend"
set "CLEAR_CACHE="

if /I "%~1"=="--clean" set "CLEAR_CACHE=1"

cd /d "%FRONTEND_DIR%" || exit /b 1

if defined CLEAR_CACHE (
  if exist ".next" (
    echo [FRONTEND][INFO] Clearing stale .next cache...
    rmdir /s /q ".next"
  )

  if exist ".turbo" (
    echo [FRONTEND][INFO] Clearing stale .turbo cache...
    rmdir /s /q ".turbo"
  )
)

call npm run dev
exit /b %errorlevel%
```

- [ ] **Step 3: Run the wrapper/cache tests**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/shared/test_windows_batch_scripts.py -k "start_frontend_window_delegates_to_dev_script or start_frontend_dev_preserves_caches_without_clean or start_frontend_dev_clears_caches_with_clean" -v
```

Expected:

- PASS for all three tests.

- [ ] **Step 4: Commit the wrapper and cache behavior**

Run:

```powershell
git add scripts/start_frontend_window.cmd scripts/start_frontend_dev.cmd
git commit -m "feat: make frontend launcher startup path stable"
```

Expected:

- A commit exists containing the new wrapper and the `--clean` cache behavior.

---

### Task 3: Fix `start.bat` And Broaden Frontend Readiness Detection

**Files:**
- Modify: `start.bat`
- Modify: `scripts/windows/wait_for_services.ps1`
- Modify: `backend/tests/unit/shared/test_windows_batch_scripts.py`

- [ ] **Step 1: Update `start.bat` to use the wrapper and longer timeout**

In `start.bat`, change the frontend timeout:

```bat
set "FRONTEND_TIMEOUT=180"
```

Replace the dry-run frontend line with:

```bat
echo cmd /k start_frontend_window.cmd
```

Replace the live frontend launch line with:

```bat
start "AeroOne Frontend" /D "%SCRIPTS_DIR%" cmd /k start_frontend_window.cmd
```

Do not change the backend launch line.

- [ ] **Step 2: Broaden `wait_for_services.ps1` host checks**

Replace `scripts/windows/wait_for_services.ps1` with this content:

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
    [string[]]$TargetHosts = @("127.0.0.1", "::1", "localhost")
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
        [string[]]$TargetHosts,
        [int]$Port,
        [int]$TimeoutSeconds
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        foreach ($targetHost in $TargetHosts) {
            if (Test-TcpPort -TargetHost $targetHost -Port $Port) {
                Write-Host "[READY] $Label port $Port is accepting TCP connections on $targetHost."
                return $true
            }
        }

        Start-Sleep -Seconds 1
    }

    Write-Host "[ERROR] $Label port $Port did not become ready within $TimeoutSeconds seconds."
    return $false
}

if (-not (Wait-PortReady -Label "Backend" -TargetHosts $TargetHosts -Port $BackendPort -TimeoutSeconds $BackendTimeoutSeconds)) {
    exit 1
}

if (-not (Wait-PortReady -Label "Frontend" -TargetHosts $TargetHosts -Port $FrontendPort -TimeoutSeconds $FrontendTimeoutSeconds)) {
    exit 1
}

Start-Process $Url | Out-Null
Write-Host "[READY] Opened browser: $Url"
exit 0
```

- [ ] **Step 3: Run the launcher reliability regression subset**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/shared/test_windows_batch_scripts.py -k "frontend_wrapper_and_extended_timeout or wait_for_services_accepts_ipv6_loopback_listeners or start_frontend_window_delegates_to_dev_script or start_frontend_dev_preserves_caches_without_clean or start_frontend_dev_clears_caches_with_clean" -v
```

Expected:

- PASS for all selected tests.

- [ ] **Step 4: Verify `start.bat --dry-run` shows the new structure**

Run:

```powershell
cmd /d /c start.bat --dry-run
```

Expected:

- frontend dry-run output references `start_frontend_window.cmd`
- browser readiness line includes `open_browser.cmd` with timeout `180`
- no nested `call \"%SCRIPTS_DIR%\\start_frontend_dev.cmd\"` pattern remains

- [ ] **Step 5: Commit the launcher orchestration and readiness changes**

Run:

```powershell
git add start.bat scripts/windows/wait_for_services.ps1 backend/tests/unit/shared/test_windows_batch_scripts.py
git commit -m "feat: harden the Windows frontend launcher"
```

Expected:

- A commit exists containing the online launcher fix and readiness helper update.

---

### Task 4: Perform Final Smoke Verification

**Files:**
- No code changes required in this task unless smoke verification exposes a new launcher bug.

- [ ] **Step 1: Run the full Windows batch regression file**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/shared/test_windows_batch_scripts.py -v
```

Expected:

- PASS for the existing launcher tests
- PASS for the new frontend reliability tests

- [ ] **Step 2: Run the online launcher smoke test**

Run:

```powershell
cmd /d /c start.bat
```

Expected:

- backend CMD window opens
- frontend CMD window opens
- browser opens only after readiness succeeds
- launcher exits with status `0`

- [ ] **Step 3: Verify the key frontend URLs**

Run:

```powershell
powershell -NoLogo -NoProfile -Command "(Invoke-WebRequest -Uri http://127.0.0.1:29501/ -UseBasicParsing -TimeoutSec 60).StatusCode"
powershell -NoLogo -NoProfile -Command "(Invoke-WebRequest -Uri http://127.0.0.1:29501/newsletters -UseBasicParsing -TimeoutSec 60).StatusCode"
```

Expected:

- first command prints `200`
- second command prints `200`

- [ ] **Step 4: Verify the clean-start path still works**

Run:

```powershell
cmd /d /c scripts\start_frontend_dev.cmd --clean
```

Expected:

- `.next` and `.turbo` are removed before startup
- `npm run dev` still starts successfully

- [ ] **Step 5: If smoke verification required no additional code changes, stop without a new commit**

Run:

```powershell
git status --short
```

Expected:

- no tracked file changes remain
- only transient runtime artifacts, if any, need cleanup

If a smoke-test bug required a code fix, commit that fix separately with a narrow message before closing the task.

---

## Final Verification Checklist

- [ ] `git status --short`
- [ ] `backend\.venv\Scripts\python.exe -m pytest backend/tests/unit/shared/test_windows_batch_scripts.py -v`
- [ ] `cmd /d /c start.bat --dry-run`
- [ ] `cmd /d /c start.bat`
- [ ] `powershell -NoLogo -NoProfile -Command "(Invoke-WebRequest -Uri http://127.0.0.1:29501/ -UseBasicParsing -TimeoutSec 60).StatusCode"`
- [ ] `powershell -NoLogo -NoProfile -Command "(Invoke-WebRequest -Uri http://127.0.0.1:29501/newsletters -UseBasicParsing -TimeoutSec 60).StatusCode"`
- [ ] `cmd /d /c scripts\start_frontend_dev.cmd --clean`
- [ ] Confirm browser opens only after readiness
- [ ] Confirm frontend launch no longer depends on fragile nested quoted batch invocation
