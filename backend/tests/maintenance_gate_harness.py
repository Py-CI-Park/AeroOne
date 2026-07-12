from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import time


REPO_ROOT = Path(__file__).resolve().parents[2]


def rotation_at_database_barrier(
    root: Path,
    *,
    barrier: str = "hold_after_recovery",
    extra_arguments: tuple[str, ...] = (),
) -> tuple[subprocess.Popen[str], Path]:
    nonce = root.name.removeprefix("aeroone-rotation-test-")
    environment = os.environ.copy()
    for key in tuple(environment):
        if key.startswith("AEROONE_ROTATION_"):
            del environment[key]
    environment["AEROONE_ROTATION_PYTHON"] = sys.executable
    environment["AEROONE_ROTATION_INTERNAL_DB_BARRIER"] = f"{nonce}:{barrier}"
    environment["TEMP"] = str(root.parent)
    environment["TMP"] = str(root.parent)
    process = subprocess.Popen(
        (
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(REPO_ROOT / "scripts" / "rotate_aeroone_credentials.ps1"),
            "-TestMode",
            "-TestWorkspaceRoot",
            str(root),
            *extra_arguments,
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
    )
    ready = root / ".aeroone-rotation-db-barrier-ready"
    deadline = time.monotonic() + 60
    while not ready.is_file():
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            raise AssertionError(f"rotation exited before barrier: {stdout=} {stderr=}")
        if time.monotonic() >= deadline:
            process.kill()
            stdout, stderr = process.communicate()
            raise AssertionError(f"rotation barrier timed out: {stdout=} {stderr=}")
        time.sleep(0.05)
    return process, root / ".aeroone-rotation-db-barrier-release"


def terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        process.kill()
    try:
        process.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate(timeout=10)


def wait_for_file(path: Path, process: subprocess.Popen[str], timeout_seconds: int = 30) -> None:
    deadline = time.monotonic() + timeout_seconds
    while not path.is_file():
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            raise AssertionError(f"process exited before marker: {stdout=} {stderr=}")
        if time.monotonic() >= deadline:
            raise AssertionError(f"marker timed out: {path}")
        time.sleep(0.05)
