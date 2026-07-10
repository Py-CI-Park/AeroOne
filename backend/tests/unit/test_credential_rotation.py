from __future__ import annotations

from datetime import UTC, datetime, timedelta
import secrets

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
import pytest

from app.core.security import hash_password, verify_password
from app.db.base import Base
from app.modules.admin.models import UserSessionActivity
from app.modules.auth.models import User
from app.operations.credential_rotation import (
    CredentialBundle,
    CredentialRotationError,
    RotationRequest,
    UserCredential,
    rotate_all_credentials,
)
from app.operations.credential_bundle import (
    BundlePreparationRequest,
    load_credential_bundle,
    prepare_credential_bundle,
)
from app.operations.windows_dpapi import protect_for_current_user, unprotect_for_current_user


def test_all_user_credentials_and_sessions_rotate_in_one_transaction(tmp_path) -> None:
    # Given: two users with different authorization state and live sessions.
    database_url = f"sqlite:///{tmp_path / 'rotation.db'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    old_passwords = {'admin': secrets.token_urlsafe(24), 'reader': secrets.token_urlsafe(24)}
    with Session(engine) as session, session.begin():
        admin = User(
            username='admin',
            password_hash=hash_password(old_passwords['admin']),
            role='admin',
            is_active=True,
            session_version=4,
        )
        reader = User(
            username='reader',
            password_hash=hash_password(old_passwords['reader']),
            role='user',
            is_active=False,
            session_version=7,
        )
        session.add_all([admin, reader])
        session.flush()
        now = datetime.now(UTC)
        session.add_all(
            [
                UserSessionActivity(
                    user_id=admin.id,
                    session_hash='a' * 64,
                    last_seen_at=now,
                    expires_at=now + timedelta(minutes=30),
                ),
                UserSessionActivity(
                    user_id=reader.id,
                    session_hash='b' * 64,
                    last_seen_at=now,
                    expires_at=now + timedelta(minutes=30),
                ),
            ]
        )
    bundle = CredentialBundle(
        admin_username='admin',
        jwt_secret_key=secrets.token_hex(32),
        users=(
            UserCredential(username='admin', password=secrets.token_urlsafe(24)),
            UserCredential(username='reader', password=secrets.token_urlsafe(24)),
        ),
    )

    # When: the database-aware rotation runs once.
    result = rotate_all_credentials(RotationRequest(database_url=database_url, bundle=bundle))

    # Then: every password/version/timestamp changes, sessions vanish, and authorization does not change.
    assert result.user_count_before == 2
    assert result.user_count_after == 2
    assert result.password_count_changed == 2
    assert result.session_count_before == 2
    assert result.session_count_after == 0
    with Session(engine) as session:
        users = session.scalars(select(User).order_by(User.username)).all()
        assert [(user.username, user.role, user.is_active, user.session_version) for user in users] == [
            ('admin', 'admin', True, 5),
            ('reader', 'user', False, 8),
        ]
        assert all(user.password_changed_at is not None for user in users)
        assert not verify_password(old_passwords['admin'], users[0].password_hash)
        assert not verify_password(old_passwords['reader'], users[1].password_hash)
        assert session.scalar(select(UserSessionActivity.id)) is None


def test_dpapi_bundle_is_bound_to_the_current_windows_user() -> None:
    # Given: an in-memory payload that has never been written as plaintext.
    plaintext = secrets.token_bytes(96)

    # When: Windows DPAPI protects and then unprotects it for the current user.
    protected = protect_for_current_user(plaintext)
    recovered = unprotect_for_current_user(protected)

    # Then: ciphertext is different and the same Windows identity can recover it.
    assert protected != plaintext
    assert recovered == plaintext


def test_precommit_failure_rolls_back_and_same_bundle_resumes_only_once(tmp_path) -> None:
    # Given: one user, one live session, and one reusable protected rotation identity.
    database_url = f"sqlite:///{tmp_path / 'resume.db'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    old_password = secrets.token_urlsafe(24)
    with Session(engine) as session, session.begin():
        user = User(
            username='admin',
            password_hash=hash_password(old_password),
            role='admin',
            is_active=True,
            session_version=9,
        )
        session.add(user)
        session.flush()
        session.add(
            UserSessionActivity(
                user_id=user.id,
                session_hash=secrets.token_hex(32),
                last_seen_at=datetime.now(UTC),
                expires_at=None,
            )
        )
    bundle = CredentialBundle(
        admin_username='admin',
        jwt_secret_key=secrets.token_hex(32),
        users=(UserCredential(username='admin', password=secrets.token_urlsafe(24)),),
    )

    # When: the precommit failpoint fires, followed by two resumes with the same bundle.
    with pytest.raises(CredentialRotationError, match='test-failpoint'):
        rotate_all_credentials(
            RotationRequest(database_url=database_url, bundle=bundle, fail_before_commit=True)
        )
    first_resume = rotate_all_credentials(RotationRequest(database_url=database_url, bundle=bundle))
    second_resume = rotate_all_credentials(RotationRequest(database_url=database_url, bundle=bundle))

    # Then: rollback preserved the old state and the committed rotation was applied only once.
    assert first_resume.password_count_changed == 1
    assert second_resume.password_count_changed == 1
    with Session(engine) as session:
        user = session.scalar(select(User).where(User.username == 'admin'))
        assert user is not None
        assert user.session_version == 10
        assert not verify_password(old_password, user.password_hash)
        assert session.scalar(select(UserSessionActivity.id)) is None


def test_user_count_drift_after_bundle_preparation_rolls_back(tmp_path) -> None:
    # Given: a protected bundle prepared for one user before a second row appears.
    database_url = f"sqlite:///{tmp_path / 'row-drift.db'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    old_password = secrets.token_urlsafe(24)
    with Session(engine) as session, session.begin():
        session.add(User(username='admin', password_hash=hash_password(old_password), session_version=5))
    bundle_path = tmp_path / 'credentials.dpapi'
    prepare_credential_bundle(
        BundlePreparationRequest(
            database_url=database_url,
            admin_username='admin',
            bundle_path=bundle_path,
        )
    )
    with Session(engine) as session, session.begin():
        session.add(User(username='late-user', password_hash=hash_password(secrets.token_urlsafe(24))))

    # When: commit sees a different database user count than the protected bundle.
    with pytest.raises(CredentialRotationError, match='credential-count-mismatch'):
        rotate_all_credentials(
            RotationRequest(database_url=database_url, bundle=load_credential_bundle(bundle_path))
        )

    # Then: no existing row was partially rotated.
    with Session(engine) as session:
        admin = session.scalar(select(User).where(User.username == 'admin'))
        assert admin is not None
        assert admin.session_version == 5
        assert verify_password(old_password, admin.password_hash)
