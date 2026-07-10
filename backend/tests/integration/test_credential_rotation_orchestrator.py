from __future__ import annotations

import json
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
    has_exact_secure_acl,
    invoke_rotation as _invoke_rotation,
)


def test_dry_run_validates_exact_scope_without_writing_or_disclosing_secrets(tmp_path: Path) -> None:
    # Given: a synthetic exact-key workspace and canonical SQLite database.
    workspace = _create_synthetic_workspace(tmp_path)
    before_root_env = (workspace.root / '.env').read_bytes()
    before_backend_env = (workspace.root / 'backend' / '.env').read_bytes()

    # When: the incident orchestrator validates in test-only dry-run mode.
    completed = _invoke_rotation(workspace, ('-DryRun',))

    # Then: validation succeeds without mutations or secret-bearing output.
    combined_output = completed.stdout + completed.stderr
    assert completed.returncode == 0
    assert 'status=dry-run scope=valid users=1' in completed.stdout
    assert workspace.jwt_secret not in combined_output
    assert workspace.admin_password not in combined_output
    assert (workspace.root / '.env').read_bytes() == before_root_env
    assert (workspace.root / 'backend' / '.env').read_bytes() == before_backend_env


def test_before_db_commit_rolls_back_then_resumes_forward_exactly_once(tmp_path: Path) -> None:
    # Given: an exact synthetic workspace with one old credential and one live session.
    workspace = _create_synthetic_workspace(tmp_path)
    root_env_path = workspace.root / '.env'
    backend_env_path = workspace.root / 'backend' / '.env'
    before_root_env = root_env_path.read_bytes()
    before_backend_env = backend_env_path.read_bytes()

    # When: the precommit failpoint fires and two subsequent runs resume the same journal.
    failed = _invoke_rotation(workspace, ('-Failpoint', 'before_db_commit'))
    with create_engine(workspace.database_url).connect() as connection:
        failed_version = connection.scalar(select(User.session_version).where(User.username == 'admin'))
        failed_sessions = connection.scalar(select(func.count()).select_from(UserSessionActivity))
    failed_root_env = root_env_path.read_bytes()
    failed_backend_env = backend_env_path.read_bytes()
    resumed = _invoke_rotation(workspace)
    repeated = _invoke_rotation(workspace)

    # Then: rollback kept old state, resume completed, and repetition did not rotate again.
    combined_output = failed.stdout + failed.stderr + resumed.stdout + resumed.stderr + repeated.stdout + repeated.stderr
    assert failed.returncode != 0
    assert 'python-test-failpoint' in failed.stderr
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
        user = session.scalar(select(User).where(User.username == 'admin'))
        assert user is not None
        assert user.session_version == 3
        assert not verify_password(workspace.admin_password, user.password_hash)
        assert session.scalar(select(func.count()).select_from(UserSessionActivity)) == 0
    final_bundle_path = workspace.root / '.rotation-secure' / '1.12.3-credentials.dpapi'
    bundle = load_credential_bundle(final_bundle_path)
    admin_credential = next(item for item in bundle.users if item.username == bundle.admin_username)
    assert _env_value(root_env_path, 'JWT_SECRET_KEY') == bundle.jwt_secret_key
    assert _env_value(backend_env_path, 'JWT_SECRET_KEY') == bundle.jwt_secret_key
    assert _env_value(root_env_path, 'ADMIN_PASSWORD') == admin_credential.password
    assert _env_value(backend_env_path, 'ADMIN_PASSWORD') == admin_credential.password
    secure_root = workspace.root / '.rotation-secure'
    protected_paths = (
        secure_root,
        secure_root / 'recovery',
        secure_root / 'recovery' / 'aeroone-db-before-rotation.dpapi',
        secure_root / 'rotation-state.json.dpapi',
        final_bundle_path,
        secure_root / 'quarantine' / 'environment' / 'root.env.before-rotation',
        secure_root / 'quarantine' / 'environment' / 'backend.env.before-rotation',
        secure_root / 'quarantine' / 'quarantine-manifest.json',
    )
    acl_results = tuple(has_exact_secure_acl(path) for path in protected_paths)
    assert acl_results == (True,) * len(protected_paths)
    manifest = json.loads((secure_root / 'quarantine' / 'quarantine-manifest.json').read_text(encoding='utf-8'))
    assert manifest['retention'] == '2027-07-10T00:00:00+09:00'
    assert {entry['source'] for entry in manifest['entries']} == {'.env', 'backend/.env'}
    assert all(entry['category'] == 'environment' for entry in manifest['entries'])
    assert all(len(entry['sha256']) == 64 for entry in manifest['entries'])
    pending_root_env = (secure_root / 'pending' / 'root-env.dpapi').read_bytes()
    assert bundle.jwt_secret_key.encode() not in pending_root_env
    assert admin_credential.password.encode() not in pending_root_env


