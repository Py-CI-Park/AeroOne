from __future__ import annotations

import atexit
import os
from pathlib import Path
import subprocess


_TEST_FIXTURE_ENV = "AEROONE_MAINTENANCE_GATE_TEST_FIXTURE"
_BYPASS_TEST_FIXTURE_VALUE = "pytest-app-env-test"
_PROBE_TEST_FIXTURE_VALUE = "pytest-isolated-maintenance-probe"
_lease_process: subprocess.Popen[str] | None = None


def _release_lease() -> None:
    global _lease_process
    process = _lease_process
    _lease_process = None
    if process is None:
        return
    if process.stdin is not None:
        process.stdin.close()
    try:
        _ = process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        _ = process.wait(timeout=10)


def _validate_probe_workspace(workspace_root: Path) -> Path:
    resolved = workspace_root.resolve(strict=True)
    prefix = "aeroone-rotation-test-"
    nonce = resolved.name.removeprefix(prefix)
    marker = resolved / ".aeroone-rotation-test-root"
    if (
        not resolved.name.startswith(prefix)
        or len(nonce) != 32
        or not marker.is_file()
        or marker.read_text(encoding="utf-8") != f"aeroone-rotation-test-v1:{nonce}"
    ):
        raise RuntimeError("maintenance-gate-probe-workspace-forbidden")
    return resolved


def acquire_backend_maintenance_gate(*, workspace_root: Path | None = None) -> None:
    global _lease_process
    if os.name != "nt" or _lease_process is not None:
        return
    app_env = os.environ.get("APP_ENV", "development")
    fixture = os.environ.get(_TEST_FIXTURE_ENV, "")
    if app_env == "test" and fixture == _BYPASS_TEST_FIXTURE_VALUE and workspace_root is None:
        return
    if workspace_root is None:
        if fixture:
            raise RuntimeError("maintenance-gate-test-fixture-forbidden")
        selected_workspace = Path(__file__).resolve().parents[3]
    elif app_env == "test" and fixture == _PROBE_TEST_FIXTURE_VALUE:
        selected_workspace = _validate_probe_workspace(workspace_root)
    else:
        raise RuntimeError("maintenance-gate-test-fixture-forbidden")
    product_root = Path(__file__).resolve().parents[3]
    holder = product_root / "scripts" / "windows" / "hold_maintenance_gate.ps1"
    process = subprocess.Popen(
        (
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(holder),
            "-WorkspaceRoot",
            str(selected_workspace),
        ),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if process.stdout is None:
        process.kill()
        _ = process.wait(timeout=10)
        raise RuntimeError("maintenance-gate-output-unavailable")
    ready = process.stdout.readline().strip()
    if ready != "status=maintenance-gate-ready":
        stderr = "" if process.stderr is None else process.stderr.read().strip()
        process.kill()
        _ = process.wait(timeout=10)
        raise RuntimeError(f"maintenance-gate-acquire-failed:{stderr}")
    _lease_process = process


_ = atexit.register(_release_lease)
