from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import time

from tests.maintenance_gate_harness import (
    rotation_at_database_barrier,
    terminate_process,
    wait_for_file,
)
from tests.rotation_harness import create_synthetic_workspace


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_start_wrapper_waits_while_rotation_holds_maintenance_gate(tmp_path: Path) -> None:
    # Given: credential rotation owns the workspace maintenance gate mid-transaction.
    workspace = create_synthetic_workspace(tmp_path)
    rotation, release = rotation_at_database_barrier(workspace.root)
    marker = workspace.root / "synthetic-app-crossed.txt"
    command = workspace.root / "synthetic-app-start.cmd"
    command.write_text(f'@echo crossed>"{marker}"\n', encoding="utf-8")
    gate = REPO_ROOT / "scripts" / "windows" / "invoke_with_maintenance_gate.ps1"
    starter = subprocess.Popen(
        (
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(gate),
            "-WorkspaceRoot",
            str(workspace.root),
            "-BatchPath",
            str(command),
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # When: the synthetic start wrapper tries to cross the gate before rotation releases it.
    try:
        time.sleep(1)
        assert starter.poll() is None
        assert not marker.exists()
        release.write_text("release", encoding="utf-8")
        rotation_stdout, rotation_stderr = rotation.communicate(timeout=90)
        starter_stdout, starter_stderr = starter.communicate(timeout=30)
    finally:
        release.write_text("release", encoding="utf-8")
        terminate_process(starter)
        terminate_process(rotation)

    # Then: rotation completes first and the start action crosses exactly once afterward.
    assert rotation.returncode == 0, rotation_stderr
    assert "status=complete" in rotation_stdout
    assert starter.returncode == 0, f"{starter_stdout=} {starter_stderr=}"
    assert marker.read_text(encoding="utf-8").strip() == "crossed"


def test_backend_direct_gate_interlocks_with_rotation_for_process_lifetime(
    tmp_path: Path,
) -> None:
    # Given: rotation owns the gate for an isolated nonce-bound workspace.
    workspace = create_synthetic_workspace(tmp_path)
    rotation, release = rotation_at_database_barrier(workspace.root)
    direct_marker = workspace.root / "direct-gate-acquired.txt"
    wrapper_marker = workspace.root / "wrapper-crossed.txt"
    wrapper_command = workspace.root / "wrapper-after-direct.cmd"
    wrapper_command.write_text(f'@echo crossed>"{wrapper_marker}"\n', encoding="utf-8")
    probe_program = "\n".join(
        (
            "from pathlib import Path",
            "import sys",
            "from app.core.maintenance_gate import acquire_backend_maintenance_gate",
            "acquire_backend_maintenance_gate(workspace_root=Path(sys.argv[1]))",
            "Path(sys.argv[2]).write_text('acquired', encoding='utf-8')",
            "sys.stdin.readline()",
        )
    )
    probe_environment = os.environ.copy()
    probe_environment["APP_ENV"] = "test"
    probe_environment["AEROONE_MAINTENANCE_GATE_TEST_FIXTURE"] = (
        "pytest-isolated-maintenance-probe"
    )
    probe_environment["PYTHONPATH"] = str(REPO_ROOT / "backend")
    probe = subprocess.Popen(
        [sys.executable, "-c", probe_program, str(workspace.root), str(direct_marker)],
        cwd=REPO_ROOT / "backend",
        env=probe_environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    starter: subprocess.Popen[str] | None = None

    # When: rotation releases to the direct backend, then a wrapper waits on that backend lease.
    try:
        time.sleep(1)
        assert not direct_marker.exists()
        release.write_text("release", encoding="utf-8")
        rotation_stdout, rotation_stderr = rotation.communicate(timeout=90)
        wait_for_file(direct_marker, probe)
        starter = subprocess.Popen(
            (
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(REPO_ROOT / "scripts" / "windows" / "invoke_with_maintenance_gate.ps1"),
                "-WorkspaceRoot",
                str(workspace.root),
                "-BatchPath",
                str(wrapper_command),
            ),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        time.sleep(1)
        assert starter.poll() is None
        assert not wrapper_marker.exists()
        assert probe.stdin is not None
        probe.stdin.close()
        probe.stdin = None
        probe.wait(timeout=30)
        starter_stdout, starter_stderr = starter.communicate(timeout=30)
    finally:
        release.write_text("release", encoding="utf-8")
        if probe.stdin is not None:
            probe.stdin.close()
            probe.stdin = None
        terminate_process(probe)
        if starter is not None:
            terminate_process(starter)
        terminate_process(rotation)

    # Then: acquisition order is rotation, direct backend lifetime, and finally wrapper.
    assert rotation.returncode == 0, rotation_stderr
    assert "status=complete" in rotation_stdout
    assert probe.returncode == 0
    assert starter is not None
    assert starter.returncode == 0, f"{starter_stdout=} {starter_stderr=}"
    assert wrapper_marker.read_text(encoding="utf-8").strip() == "crossed"


def test_app_entry_acquires_maintenance_gate_before_config_or_database_imports() -> None:
    # Given: the direct uvicorn module entry source.
    source = (REPO_ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
    bootstrap = (
        REPO_ROOT / "backend" / "app" / "core" / "maintenance_gate_bootstrap.py"
    ).read_text(encoding="utf-8")

    # When: import and acquisition positions are compared to settings and DB imports.
    acquisition = source.index("from app.core.maintenance_gate_bootstrap import")
    settings_import = source.index("from app.core.config import")
    database_import = source.index("from app.db.session import")

    # Then: no settings or database work can run before the process-lifetime gate is held.
    assert acquisition < settings_import
    assert acquisition < database_import
    assert "acquire_backend_maintenance_gate()" in bootstrap
