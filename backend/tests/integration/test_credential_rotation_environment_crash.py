from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from tests.rotation_harness import create_synthetic_workspace, env_value, invoke_rotation


def _database_state(database_path: Path) -> tuple[int, int]:
    with sqlite3.connect(database_path) as connection:
        session_version = connection.execute(
            "SELECT session_version FROM users WHERE username = 'admin'",
        ).fetchone()
        ledger_count = connection.execute(
            "SELECT COUNT(*) FROM credential_rotation_ledger",
        ).fetchone()
    assert session_version is not None
    assert ledger_count is not None
    return int(session_version[0]), int(ledger_count[0])


@pytest.mark.parametrize(
    ("crashpoint", "active_relative", "quarantine_name"),
    (
        ("crash_after_root_env_publish", ".env", "root.env.before-rotation"),
        (
            "crash_after_backend_env_publish",
            "backend/.env",
            "backend.env.before-rotation",
        ),
    ),
)
def test_environment_publish_crash_resumes_without_recreating_old_quarantine(
    tmp_path: Path,
    crashpoint: str,
    active_relative: str,
    quarantine_name: str,
) -> None:
    # Given: a process self-kills immediately after one active env publish.
    workspace = create_synthetic_workspace(tmp_path)
    database_path = Path(workspace.database_url.removeprefix("sqlite:///"))
    active_environment = workspace.root / active_relative
    old_environment = active_environment.read_bytes()
    crashed = invoke_rotation(workspace, internal_crashpoint=crashpoint)
    quarantine = (
        workspace.root / ".rotation-secure" / "quarantine" / "environment" / quarantine_name
    )
    published_environment = active_environment.read_bytes()
    quarantine_identity = (quarantine.stat().st_ino, quarantine.stat().st_mtime_ns)
    committed_state = _database_state(database_path)

    # When: a new process resumes the journal one phase behind the observed active digest.
    resumed = invoke_rotation(workspace)

    # Then: it validates NEW, advances only the journal, and preserves the old quarantine object.
    assert crashed.returncode != 0
    assert published_environment != old_environment
    assert quarantine.read_bytes() == old_environment
    assert resumed.returncode == 0, resumed.stderr
    assert active_environment.read_bytes() == published_environment
    assert (quarantine.stat().st_ino, quarantine.stat().st_mtime_ns) == quarantine_identity
    assert _database_state(database_path) == committed_state == (3, 1)
    assert workspace.jwt_secret not in crashed.stdout + crashed.stderr
    assert workspace.admin_password not in crashed.stdout + crashed.stderr


def test_foreign_active_environment_after_publish_crash_fails_closed(tmp_path: Path) -> None:
    # Given: root publish completed, then the process died and the active env became foreign.
    workspace = create_synthetic_workspace(tmp_path)
    crashed = invoke_rotation(
        workspace,
        internal_crashpoint="crash_after_root_env_publish",
    )
    root_environment = workspace.root / ".env"
    backend_environment = workspace.root / "backend" / ".env"
    quarantine = (
        workspace.root
        / ".rotation-secure"
        / "quarantine"
        / "environment"
        / "root.env.before-rotation"
    )
    assert crashed.returncode != 0
    root_environment.write_text(
        root_environment.read_text(encoding="utf-8").replace(
            f"JWT_SECRET_KEY={env_value(root_environment, 'JWT_SECRET_KEY')}",
            "JWT_SECRET_KEY=foreign-drift",
        ),
        encoding="utf-8",
    )
    before = (
        root_environment.read_bytes(),
        backend_environment.read_bytes(),
        quarantine.read_bytes(),
    )

    # When: resume observes a digest matching neither expected OLD nor expected NEW.
    resumed = invoke_rotation(workspace)

    # Then: it rejects without changing either live env or the bound quarantine.
    assert resumed.returncode != 0
    assert "root-env-state-ambiguous" in resumed.stderr
    assert before == (
        root_environment.read_bytes(),
        backend_environment.read_bytes(),
        quarantine.read_bytes(),
    )


def test_restored_old_environment_reuses_validated_quarantine_on_resume(
    tmp_path: Path,
) -> None:
    # Given: root publish crashed after quarantine, then an exact old env backup was restored.
    workspace = create_synthetic_workspace(tmp_path)
    crashed = invoke_rotation(
        workspace,
        internal_crashpoint="crash_after_root_env_publish",
    )
    root_environment = workspace.root / ".env"
    quarantine = (
        workspace.root
        / ".rotation-secure"
        / "quarantine"
        / "environment"
        / "root.env.before-rotation"
    )
    old_environment = quarantine.read_bytes()
    quarantine_identity = (quarantine.stat().st_ino, quarantine.stat().st_mtime_ns)
    root_environment.write_bytes(old_environment)

    # When: resume sees OLD live bytes already represented by the bound quarantine entry.
    resumed = invoke_rotation(workspace)

    # Then: it reuses that verified entry and completes without a destructive first failure.
    assert crashed.returncode != 0
    assert resumed.returncode == 0, resumed.stderr
    assert root_environment.read_bytes() != old_environment
    assert quarantine.read_bytes() == old_environment
    assert (quarantine.stat().st_ino, quarantine.stat().st_mtime_ns) == quarantine_identity


def test_plaintext_environment_temp_orphan_is_zeroized_and_removed_on_resume(
    tmp_path: Path,
) -> None:
    # Given: the process self-kills halfway through a root env sibling temp write.
    workspace = create_synthetic_workspace(tmp_path)
    crashed = invoke_rotation(
        workspace,
        internal_crashpoint="crash_during_root_env_temp_write",
    )
    orphaned = tuple(workspace.root.glob(".aeroone-rotation-*.tmp"))

    # When: a new process resumes through the validated journal and bootstrap binding.
    assert crashed.returncode != 0
    assert not (workspace.root / ".env").exists()
    assert len(orphaned) == 1
    assert orphaned[0].stat().st_size > 0
    resumed = invoke_rotation(workspace)

    # Then: the owned plaintext orphan is gone and the same rotation completes once.
    assert resumed.returncode == 0, resumed.stderr
    assert tuple(workspace.root.glob(".aeroone-rotation-*.tmp")) == ()
