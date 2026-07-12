from __future__ import annotations

import os
from pathlib import Path
import secrets
import stat
import subprocess

from fastapi.testclient import TestClient
import jwt
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import reset_settings_cache
from app.core.security import create_access_token, decode_access_token, verify_password
from app.db.session import reset_db_caches
from app.main import create_app
from app.modules.admin.models import UserSessionActivity
from app.modules.auth.models import User
from app.operations.credential_bundle import load_credential_bundle
from tests.rotation_harness import (
    SyntheticWorkspace,
    create_synthetic_workspace as _create_synthetic_workspace,
    env_value as _env_value,
    invoke_rotation as _invoke_rotation,
)


@pytest.mark.parametrize(
    "failpoint",
    ("after_db_commit", "after_root_env_promote", "before_credentials_promote"),
)
def test_postcommit_failpoints_resume_forward_without_second_rotation(
    tmp_path: Path,
    failpoint: str,
) -> None:
    # Given: a fresh synthetic workspace and one supported postcommit failpoint.
    workspace = _create_synthetic_workspace(tmp_path)

    # When: execution stops after commit and the same journal is resumed twice.
    failed = _invoke_rotation(workspace, ("-Failpoint", failpoint))
    resumed = _invoke_rotation(workspace)
    repeated = _invoke_rotation(workspace)

    # Then: forward recovery completes once without exposing or restoring old credentials.
    combined_output = (
        failed.stdout
        + failed.stderr
        + resumed.stdout
        + resumed.stderr
        + repeated.stdout
        + repeated.stderr
    )
    assert failed.returncode != 0
    assert f"injected_{failpoint}" in failed.stderr
    assert resumed.returncode == 0, resumed.stderr
    assert repeated.returncode == 0, repeated.stderr
    assert workspace.jwt_secret not in combined_output
    assert workspace.admin_password not in combined_output
    with Session(create_engine(workspace.database_url)) as session:
        user = session.scalar(select(User).where(User.username == "admin"))
        assert user is not None
        assert user.session_version == 3
        assert not verify_password(workspace.admin_password, user.password_hash)
        assert session.scalar(select(func.count()).select_from(UserSessionActivity)) == 0
    bundle_path = workspace.root / ".rotation-secure" / "credentials.dpapi"
    bundle = load_credential_bundle(bundle_path)
    admin_credential = next(item for item in bundle.users if item.username == bundle.admin_username)
    assert _env_value(workspace.root / ".env", "ADMIN_PASSWORD") == admin_credential.password
    assert (
        _env_value(workspace.root / "backend" / ".env", "ADMIN_PASSWORD")
        == admin_credential.password
    )


def test_unknown_credential_key_blocks_before_secure_output(tmp_path: Path) -> None:
    # Given: an otherwise valid scope with one provider key outside the exact allow-list.
    workspace = _create_synthetic_workspace(tmp_path)
    unknown_secret = secrets.token_urlsafe(24)
    for env_path in (workspace.root / ".env", workspace.root / "backend" / ".env"):
        env_path.write_text(
            env_path.read_text(encoding="utf-8") + f"EXTERNAL_API_TOKEN={unknown_secret}\n",
            encoding="utf-8",
        )

    # When: dry-run validates the credential inventory.
    completed = _invoke_rotation(workspace, ("-DryRun",))

    # Then: the unknown key blocks without creating a recovery root or printing its value.
    assert completed.returncode != 0
    assert "unknown-env-key" in completed.stderr
    assert unknown_secret not in completed.stdout + completed.stderr
    assert not (workspace.root / ".rotation-secure").exists()


@pytest.mark.parametrize(
    "unexpected_key",
    ("SMTP_PASSPHRASE", "SERVICE_CREDENTIAL", "SIGNING_SECRET", "UNEXPECTED_FLAG"),
)
def test_any_undocumented_environment_key_is_rejected(
    tmp_path: Path,
    unexpected_key: str,
) -> None:
    # Given: a valid workspace with one key outside the documented profile.
    workspace = _create_synthetic_workspace(tmp_path)
    unexpected_value = secrets.token_urlsafe(24)
    for env_path in (workspace.root / ".env", workspace.root / "backend" / ".env"):
        env_path.write_text(
            env_path.read_text(encoding="utf-8") + f"{unexpected_key}={unexpected_value}\n",
            encoding="utf-8",
        )

    # When: dry-run parses the environment profile.
    completed = _invoke_rotation(workspace, ("-DryRun",))

    # Then: the unknown key is blocked without revealing its value.
    assert completed.returncode != 0
    assert "unknown-env-key" in completed.stderr
    assert unexpected_value not in completed.stdout + completed.stderr
    assert not (workspace.root / ".rotation-secure").exists()


