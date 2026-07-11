from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.modules.admin.models import UserSessionActivity
from app.modules.auth.models import User
from app.operations.credential_bundle import load_credential_bundle
from tests.rotation_harness import (
    create_synthetic_workspace,
    env_value,
    has_exact_secure_acl,
    invoke_rotation,
)


def test_dry_run_validates_exact_scope_without_writing_or_disclosing_secrets(
    tmp_path: Path,
) -> None:
    # Given: a synthetic exact-key workspace and canonical SQLite database.
    workspace = create_synthetic_workspace(tmp_path)
    before_root_env = (workspace.root / ".env").read_bytes()
    before_backend_env = (workspace.root / "backend" / ".env").read_bytes()

    # When: the incident orchestrator validates in test-only dry-run mode.
    completed = invoke_rotation(workspace, ("-DryRun",))

    # Then: validation succeeds without mutations or secret-bearing output.
    combined_output = completed.stdout + completed.stderr
    assert completed.returncode == 0
    assert "status=dry-run scope=valid users=1" in completed.stdout
    assert workspace.jwt_secret not in combined_output
    assert workspace.admin_password not in combined_output
    assert (workspace.root / ".env").read_bytes() == before_root_env
    assert (workspace.root / "backend" / ".env").read_bytes() == before_backend_env


def test_before_db_commit_rolls_back_then_resumes_forward_exactly_once(tmp_path: Path) -> None:
    # Given: an exact synthetic workspace with one old credential and one live session.
    workspace = create_synthetic_workspace(tmp_path)
    root_env_path = workspace.root / ".env"
    backend_env_path = workspace.root / "backend" / ".env"
    before_root_env = root_env_path.read_bytes()
    before_backend_env = backend_env_path.read_bytes()

    # When: the precommit failpoint fires and two subsequent runs resume the same journal.
    failed = invoke_rotation(workspace, ("-Failpoint", "before_db_commit"))
    with create_engine(workspace.database_url).connect() as connection:
        failed_version = connection.scalar(
            select(User.session_version).where(User.username == "admin")
        )
        failed_sessions = connection.scalar(select(func.count()).select_from(UserSessionActivity))
    failed_root_env = root_env_path.read_bytes()
    failed_backend_env = backend_env_path.read_bytes()
    resumed = invoke_rotation(workspace)
    repeated = invoke_rotation(workspace)

    # Then: rollback kept old state, resume completed, and repetition did not rotate again.
    combined_output = (
        failed.stdout
        + failed.stderr
        + resumed.stdout
        + resumed.stderr
        + repeated.stdout
        + repeated.stderr
    )
    assert failed.returncode != 0
    assert "python-test-failpoint" in failed.stderr
    assert failed_version == 2
    assert failed_sessions == 1
    assert failed_root_env == before_root_env
    assert failed_backend_env == before_backend_env
    assert resumed.returncode == 0, resumed.stderr
    assert repeated.returncode == 0, repeated.stderr
    assert before_root_env != root_env_path.read_bytes()
    assert before_backend_env != backend_env_path.read_bytes()
    assert workspace.jwt_secret not in combined_output
    assert workspace.admin_password not in combined_output
    with Session(create_engine(workspace.database_url)) as session:
        user = session.scalar(select(User).where(User.username == "admin"))
        assert user is not None
        assert user.session_version == 3
        assert not verify_password(workspace.admin_password, user.password_hash)
        assert session.scalar(select(func.count()).select_from(UserSessionActivity)) == 0
    final_bundle_path = workspace.root / ".rotation-secure" / "credentials.dpapi"
    bundle = load_credential_bundle(final_bundle_path)
    admin_credential = next(item for item in bundle.users if item.username == bundle.admin_username)
    assert env_value(root_env_path, "JWT_SECRET_KEY") == bundle.jwt_secret_key
    assert env_value(backend_env_path, "JWT_SECRET_KEY") == bundle.jwt_secret_key
    assert env_value(root_env_path, "ADMIN_PASSWORD") == admin_credential.password
    assert env_value(backend_env_path, "ADMIN_PASSWORD") == admin_credential.password
    secure_root = workspace.root / ".rotation-secure"
    recovery_paths = tuple(
        (secure_root / "recovery").glob("aeroone-db-before-rotation.*.dpapi")
    )
    assert len(recovery_paths) == 1
    protected_paths = (
        secure_root,
        secure_root / "recovery",
        recovery_paths[0],
        secure_root / "rotation-state.json.dpapi",
        final_bundle_path,
        secure_root / "quarantine" / "environment" / "root.env.before-rotation",
        secure_root / "quarantine" / "environment" / "backend.env.before-rotation",
        secure_root / "quarantine" / "quarantine-manifest.json",
    )
    acl_results = tuple(has_exact_secure_acl(path) for path in protected_paths)
    assert acl_results == (True,) * len(protected_paths)
    manifest = json.loads(
        (secure_root / "quarantine" / "quarantine-manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["retention"] == "2027-07-10T00:00:00+09:00"
    assert {entry["source"] for entry in manifest["entries"]} == {".env", "backend/.env"}
    assert all(entry["category"] == "environment" for entry in manifest["entries"])
    assert all(len(entry["sha256"]) == 64 for entry in manifest["entries"])
    pending_root_env = (secure_root / "pending" / "root-env.dpapi").read_bytes()
    assert bundle.jwt_secret_key.encode() not in pending_root_env
    assert admin_credential.password.encode() not in pending_root_env

