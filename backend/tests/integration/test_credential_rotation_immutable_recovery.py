from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess

import pytest

from app.operations.credential_bundle import load_credential_bundle
from app.operations.sqlite_recovery import (
    RecoveryErrorCode,
    SqliteRecoveryError,
    confirm_database_matches_recovery,
    create_database_recovery,
)
from tests.rotation_harness import create_synthetic_workspace, invoke_rotation


def _immutable_recovery(root: Path) -> Path:
    candidates = tuple((root / ".rotation-secure" / "recovery").glob("*.dpapi"))
    assert len(candidates) == 1
    recovery = candidates[0]
    prefix = "aeroone-db-before-rotation."
    assert recovery.name.startswith(prefix)
    assert recovery.name.endswith(".dpapi")
    assert len(recovery.name.removeprefix(prefix).removesuffix(".dpapi")) == 36
    return recovery


def _identity_and_digest(path: Path) -> tuple[int, str, bytes]:
    payload = path.read_bytes()
    return path.stat().st_ino, hashlib.sha256(payload).hexdigest(), payload


def _copy_exact_acl(source: Path, destination: Path) -> None:
    destination.write_bytes(source.read_bytes())
    environment = os.environ.copy()
    environment["AEROONE_ACL_DESTINATION"] = str(destination)
    module_root = Path(__file__).resolve().parents[3] / "scripts" / "credential_rotation"
    environment["AEROONE_SECURE_IO_MODULE"] = str(module_root / "Rotation.SecureIO.psm1")
    environment["AEROONE_SECURITY_MODULE"] = str(module_root / "Rotation.Security.psm1")
    completed = subprocess.run(
        (
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "Import-Module $env:AEROONE_SECURE_IO_MODULE -Force -DisableNameChecking; "
            "Import-Module $env:AEROONE_SECURITY_MODULE -Force -DisableNameChecking; "
            "Set-SecureFileAcl -Path $env:AEROONE_ACL_DESTINATION",
        ),
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert completed.returncode == 0, completed.stderr


def test_kill_after_database_commit_advances_only_journal_on_resume(tmp_path: Path) -> None:
    # Given: the process is killed after SQLite commit and before db_committed journal advance.
    workspace = create_synthetic_workspace(tmp_path)
    crashed = invoke_rotation(workspace, internal_crashpoint="crash_after_database_commit")
    recovery = _immutable_recovery(workspace.root)
    original = _identity_and_digest(recovery)

    # When: resume finds the exact committed ledger/post-state under BEGIN IMMEDIATE.
    resumed = invoke_rotation(workspace)

    # Then: only the journal advances and the original recovery object remains byte-identical.
    assert crashed.returncode != 0
    assert resumed.returncode == 0, resumed.stderr
    assert _identity_and_digest(recovery) == original


def test_kill_after_recovery_publish_reuses_versioned_artifact_before_journal(
    tmp_path: Path,
) -> None:
    # Given: an atomic versioned recovery publish followed immediately by process death.
    workspace = create_synthetic_workspace(tmp_path)
    crashed = invoke_rotation(workspace, internal_crashpoint="crash_after_recovery_publish")
    recovery = _immutable_recovery(workspace.root)
    original = _identity_and_digest(recovery)
    assert not (workspace.root / ".rotation-secure" / "rotation-state.json.dpapi").exists()

    # When: a fresh process reinitializes prepared state from bound immutable artifacts.
    resumed = invoke_rotation(workspace)

    # Then: recovery is reused without delete/re-encrypt and the rotation completes once.
    assert crashed.returncode != 0
    assert resumed.returncode == 0, resumed.stderr
    assert _identity_and_digest(recovery) == original


def test_torn_prepared_fallback_with_committed_ledger_preserves_recovery(
    tmp_path: Path,
) -> None:
    # Given: a committed ledger, prepared previous journal, and torn current journal.
    workspace = create_synthetic_workspace(tmp_path)
    crashed = invoke_rotation(workspace, internal_crashpoint="crash_after_database_commit")
    secure_root = workspace.root / ".rotation-secure"
    current = secure_root / "rotation-state.json.dpapi"
    previous = secure_root / "rotation-state.previous.json.dpapi"
    _copy_exact_acl(current, previous)
    corrupted = bytearray(current.read_bytes())
    corrupted[len(corrupted) // 2] ^= 1
    current.write_bytes(corrupted)
    recovery = _immutable_recovery(workspace.root)
    original = _identity_and_digest(recovery)

    # When: resume falls back to the prepared generation and detects the exact ledger.
    resumed = invoke_rotation(workspace)

    # Then: journal reconciliation completes without generating a post-state recovery.
    assert crashed.returncode != 0
    assert resumed.returncode == 0, resumed.stderr
    assert _identity_and_digest(recovery) == original


def test_restore_confirmation_rejects_post_state_masquerading_as_recovery(
    tmp_path: Path,
) -> None:
    # Given: a completed rotation and a new recovery envelope captured from its post-state.
    workspace = create_synthetic_workspace(tmp_path)
    completed = invoke_rotation(workspace)
    assert completed.returncode == 0, completed.stderr
    secure_root = workspace.root / ".rotation-secure"
    bundle = load_credential_bundle(secure_root / "credentials.dpapi")
    database_path = Path(workspace.database_url.removeprefix("sqlite:///"))
    masquerade = tmp_path / "post-state.dpapi"
    create_database_recovery(
        database_path,
        masquerade,
        bundle.rotation_id,
        bundle.database_id,
    )

    # When: restore confirmation compares the post-state database to that masquerade.
    with pytest.raises(SqliteRecoveryError) as captured:
        confirm_database_matches_recovery(
            database_path,
            masquerade,
            bundle.rotation_id,
            bundle.database_id,
        )

    # Then: a same-byte snapshot containing the committed ledger is still rejected.
    assert captured.value.code is RecoveryErrorCode.RESTORE_STATE_MISMATCH
