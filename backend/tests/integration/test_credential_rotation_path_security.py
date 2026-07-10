from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

from tests.rotation_harness import create_synthetic_workspace, invoke_rotation


def test_canonical_database_hardlink_is_rejected_before_inspection(tmp_path: Path) -> None:
    # Given: the canonical database name is a hardlink to a file outside the workspace.
    workspace = create_synthetic_workspace(tmp_path)
    database_path = Path(workspace.database_url.removeprefix("sqlite:///"))
    outside_database = tmp_path / "outside.db"
    database_path.replace(outside_database)
    os.link(outside_database, database_path)

    # When: dry-run evaluates the canonical database boundary.
    completed = invoke_rotation(workspace, ("-DryRun",))

    # Then: physical link identity blocks Python inspection.
    assert completed.returncode != 0
    assert "hardlink-forbidden" in completed.stderr
    assert not (workspace.root / ".rotation-secure").exists()


def test_test_marker_hardlink_is_rejected_before_workspace_discovery(tmp_path: Path) -> None:
    # Given: a nonce-valid marker whose canonical name is a hardlink.
    workspace = create_synthetic_workspace(tmp_path)
    marker = workspace.root / ".aeroone-rotation-test-root"
    outside_marker = tmp_path / "outside-marker"
    marker.replace(outside_marker)
    os.link(outside_marker, marker)

    # When: TestMode evaluates the root capability.
    completed = invoke_rotation(workspace, ("-DryRun",))

    # Then: the marker cannot authorize a physical alias.
    assert completed.returncode != 0
    assert "hardlink-forbidden" in completed.stderr
    assert not (workspace.root / ".rotation-secure").exists()


def test_database_parent_junction_is_rejected_before_inspection(tmp_path: Path) -> None:
    # Given: the canonical database is reached through a junctioned data directory.
    workspace = create_synthetic_workspace(tmp_path)
    data_directory = workspace.root / "backend" / "data"
    outside_data = tmp_path / "outside-data"
    data_directory.replace(outside_data)
    linked = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(data_directory), str(outside_data)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert linked.returncode == 0

    # When: dry-run resolves the database through the canonical lexical path.
    completed = invoke_rotation(workspace, ("-DryRun",))

    # Then: component-level reparse detection blocks the alias.
    assert completed.returncode != 0
    assert "reparse-forbidden" in completed.stderr
    assert not (workspace.root / ".rotation-secure").exists()


def test_copied_script_cannot_target_the_production_workspace(tmp_path: Path) -> None:
    # Given: the reviewed script tree is copied outside the production workspace.
    repository_root = Path(__file__).resolve().parents[3]
    copied_root = tmp_path / "copied-tree"
    shutil.copytree(repository_root / "scripts", copied_root / "scripts")
    copied_script = copied_root / "scripts" / "rotate_aeroone_credentials.ps1"

    # When: the copied script is invoked in production mode.
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(copied_script),
            "-DryRun",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    # Then: physical provenance fails before environment or database discovery.
    assert completed.returncode != 0
    assert "provenance-root-mismatch" in completed.stderr