@pytest.mark.parametrize(
    'failpoint',
    ('after_db_commit', 'after_root_env_promote', 'before_credentials_promote'),
)
def test_postcommit_failpoints_resume_forward_without_second_rotation(
    tmp_path: Path,
    failpoint: str,
) -> None:
    # Given: a fresh synthetic workspace and one supported postcommit failpoint.
    workspace = _create_synthetic_workspace(tmp_path)

    # When: execution stops after commit and the same journal is resumed twice.
    failed = _invoke_rotation(workspace, ('-Failpoint', failpoint))
    resumed = _invoke_rotation(workspace)
    repeated = _invoke_rotation(workspace)

    # Then: forward recovery completes once without exposing or restoring old credentials.
    combined_output = failed.stdout + failed.stderr + resumed.stdout + resumed.stderr + repeated.stdout + repeated.stderr
    assert failed.returncode != 0
    assert f'injected_{failpoint}' in failed.stderr
    assert resumed.returncode == 0, resumed.stderr
    assert repeated.returncode == 0, repeated.stderr
    assert workspace.jwt_secret not in combined_output
    assert workspace.admin_password not in combined_output
    with Session(create_engine(workspace.database_url)) as session:
        user = session.scalar(select(User).where(User.username == 'admin'))
        assert user is not None
        assert user.session_version == 3
        assert not verify_password(workspace.admin_password, user.password_hash)
        assert session.scalar(select(func.count()).select_from(UserSessionActivity)) == 0
    bundle_path = workspace.root / '.rotation-secure' / '1.12.3-credentials.dpapi'
    bundle = load_credential_bundle(bundle_path)
    admin_credential = next(item for item in bundle.users if item.username == bundle.admin_username)
    assert _env_value(workspace.root / '.env', 'ADMIN_PASSWORD') == admin_credential.password
    assert _env_value(workspace.root / 'backend' / '.env', 'ADMIN_PASSWORD') == admin_credential.password


def test_unknown_credential_key_blocks_before_secure_output(tmp_path: Path) -> None:
    # Given: an otherwise valid scope with one provider key outside the exact allow-list.
    workspace = _create_synthetic_workspace(tmp_path)
    unknown_secret = secrets.token_urlsafe(24)
    for env_path in (workspace.root / '.env', workspace.root / 'backend' / '.env'):
        env_path.write_text(
            env_path.read_text(encoding='utf-8') + f'EXTERNAL_API_TOKEN={unknown_secret}\n',
            encoding='utf-8',
        )

    # When: dry-run validates the credential inventory.
    completed = _invoke_rotation(workspace, ('-DryRun',))

    # Then: the unknown key blocks without creating a recovery root or printing its value.
    assert completed.returncode != 0
    assert 'unknown-credential-key' in completed.stderr
    assert unknown_secret not in completed.stdout + completed.stderr
    assert not (workspace.root / '.rotation-secure').exists()


def test_insecure_pending_acl_blocks_postcommit_resume(tmp_path: Path) -> None:
    # Given: a committed journal whose pending environment ACL gains an unauthorized reader.
    workspace = _create_synthetic_workspace(tmp_path)
    failed = _invoke_rotation(workspace, ('-Failpoint', 'after_db_commit'))
    assert failed.returncode != 0
    pending_env = workspace.root / '.rotation-secure' / 'pending' / 'root-env.dpapi'
    acl_change = subprocess.run(
        ['icacls.exe', str(pending_env), '/grant', '*S-1-5-32-545:R'],
        check=False,
        capture_output=True,
        text=True,
    )
    assert acl_change.returncode == 0

    # When: forward resume validates every protected input before promotion.
    resumed = _invoke_rotation(workspace)

    # Then: insecure ACL fails closed and old environments remain active.
    assert resumed.returncode != 0
    assert 'insecure-acl' in resumed.stderr
    assert _env_value(workspace.root / '.env', 'JWT_SECRET_KEY') == workspace.jwt_secret
    assert _env_value(workspace.root / 'backend' / '.env', 'JWT_SECRET_KEY') == workspace.jwt_secret


