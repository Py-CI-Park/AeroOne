# AeroOne Windows Start Launcher Readiness Design

Date: 2026-03-31
Status: Approved for planning

## Summary

`Newsletter_AI` uses a Windows launcher flow where running `Run.bat` opens separate backend and frontend terminals and only opens the browser after the web stack is actually ready. `AeroOne` should provide the same user experience when `start.bat` or `start_offline.bat` is executed.

The approved design keeps the current lightweight batch-oriented structure in `AeroOne`. It does not import the heavier `Newsletter_AI` PowerShell launcher stack. Instead, it adds one shared Windows readiness helper and upgrades the existing batch files so browser opening is gated on backend and frontend readiness rather than a fixed sleep.

## Goals

- Running `start.bat` opens separate backend and frontend terminals and then opens the browser only after both services are ready.
- Running `start_offline.bat` follows the same readiness-gated flow.
- Startup failures remain visible to the user instead of silently opening the browser too early.
- The implementation stays small, reviewable, and consistent with the existing `AeroOne` script layout.

## Non-Goals

- Rebuilding `AeroOne` around the full `Newsletter_AI` `run_web.ps1` architecture.
- Adding automatic fallback ports.
- Changing backend or frontend runtime commands beyond what is required to support the launcher flow.
- Modifying setup or packaging scripts unless a narrow compatibility fix is required by the launcher change.

## Current State

- `start.bat` and `start_offline.bat` already open backend and frontend in separate CMD windows.
- `scripts/open_browser.cmd` currently waits a fixed number of seconds and then opens the target URL.
- Fixed-delay browser opening is fragile because frontend startup time is variable.
- If a fixed port is already in use, the current flow can produce ambiguous results or open the browser before the correct app is ready.
- `scripts/start_frontend_dev.cmd` and `scripts/start_frontend_offline.cmd` already provide a clean boundary for frontend runtime commands and should keep that responsibility only.

## Approved Approach

### 1. Keep the current entry points

The primary entry points remain:

- `start.bat`
- `start_offline.bat`

These batch files continue to launch separate backend and frontend CMD windows. This preserves the current Windows usage model and keeps the change reversible.

### 2. Introduce one shared readiness helper

Add one Windows-specific helper script under `scripts/windows/`:

- Recommended file: `scripts/windows/wait_for_services.ps1`

This helper is responsible for:

- waiting for the backend port to accept TCP connections
- waiting for the frontend port to accept TCP connections
- opening the browser only after both checks succeed
- returning a non-zero exit code when readiness is not reached in time

This helper replaces the current fixed-delay logic without introducing the full `Newsletter_AI` launcher system.

### 3. Keep `open_browser.cmd` as a thin wrapper

`scripts/open_browser.cmd` remains the batch-level browser launcher surface, but its internal behavior changes:

- remove the hard-coded `timeout /t 6`
- delegate readiness checks to `scripts/windows/wait_for_services.ps1`
- accept the target URL and readiness parameters from the caller

This keeps Windows callers simple and allows both online and offline launchers to reuse the same behavior.

### 4. Preserve frontend script boundaries

The following scripts continue to focus only on starting frontend processes:

- `scripts/start_frontend_dev.cmd`
- `scripts/start_frontend_offline.cmd`

They should not own browser opening or readiness checks. If needed, they may receive small argument or quoting cleanup, but no change in responsibility is intended.

## Runtime Flow

### Online

1. `start.bat` verifies required directories exist.
2. `start.bat` performs a preflight fixed-port availability check for backend `18437` and frontend `29501`.
3. If either port is already occupied, `start.bat` prints a clear error and stops before opening any new browser window.
4. If both ports are free, `start.bat` opens backend and frontend CMD windows.
5. `start.bat` then calls `scripts/open_browser.cmd` with:
   - frontend URL
   - backend port
   - frontend port
   - backend timeout
   - frontend timeout
6. `open_browser.cmd` delegates to `wait_for_services.ps1`.
7. The PowerShell helper waits for backend readiness first, then frontend readiness.
8. If both services become reachable, the helper opens the browser to the frontend URL.
9. If readiness fails, the helper exits non-zero and `start.bat` shows the failure reason and pauses.

### Offline

`start_offline.bat` follows the same flow. The only intentional differences are the existing offline runtime commands and labels. Readiness policy remains shared.

## Port and Readiness Policy

- Online backend port: `18437`
- Online frontend port: `29501`
- Offline backend port: `18437`
- Offline frontend port: `29501`
- Ports remain fixed; no automatic fallback is introduced
- Readiness is defined as successful TCP connection to the configured port
- Browser opening order is always `backend ready` then `frontend ready` then `open browser`

Recommended default timeouts:

- backend timeout: 20 seconds
- frontend timeout: 60 seconds

The longer frontend timeout reflects slower Next.js startup on cold boot.

## Error Handling

### Port collision

- Detect before service launch when possible.
- Print which fixed port is occupied.
- Do not start the browser.
- Do not auto-switch to a different port.
- Stop with `pause` so the user can read the error.

### Readiness timeout

- If backend readiness fails, stop before frontend browser open.
- If frontend readiness fails, stop before browser open.
- Keep the backend and frontend CMD windows open so the user can inspect logs.
- Print a short summary in the launcher window and pause.

### Immediate helper failure

- If `open_browser.cmd` or the PowerShell helper cannot run, the launcher treats this as a startup failure.
- The launcher prints the failing step and pauses.

## Dry-Run Behavior

`--dry-run` remains supported in both `start.bat` and `start_offline.bat`.

Dry-run output should show:

- backend launch command
- frontend launch command
- readiness-helper invocation
- final target URL

This keeps the launcher inspectable without starting processes.

## Files Expected To Change

- `start.bat`
- `start_offline.bat`
- `scripts/open_browser.cmd`
- `scripts/windows/wait_for_services.ps1` (new)

Possible narrow-touch files:

- `scripts/start_frontend_dev.cmd`
- `scripts/start_frontend_offline.cmd`

## Verification Plan

### Static verification

- confirm `--dry-run` output for `start.bat`
- confirm `--dry-run` output for `start_offline.bat`
- confirm readiness helper receives the expected ports, timeouts, and URL

### Functional verification

- run `start.bat` and verify:
  - backend CMD window opens
  - frontend CMD window opens
  - browser does not open before services are ready
  - browser opens after frontend readiness
- run `start_offline.bat` and verify the same behavior

### Failure verification

- simulate a fixed-port collision and verify:
  - clear error is shown
  - browser does not open
  - launcher pauses
- simulate a readiness timeout and verify:
  - browser does not open
  - launcher prints which phase failed
  - backend and frontend windows remain available for debugging

## Rationale

This design intentionally copies the user-visible behavior of `Newsletter_AI` while avoiding its larger launcher framework. The result is a smaller change set with clear responsibilities:

- batch files launch windows and report status
- frontend scripts start frontend processes
- one shared Windows helper performs readiness checks and browser opening

That balance matches the requested outcome without over-engineering the launcher stack.
