# AeroOne Windows Frontend Launcher Reliability Design

Date: 2026-04-04
Status: Approved for planning

## Summary

`AeroOne` currently has a Windows launcher failure in `start.bat` where the backend starts correctly but the frontend often fails to start through the batch launcher flow. Manual frontend startup works, which shows the application itself is healthy and narrows the fault to launcher orchestration.

The approved design fixes the direct launch failure and the most likely recurrence factors without rewriting the entire launcher stack. The change keeps the existing Windows batch entrypoints, but makes frontend startup safer by moving the frontend window bootstrap into a dedicated wrapper, removing unconditional frontend cache deletion from the default path, increasing frontend readiness timeout, and making readiness checks more tolerant of local host binding variations.

## Goals

- Make `start.bat` reliably start both backend and frontend on Windows.
- Eliminate the frontend launcher quoting failure in the current batch command.
- Reduce false launcher failures caused by slow cold starts.
- Preserve the current user-facing workflow: one launcher, separate backend/frontend windows, browser auto-open after readiness.
- Keep the change small, reviewable, and consistent with the current script layout.

## Non-Goals

- Replacing the Windows batch launcher system with a different launcher architecture.
- Changing backend runtime behavior.
- Changing Next.js application behavior beyond startup reliability.
- Introducing automatic fallback ports.
- Adding unrelated refactors to packaging or setup scripts.

## Current State

- `start.bat` launches backend and frontend in separate CMD windows.
- The backend launch path works reliably.
- The frontend launch path is embedded as a long `cmd /k "..."` string containing a quoted batch-script invocation.
- Reproducing that invocation directly shows the current quoting is invalid for `cmd`, causing the frontend startup script not to run.
- `scripts/start_frontend_dev.cmd` always deletes `.next` and `.turbo` before launching `npm run dev`.
- `scripts/windows/wait_for_services.ps1` checks readiness only against `127.0.0.1`.
- `FRONTEND_TIMEOUT` is currently `60` seconds, which is vulnerable to cold-start delays when frontend caches are wiped.

## Root Cause

The primary failure is launcher-side quoting in the frontend command inside `start.bat`.

The frontend launch currently uses a command of this shape:

- `call \"%SCRIPTS_DIR%\\start_frontend_dev.cmd\"`

When reproduced through `cmd /c`, this does not resolve to a valid batch invocation and causes the frontend launch step to fail before Next.js even starts.

This direct fault is made more fragile by two additional factors:

1. `scripts/start_frontend_dev.cmd` forces a cold boot by deleting `.next` and `.turbo` every time.
2. `wait_for_services.ps1` gives the frontend only `60` seconds and only checks one host form.

The result is:

1. backend starts
2. frontend launch command fails or becomes unnecessarily slow
3. readiness helper waits for port `29501`
4. launcher exits with frontend readiness failure

## Approved Approach

### 1. Keep `start.bat` as the orchestrator

`start.bat` remains responsible for:

- verifying required directories exist
- checking fixed ports before startup
- opening backend and frontend windows
- invoking browser-open/readiness behavior

It should not continue to embed a fragile long frontend bootstrap string.

### 2. Move frontend window bootstrap into a dedicated wrapper

Add a dedicated script:

- `scripts/start_frontend_window.cmd`

This wrapper owns:

- window title
- code page setup
- color
- banner output
- calling `start_frontend_dev.cmd`

This allows `start.bat` to launch the frontend window with a short stable command instead of inline nested quoting.

### 3. Make frontend cache clearing opt-in

`scripts/start_frontend_dev.cmd` should not delete `.next` and `.turbo` by default.

Approved behavior:

- default: launch `npm run dev` without cache deletion
- optional: `--clean` enables cache deletion before launch

This keeps the common launch path fast while preserving a manual escape hatch for cache-related debugging.

### 4. Increase frontend readiness tolerance

`FRONTEND_TIMEOUT` in `start.bat` should be increased from `60` seconds to a value better suited for Windows cold starts.

Recommended default:

- `180` seconds

This is intentionally conservative because startup reliability matters more than aggressive timeout failure in the default launcher path.

### 5. Broaden local readiness host checks

`scripts/windows/wait_for_services.ps1` should no longer assume only `127.0.0.1`.

Approved readiness targets:

- `127.0.0.1`
- `::1`
- `localhost`

The helper should succeed when any of these host forms can establish a TCP connection for the target port.

## Runtime Flow After Change

1. `start.bat` checks fixed ports `18437` and `29501`.
2. `start.bat` opens the backend window exactly as today.
3. `start.bat` opens the frontend window by delegating to `scripts/start_frontend_window.cmd`.
4. `start_frontend_window.cmd` prints the frontend banner and calls `scripts/start_frontend_dev.cmd`.
5. `start_frontend_dev.cmd` launches `npm run dev` without deleting caches unless `--clean` is explicitly provided.
6. `start.bat` invokes `scripts/open_browser.cmd`.
7. `wait_for_services.ps1` waits for backend readiness, then frontend readiness, across the approved local host forms.
8. Once both services are ready, the browser opens to `http://localhost:29501/`.

## Error Handling

### Frontend launch failure

- If the frontend wrapper or frontend dev script cannot run, the frontend CMD window should show the error directly.
- The launcher window should fail only after frontend readiness is not reached.

### Slow cold start

- The launcher should tolerate a much longer first startup due to the increased frontend timeout.
- Default startup should be faster because cache deletion is removed from the normal path.

### Cache-debug scenario

- If the user needs a clean frontend boot, they should be able to run the frontend script with `--clean`.
- Cache clearing is therefore preserved, but no longer imposed on every launcher run.

## Files Expected To Change

- `start.bat`
- `scripts/start_frontend_dev.cmd`
- `scripts/windows/wait_for_services.ps1`
- `scripts/start_frontend_window.cmd` (new)

## Verification Plan

### Static verification

- confirm the frontend launch line in `start.bat` no longer uses the fragile nested quoted `call \"%SCRIPTS_DIR%\\start_frontend_dev.cmd\"` pattern
- confirm `start_frontend_dev.cmd` only clears caches when explicitly asked
- confirm `wait_for_services.ps1` supports multiple local host forms
- confirm dry-run output matches the new launch structure

### Functional verification

- run `start.bat`
- verify backend window opens
- verify frontend window opens
- verify browser opens automatically after readiness
- verify `http://localhost:29501/` returns `200`
- verify `http://localhost:29501/newsletters` returns `200`

### Regression verification

- re-run `start.bat` after the frontend has previously started once
- verify no false frontend timeout occurs due to default cache clearing
- manually run `scripts/start_frontend_dev.cmd --clean` and confirm the clean-start path still works

## Rationale

This design intentionally avoids a full launcher rewrite. The current issue is specific and well-understood:

- frontend command quoting is fragile
- frontend cold-start path is unnecessarily slow
- readiness checks are stricter than needed

The approved solution fixes all three with narrowly-scoped script changes. That is the best trade-off between reliability, reviewability, and preserving the current Windows workflow.
