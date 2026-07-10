from __future__ import annotations

from pathlib import Path
import secrets
import sqlite3

from app.core.security import hash_password
from app.operations.credential_bundle import load_credential_bundle
from app.operations.sqlite_recovery import load_database_recovery
from tests.rotation_harness import create_synthetic_workspace, invoke_rotation


def test_database_recovery_snapshot_includes_committed_wal_frames(tmp_path: Path) -> None:
    # Given: a synthetic database with a committed user row retained only in its WAL.
    workspace = create_synthetic_workspace(tmp_path)
    database_path = Path(workspace.database_url.removeprefix("sqlite:///"))
    writer = sqlite3.connect(database_path)
    try:
        assert writer.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute(
            "INSERT INTO users "
            "(username, password_hash, role, is_active, session_version) "
            "VALUES (?, ?, ?, ?, ?)",
            ("wal-admin", hash_password(secrets.token_urlsafe(24)), "admin", 1, 0),
        )
        writer.commit()
        assert database_path.with_name(f"{database_path.name}-wal").exists()

        # When: execution prepares recovery and stops before the credential commit.
        completed = invoke_rotation(workspace, ("-Failpoint", "before_db_commit"))
        recovery_path = (
            workspace.root / ".rotation-secure" / "recovery" / "aeroone-db-before-rotation.dpapi"
        )
        assert recovery_path.exists(), completed.stderr
        bundle = load_credential_bundle(
            workspace.root / ".rotation-secure" / "pending" / "credentials.dpapi"
        )
        snapshot = load_database_recovery(
            recovery_path,
            bundle.rotation_id,
            bundle.database_id,
        )

        # Then: the protected logical snapshot contains the WAL row and is integral.
        recovered = sqlite3.connect(":memory:")
        try:
            recovered.deserialize(snapshot)
            usernames = tuple(
                row[0] for row in recovered.execute("SELECT username FROM users ORDER BY username")
            )
            assert usernames == ("admin", "wal-admin")
            assert recovered.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        finally:
            recovered.close()
            snapshot[:] = b"\0" * len(snapshot)
        assert completed.returncode != 0
    finally:
        writer.close()