def test_read_only_database_blocks_before_environment_promotion(tmp_path: Path) -> None:
    # Given: a valid scope whose canonical SQLite file is read-only.
    workspace = _create_synthetic_workspace(tmp_path)
    database_path = Path(workspace.database_url.removeprefix('sqlite:///'))
    before_root_env = (workspace.root / '.env').read_bytes()
    before_backend_env = (workspace.root / 'backend' / '.env').read_bytes()
    os.chmod(database_path, stat.S_IREAD)

    # When: execute reaches the single database transaction.
    try:
        completed = _invoke_rotation(workspace)
    finally:
        os.chmod(database_path, stat.S_IREAD | stat.S_IWRITE)

    # Then: the transaction fails before either environment is promoted.
    assert completed.returncode != 0
    assert 'python-storage-failure' in completed.stderr
    assert (workspace.root / '.env').read_bytes() == before_root_env
    assert (workspace.root / 'backend' / '.env').read_bytes() == before_backend_env
    assert workspace.jwt_secret not in completed.stdout + completed.stderr
    assert workspace.admin_password not in completed.stdout + completed.stderr


def test_unknown_test_root_is_rejected_without_discovery(tmp_path: Path) -> None:
    # Given: a directory without the exact test-root marker or AeroOne scope files.
    unknown_root = tmp_path / 'unknown'
    unknown_root.mkdir()
    workspace = SyntheticWorkspace(
        root=unknown_root,
        database_url='',
        jwt_secret='',
        admin_password='',
    )

    # When: test mode is pointed at that unknown root.
    completed = _invoke_rotation(workspace, ('-DryRun',))

    # Then: validation stops before creating or discovering any secure output.
    assert completed.returncode != 0
    assert 'unknown-test-root' in completed.stderr
    assert list(unknown_root.iterdir()) == []


def test_old_auth_is_rejected_and_dpapi_admin_login_succeeds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a known-old token/password and a completed synthetic rotation.
    workspace = _create_synthetic_workspace(tmp_path)
    old_token = create_access_token(
        workspace.jwt_secret,
        '1',
        'admin',
        secrets.token_urlsafe(24),
        30,
        2,
    )
    completed = _invoke_rotation(workspace)
    assert completed.returncode == 0, completed.stderr
    bundle = load_credential_bundle(workspace.root / '.rotation-secure' / '1.12.3-credentials.dpapi')
    admin_credential = next(item for item in bundle.users if item.username == bundle.admin_username)
    new_jwt = _env_value(workspace.root / '.env', 'JWT_SECRET_KEY')
    runtime_root = tmp_path / 'runtime'
    for key, value in {
        'APP_ENV': 'test',
        'DATABASE_URL': workspace.database_url,
        'JWT_SECRET_KEY': new_jwt,
        'ADMIN_USERNAME': bundle.admin_username,
        'ADMIN_PASSWORD': admin_credential.password,
        'NEWSLETTER_IMPORT_ROOT_CONTAINER': str(runtime_root / 'newsletter'),
        'CIVIL_AIRCRAFT_ROOT': str(runtime_root / 'civil'),
        'DOCUMENT_ROOT': str(runtime_root / 'document'),
        'NSA_ROOT': str(runtime_root / 'nsa'),
        'STORAGE_ROOT': str(runtime_root / 'storage'),
    }.items():
        monkeypatch.setenv(key, value)
    reset_settings_cache()
    reset_db_caches()

    # When: known-old auth and the DPAPI-recovered new admin auth hit the real login surface.
    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(old_token, new_jwt)
    with TestClient(create_app()) as client:
        old_login = client.post(
            '/api/v1/auth/login',
            json={'username': bundle.admin_username, 'password': workspace.admin_password},
        )
        new_login = client.post(
            '/api/v1/auth/login',
            json={'username': bundle.admin_username, 'password': admin_credential.password},
        )

    # Then: old credentials receive 401 and the protected replacement receives 200.
    assert old_login.status_code == 401
    assert new_login.status_code == 200
    reset_settings_cache()
    reset_db_caches()
