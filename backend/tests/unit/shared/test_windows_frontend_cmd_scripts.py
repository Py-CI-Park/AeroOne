from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows batch scripts only")

REPO_ROOT = Path(__file__).resolve().parents[4]


def _run_cmd(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["cmd", "/d", "/c", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def test_start_frontend_dev_script_runs_npm_with_call() -> None:
    script = REPO_ROOT / "scripts" / "start_frontend_dev.cmd"
    contents = script.read_text(encoding="utf-8")

    assert "call npm run dev" in contents


def test_start_frontend_offline_script_runs_npx_with_call() -> None:
    script = REPO_ROOT / "scripts" / "start_frontend_offline.cmd"
    contents = script.read_text(encoding="utf-8")

    assert "call npx next start" in contents
