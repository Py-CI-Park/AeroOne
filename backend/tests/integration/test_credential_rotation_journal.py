from __future__ import annotations

import os
from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import reset_settings_cache
from app.db.session import reset_db_caches
from app.main import create_app
from app.modules.auth.models import User
from app.operations.credential_bundle import load_credential_bundle
from tests.rotation_harness import (
    create_synthetic_workspace,
    env_value,
    has_exact_secure_acl,
    invoke_rotation,
)


def test_torn_current_journal_recovers_from_valid_previous_generation(tmp_path: Path) -> None:
    # Given: the database commit was journaled with a retained previous generation.
    workspace = create_synthetic_workspace(tmp_path)
    failed = invoke_rotation(workspace, ("-Failpoint", "after_db_commit"))
    secure_root = workspace.root / ".rotation-secure"
    current = secure_root / "rotation-state.json.dpapi"
    previous = secure_root / "rotation-state.previous.json.dpapi"
    assert failed.returncode != 0
    assert current.exists()
    assert previous.exists()

    # When: a crash-torn current generation is encountered on resume.
    corrupted = bytearray(current.read_bytes())
    corrupted[len(corrupted) // 2] ^= 1
    current.write_bytes(corrupted)
    resumed = invoke_rotation(workspace)

    # Then: the valid previous generation reconciles the committed database and finishes once.
    assert resumed.returncode == 0, resumed.stderr


def test_missing_live_root_after_quarantine_is_reconciled_from_journal(tmp_path: Path) -> None:
    # Given: the process stopped after the DB commit and then died after moving the root env.
    workspace = create_synthetic_workspace(tmp_path)
    failed = invoke_rotation(workspace, ("-Failpoint", "after_db_commit"))
    root_env = workspace.root / ".env"
    quarantined = (
        workspace.root
        / ".rotation-secure"
        / "quarantine"
        / "environment"
        / "root.env.before-rotation"
    )
    assert failed.returncode != 0
    os.replace(root_env, quarantined)

    # When: a new process resumes with no live root environment file.
    resumed = invoke_rotation(workspace)

    # Then: validated journal artifacts repair the seam and complete the same rotation.
    assert resumed.returncode == 0, resumed.stderr


def test_process_crash_after_credential_move_reconciles_final_artifact(tmp_path: Path) -> None:
    # Given: the process is killed after the credential bundle move but before journal advance.
    workspace = create_synthetic_workspace(tmp_path)
    crashed = invoke_rotation(workspace, internal_crashpoint="crash_after_credentials_move")
    secure_root = workspace.root / ".rotation-secure"
    pending = secure_root / "pending" / "credentials.dpapi"
    final = secure_root / "1.12.3-credentials.dpapi"
    assert crashed.returncode != 0
    assert not pending.exists()
    assert final.exists()

    # When: a new PowerShell process resumes the same journal.
    resumed = invoke_rotation(workspace)

    # Then: the final artifact binding advances the journal without a second rotation.
    assert resumed.returncode == 0, resumed.stderr


def test_process_crash_after_quarantine_finalize_preserves_source_until_verified(
    tmp_path: Path,
) -> None:
    # Given: the process is killed after quarantine finalize but before source deletion.
    workspace = create_synthetic_workspace(tmp_path)
    root_env = workspace.root / ".env"
    original = root_env.read_bytes()
    crashed = invoke_rotation(
        workspace,
        internal_crashpoint="crash_after_root_quarantine_finalize",
    )
    quarantined = (
        workspace.root
        / ".rotation-secure"
        / "quarantine"
        / "environment"
        / "root.env.before-rotation"
    )

    # When: the process dies at the cross-volume-safe finalize seam.
    assert crashed.returncode != 0
    assert root_env.read_bytes() == original
    assert quarantined.read_bytes() == original
    resumed = invoke_rotation(workspace)

    # Then: resume verifies the finalized copy, deletes the source, and promotes once.
    assert resumed.returncode == 0, resumed.stderr


def test_process_crash_during_quarantine_copy_removes_only_verified_orphan_temp(
    tmp_path: Path,
) -> None:
    # Given: the process is killed after flushing only half of a secure quarantine temp.
    workspace = create_synthetic_workspace(tmp_path)
    root_env = workspace.root / ".env"
    original = root_env.read_bytes()
    crashed = invoke_rotation(
        workspace,
        internal_crashpoint="crash_during_root_quarantine_copy",
    )
    quarantine_directory = workspace.root / ".rotation-secure" / "quarantine" / "environment"
    orphaned = tuple(quarantine_directory.glob(".aeroone-rotation-*.tmp"))

    # When: the partial temp is inspected before restart and then resume is invoked.
    assert crashed.returncode != 0
    assert root_env.read_bytes() == original
    assert len(orphaned) == 1
    assert 0 < orphaned[0].stat().st_size < len(original)
    resumed = invoke_rotation(workspace)

    # Then: preflight removes the owned orphan and the verified copy pipeline completes.
    assert resumed.returncode == 0, resumed.stderr
    assert tuple(quarantine_directory.glob(".aeroone-rotation-*.tmp")) == ()


def test_existing_final_credential_blocks_before_database_or_environment_mutation(
    tmp_path: Path,
) -> None:
    workspace = create_synthetic_workspace(tmp_path)
    root_env = workspace.root / ".env"
    before_env = root_env.read_bytes()
    secure_root = workspace.root / ".rotation-secure"
    secure_root.mkdir()
    (secure_root / "1.12.3-credentials.dpapi").write_bytes(b"collision")

    completed = invoke_rotation(workspace)

    assert completed.returncode != 0
    assert "credential-destination-exists" in completed.stderr
    assert root_env.read_bytes() == before_env
    with Session(create_engine(workspace.database_url)) as session:
        assert session.scalar(select(User.session_version)) == 2


def test_process_crash_before_initial_journal_recovers_owned_secure_root(tmp_path: Path) -> None:
    workspace = create_synthetic_workspace(tmp_path)

    crashed = invoke_rotation(workspace, internal_crashpoint="crash_after_secure_root_init")
    resumed = invoke_rotation(workspace)

    assert crashed.returncode != 0
    assert resumed.returncode == 0, resumed.stderr


def test_unexpected_secure_output_blocks_resume_before_live_environment_mutation(
    tmp_path: Path,
) -> None:
    workspace = create_synthetic_workspace(tmp_path)
    failed = invoke_rotation(workspace, ("-Failpoint", "after_db_commit"))
    root_env = workspace.root / ".env"
    before_env = root_env.read_bytes()
    unexpected = workspace.root / ".rotation-secure" / "pending" / "unexpected.bin"
    unexpected.write_bytes(b"unexpected")

    resumed = invoke_rotation(workspace)

    assert failed.returncode != 0
    assert resumed.returncode != 0
    assert "unexpected-secure-output" in resumed.stderr
    assert root_env.read_bytes() == before_env


def test_swapped_pending_environment_artifacts_fail_before_live_mutation(tmp_path: Path) -> None:
    workspace = create_synthetic_workspace(tmp_path)
    failed = invoke_rotation(workspace, ("-Failpoint", "after_db_commit"))
    pending = workspace.root / ".rotation-secure" / "pending"
    root_pending = pending / "root-env.dpapi"
    backend_pending = pending / "backend-env.dpapi"
    swap = pending / "swap.dpapi"
    before_root_env = (workspace.root / ".env").read_bytes()
    os.replace(root_pending, swap)
    os.replace(backend_pending, root_pending)
    os.replace(swap, backend_pending)

    resumed = invoke_rotation(workspace)

    assert failed.returncode != 0
    assert resumed.returncode != 0
    assert (workspace.root / ".env").read_bytes() == before_root_env


def test_restored_pre_rotation_database_cannot_reuse_completed_rotation_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = create_synthetic_workspace(tmp_path)
    database_path = Path(workspace.database_url.removeprefix("sqlite:///"))
    prepared = invoke_rotation(workspace, ("-Failpoint", "before_db_commit"))
    assert prepared.returncode != 0
    assert "python-test-failpoint" in prepared.stderr
    ordinary_backup = tmp_path / "ordinary-pre-rotation-backup.db"
    with (
        sqlite3.connect(database_path) as source,
        sqlite3.connect(ordinary_backup) as destination,
    ):
        source.backup(destination)
    completed = invoke_rotation(workspace)
    assert completed.returncode == 0, completed.stderr
    secure_root = workspace.root / ".rotation-secure"
    final_bundle = load_credential_bundle(secure_root / "1.12.3-credentials.dpapi")
    final_admin = next(
        credential
        for credential in final_bundle.users
        if credential.username == final_bundle.admin_username
    )
    before_root_env = (workspace.root / ".env").read_bytes()
    for suffix in ("-wal", "-shm"):
        database_path.with_name(database_path.name + suffix).unlink(missing_ok=True)
    database_path.write_bytes(ordinary_backup.read_bytes())

    rerun = invoke_rotation(workspace)

    assert rerun.returncode != 0
    assert "python-invariant-violation" in rerun.stderr
    assert (workspace.root / ".env").read_bytes() == before_root_env
    with Session(create_engine(workspace.database_url)) as session:
        assert session.scalar(select(User.session_version)) == 2

    archived = invoke_rotation(
        workspace,
        (
            "-RestoreConfirmation",
            "ARCHIVE_COMPLETED_ROTATION_AND_START_NEW",
        ),
    )
    history_target = workspace.root / ".rotation-history" / str(final_bundle.rotation_id)
    assert archived.returncode == 0, archived.stderr
    assert "status=archived" in archived.stdout
    assert not secure_root.exists()
    assert history_target.exists()
    assert has_exact_secure_acl(history_target)
    archived_manifest = history_target / "quarantine" / "quarantine-manifest.json"
    assert "2027-07-10T00:00:00+09:00" in archived_manifest.read_text(encoding="utf-8")

    rotated = invoke_rotation(workspace)
    assert rotated.returncode == 0, rotated.stderr
    replacement_bundle = load_credential_bundle(secure_root / "1.12.3-credentials.dpapi")
    assert replacement_bundle.rotation_id != final_bundle.rotation_id
    replacement_admin = next(
        credential
        for credential in replacement_bundle.users
        if credential.username == replacement_bundle.admin_username
    )
    runtime_root = tmp_path / "restored-runtime"
    for key, value in {
        "APP_ENV": "test",
        "DATABASE_URL": workspace.database_url,
        "JWT_SECRET_KEY": env_value(workspace.root / ".env", "JWT_SECRET_KEY"),
        "ADMIN_USERNAME": replacement_bundle.admin_username,
        "ADMIN_PASSWORD": replacement_admin.password,
        "NEWSLETTER_IMPORT_ROOT_CONTAINER": str(runtime_root / "newsletter"),
        "CIVIL_AIRCRAFT_ROOT": str(runtime_root / "civil"),
        "DOCUMENT_ROOT": str(runtime_root / "document"),
        "NSA_ROOT": str(runtime_root / "nsa"),
        "STORAGE_ROOT": str(runtime_root / "storage"),
    }.items():
        monkeypatch.setenv(key, value)
    reset_settings_cache()
    reset_db_caches()
    with TestClient(create_app()) as client:
        old_login = client.post(
            "/api/v1/auth/login",
            json={
                "username": replacement_bundle.admin_username,
                "password": workspace.admin_password,
            },
        )
        archived_login = client.post(
            "/api/v1/auth/login",
            json={
                "username": replacement_bundle.admin_username,
                "password": final_admin.password,
            },
        )
        new_login = client.post(
            "/api/v1/auth/login",
            json={
                "username": replacement_bundle.admin_username,
                "password": replacement_admin.password,
            },
        )
    assert old_login.status_code == 401
    assert archived_login.status_code == 401
    assert new_login.status_code == 200
    reset_settings_cache()
    reset_db_caches()