def test_insecure_pending_acl_blocks_postcommit_resume(tmp_path: Path) -> None:
    # Given: a committed journal whose pending environment ACL gains an unauthorized reader.
    workspace = _create_synthetic_workspace(tmp_path)
    failed = _invoke_rotation(workspace, ("-Failpoint", "after_db_commit"))
    assert failed.returncode != 0
    pending_env = workspace.root / ".rotation-secure" / "pending" / "root-env.dpapi"
    acl_change = subprocess.run(
        ["icacls.exe", str(pending_env), "/grant", "*S-1-5-32-545:R"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert acl_change.returncode == 0

    # When: forward resume validates every protected input before promotion.
    resumed = _invoke_rotation(workspace)

    # Then: insecure ACL fails closed and old environments remain active.
    assert resumed.returncode != 0
    assert "insecure-acl" in resumed.stderr
    assert _env_value(workspace.root / ".env", "JWT_SECRET_KEY") == workspace.jwt_secret
    assert _env_value(workspace.root / "backend" / ".env", "JWT_SECRET_KEY") == workspace.jwt_secret


def test_exact_acl_rejects_expected_sids_with_wrong_directory_inheritance(
    tmp_path: Path,
) -> None:
    workspace = _create_synthetic_workspace(tmp_path)
    failed = _invoke_rotation(workspace, ("-Failpoint", "after_db_commit"))
    assert failed.returncode != 0
    pending_directory = workspace.root / ".rotation-secure" / "pending"
    command = (
        "$current=[Security.Principal.WindowsIdentity]::GetCurrent().User;"
        "$system=New-Object Security.Principal.SecurityIdentifier('S-1-5-18');"
        "$acl=New-Object Security.AccessControl.DirectorySecurity;"
        "$acl.SetOwner($current);$acl.SetAccessRuleProtection($true,$false);"
        "$allow=[Security.AccessControl.AccessControlType]::Allow;"
        "$none=[Security.AccessControl.InheritanceFlags]::None;"
        "$prop=[Security.AccessControl.PropagationFlags]::None;"
        "$acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule"
        "($current,'FullControl',$none,$prop,$allow)));"
        "$acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule"
        "($system,'FullControl',$none,$prop,$allow)));"
        "(Get-Item -LiteralPath $env:AEROONE_ACL_TEST_PATH -Force).SetAccessControl($acl)"
    )
    process_environment = os.environ.copy()
    process_environment["AEROONE_ACL_TEST_PATH"] = str(pending_directory)
    changed = subprocess.run(
        ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
        check=False,
        capture_output=True,
        text=True,
        env=process_environment,
    )
    assert changed.returncode == 0, changed.stderr

    resumed = _invoke_rotation(workspace)

    assert resumed.returncode != 0
    assert "insecure-acl" in resumed.stderr
    assert _env_value(workspace.root / ".env", "JWT_SECRET_KEY") == workspace.jwt_secret


def test_corrupt_pending_resume_fails_without_moving_active_environments(tmp_path: Path) -> None:
    # Given: a postcommit journal whose ACL-valid root pending artifact is corrupted.
    workspace = _create_synthetic_workspace(tmp_path)
    failed = _invoke_rotation(workspace, ("-Failpoint", "after_db_commit"))
    assert failed.returncode != 0
    root_env = workspace.root / ".env"
    backend_env = workspace.root / "backend" / ".env"
    active_root = root_env.read_bytes()
    active_backend = backend_env.read_bytes()
    pending_env = workspace.root / ".rotation-secure" / "pending" / "root-env.dpapi"
    corrupted = bytearray(pending_env.read_bytes())
    corrupted[-1] ^= 1
    pending_env.write_bytes(corrupted)

    # When: resume encounters the corrupted pending artifact.
    resumed = _invoke_rotation(workspace)

    # Then: validation fails before either active environment is moved.
    assert resumed.returncode != 0
    assert root_env.read_bytes() == active_root
    assert backend_env.read_bytes() == active_backend


def test_read_only_database_blocks_before_environment_promotion(tmp_path: Path) -> None:
    # Given: a valid scope whose canonical SQLite file is read-only.
    workspace = _create_synthetic_workspace(tmp_path)
    database_path = Path(workspace.database_url.removeprefix("sqlite:///"))
    before_root_env = (workspace.root / ".env").read_bytes()
    before_backend_env = (workspace.root / "backend" / ".env").read_bytes()
    os.chmod(database_path, stat.S_IREAD)

    # When: execute reaches the single database transaction.
    try:
        completed = _invoke_rotation(workspace)
    finally:
        os.chmod(database_path, stat.S_IREAD | stat.S_IWRITE)

    # Then: the transaction fails before either environment is promoted.
    assert completed.returncode != 0
    assert "python-storage-failure" in completed.stderr
    assert (workspace.root / ".env").read_bytes() == before_root_env
    assert (workspace.root / "backend" / ".env").read_bytes() == before_backend_env
    assert workspace.jwt_secret not in completed.stdout + completed.stderr
    assert workspace.admin_password not in completed.stdout + completed.stderr


def test_unknown_test_root_is_rejected_without_discovery(tmp_path: Path) -> None:
    # Given: a directory without the exact test-root marker or AeroOne scope files.
    unknown_root = tmp_path / "unknown"
    unknown_root.mkdir()
    workspace = SyntheticWorkspace(
        root=unknown_root,
        database_url="",
        jwt_secret="",
        admin_password="",
    )

    # When: test mode is pointed at that unknown root.
    completed = _invoke_rotation(workspace, ("-DryRun",))

    # Then: validation stops before creating or discovering any secure output.
    assert completed.returncode != 0
    assert "unknown-test-root" in completed.stderr
    assert list(unknown_root.iterdir()) == []


def test_old_auth_is_rejected_and_dpapi_admin_login_succeeds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a known-old token/password and a completed synthetic rotation.
    workspace = _create_synthetic_workspace(tmp_path)
    old_token = create_access_token(
        workspace.jwt_secret,
        "1",
        "admin",
        secrets.token_urlsafe(24),
        30,
        2,
    )
    completed = _invoke_rotation(workspace)
    assert completed.returncode == 0, completed.stderr
    bundle = load_credential_bundle(
        workspace.root / ".rotation-secure" / "credentials.dpapi"
    )
    admin_credential = next(item for item in bundle.users if item.username == bundle.admin_username)
    new_jwt = _env_value(workspace.root / ".env", "JWT_SECRET_KEY")
    runtime_root = tmp_path / "runtime"
    for key, value in {
        "APP_ENV": "test",
        "DATABASE_URL": workspace.database_url,
        "JWT_SECRET_KEY": new_jwt,
        "ADMIN_USERNAME": bundle.admin_username,
        "ADMIN_PASSWORD": admin_credential.password,
        "NEWSLETTER_IMPORT_ROOT_CONTAINER": str(runtime_root / "newsletter"),
        "CIVIL_AIRCRAFT_ROOT": str(runtime_root / "civil"),
        "DOCUMENT_ROOT": str(runtime_root / "document"),
        "NSA_ROOT": str(runtime_root / "nsa"),
        "STORAGE_ROOT": str(runtime_root / "storage"),
    }.items():
        monkeypatch.setenv(key, value)
    reset_settings_cache()
    reset_db_caches()

    # When: known-old auth and the DPAPI-recovered new admin auth hit the real login surface.
    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(old_token, new_jwt)
    with TestClient(create_app()) as client:
        old_login = client.post(
            "/api/v1/auth/login",
            json={"username": bundle.admin_username, "password": workspace.admin_password},
        )
        new_login = client.post(
            "/api/v1/auth/login",
            json={"username": bundle.admin_username, "password": admin_credential.password},
        )

    # Then: old credentials receive 401 and the protected replacement receives 200.
    assert old_login.status_code == 401
    assert new_login.status_code == 200
    reset_settings_cache()
    reset_db_caches()
