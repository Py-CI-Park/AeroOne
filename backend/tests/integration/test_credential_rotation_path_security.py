from __future__ import annotations

import os
from pathlib import Path
import shutil
import sqlite3
import subprocess

from tests.rotation_harness import create_synthetic_workspace, invoke_rotation


def _acl_sddl(path: Path) -> str:
    process_environment = os.environ.copy()
    process_environment["AEROONE_ACL_PATH"] = str(path)
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "(Get-Acl -LiteralPath $env:AEROONE_ACL_PATH).Sddl",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=process_environment,
        timeout=30,
    )
    return completed.stdout.strip()


def _database_rotation_state(database_path: Path) -> tuple[str, int, int]:
    with sqlite3.connect(database_path) as connection:
        user = connection.execute(
            "SELECT password_hash, session_version FROM users WHERE username = 'admin'",
        ).fetchone()
        ledger_count = connection.execute(
            "SELECT COUNT(*) FROM credential_rotation_ledger",
        ).fetchone()
    assert user is not None
    assert ledger_count is not None
    return str(user[0]), int(user[1]), int(ledger_count[0])


def _rotation_snapshot(
    root_environment: Path,
    backend_environment: Path,
    database_path: Path,
) -> tuple[bytes, bytes, tuple[str, int, int], str, str, str]:
    return (
        root_environment.read_bytes(),
        backend_environment.read_bytes(),
        _database_rotation_state(database_path),
        _acl_sddl(root_environment),
        _acl_sddl(backend_environment),
        _acl_sddl(database_path),
    )


def test_root_environment_hardlink_is_rejected_without_mutation(tmp_path: Path) -> None:
    # Given: the live root environment is a hardlink and all mutable state is snapshotted.
    workspace = create_synthetic_workspace(tmp_path)
    root_environment = workspace.root / ".env"
    backend_environment = workspace.root / "backend" / ".env"
    database_path = Path(workspace.database_url.removeprefix("sqlite:///"))
    outside_environment = tmp_path / "outside-root.env"
    root_environment.replace(outside_environment)
    os.link(outside_environment, root_environment)
    before = _rotation_snapshot(root_environment, backend_environment, database_path)

    # When: an ordinary rotation evaluates the live environments.
    completed = invoke_rotation(workspace)

    # Then: physical preflight rejects before any filesystem, ACL, or DB mutation.
    assert completed.returncode != 0
    assert "hardlink-forbidden" in completed.stderr
    assert not (workspace.root / ".rotation-secure").exists()
    assert before == _rotation_snapshot(root_environment, backend_environment, database_path)


def test_backend_environment_hardlink_is_rejected_without_mutation(tmp_path: Path) -> None:
    # Given: the live backend environment is a hardlink and all mutable state is snapshotted.
    workspace = create_synthetic_workspace(tmp_path)
    root_environment = workspace.root / ".env"
    backend_environment = workspace.root / "backend" / ".env"
    database_path = Path(workspace.database_url.removeprefix("sqlite:///"))
    outside_environment = tmp_path / "outside-backend.env"
    backend_environment.replace(outside_environment)
    os.link(outside_environment, backend_environment)
    before = _rotation_snapshot(root_environment, backend_environment, database_path)

    # When: an ordinary rotation evaluates the live environments.
    completed = invoke_rotation(workspace)

    # Then: physical preflight rejects before any filesystem, ACL, or DB mutation.
    assert completed.returncode != 0
    assert "hardlink-forbidden" in completed.stderr
    assert not (workspace.root / ".rotation-secure").exists()
    assert before == _rotation_snapshot(root_environment, backend_environment, database_path)


def test_backend_environment_junction_is_rejected_without_mutation(tmp_path: Path) -> None:
    # Given: the backend environment and database are reached through a directory junction.
    workspace = create_synthetic_workspace(tmp_path)
    backend_directory = workspace.root / "backend"
    outside_backend = tmp_path / "outside-backend"
    backend_directory.replace(outside_backend)
    linked = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(backend_directory), str(outside_backend)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert linked.returncode == 0
    root_environment = workspace.root / ".env"
    backend_environment = backend_directory / ".env"
    database_path = backend_directory / "data" / "aeroone.db"
    before = _rotation_snapshot(root_environment, backend_environment, database_path)

    # When: an ordinary rotation evaluates the live environments.
    completed = invoke_rotation(workspace)

    # Then: component reparse preflight rejects before any mutable state changes.
    assert completed.returncode != 0
    assert "reparse-forbidden" in completed.stderr
    assert not (workspace.root / ".rotation-secure").exists()
    assert before == _rotation_snapshot(root_environment, backend_environment, database_path)


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


def test_copied_rotation_entry_derives_its_own_trusted_product_root(tmp_path: Path) -> None:
    # Given: the reviewed script tree is copied into a production-like root with no live environment.
    repository_root = Path(__file__).resolve().parents[3]
    copied_root = tmp_path / "copied-tree"
    shutil.copytree(repository_root / "scripts", copied_root / "scripts")
    copied_script = copied_root / "scripts" / "rotate_aeroone_credentials.ps1"
    user_profile = tmp_path / "profile"
    user_profile.mkdir()
    process_environment = os.environ.copy()
    process_environment["USERPROFILE"] = str(user_profile)

    # When: the copied canonical rotation entry is invoked in production-mode dry-run.
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
        env=process_environment,
        timeout=30,
    )

    # Then: self-provenance succeeds and the next missing-environment boundary rejects.
    assert completed.returncode != 0
    assert "env-missing" in completed.stderr
    assert "provenance-" not in completed.stderr
