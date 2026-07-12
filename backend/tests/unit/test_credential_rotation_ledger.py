from __future__ import annotations

import secrets
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.base import Base
from app.modules.auth.models import User
from app.operations.credential_rotation import (
    CredentialBundle,
    CredentialRotationError,
    RotationRequest,
    UserCredential,
    rotate_all_credentials,
)


def _database_with_admin(tmp_path) -> tuple[str, User]:
    database_url = f"sqlite:///{tmp_path / 'ledger.db'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    admin = User(
        username="admin",
        password_hash=hash_password(secrets.token_urlsafe(24)),
        role="admin",
        is_active=True,
        session_version=0,
    )
    with Session(engine) as session, session.begin():
        session.add(admin)
    return database_url, admin


def _bundle() -> CredentialBundle:
    return CredentialBundle(
        admin_username="admin",
        jwt_secret_key=secrets.token_hex(32),
        users=(UserCredential(username="admin", password=secrets.token_urlsafe(24)),),
    )


def test_same_rotation_identity_rejects_different_credential_material(tmp_path) -> None:
    # Given: a committed rotation and a different bundle reusing its rotation identity.
    database_url, _ = _database_with_admin(tmp_path)
    first_bundle = _bundle()
    rotate_all_credentials(RotationRequest(database_url=database_url, bundle=first_bundle))
    conflicting_bundle = _bundle().model_copy(update={"rotation_id": first_bundle.rotation_id})

    # When: the conflicting bundle attempts to reuse the committed identity.
    with pytest.raises(CredentialRotationError, match="rotation-binding-mismatch"):
        rotate_all_credentials(
            RotationRequest(database_url=database_url, bundle=conflicting_bundle)
        )

    # Then: the committed user version remains exactly one generation ahead.
    with Session(create_engine(database_url)) as session:
        assert session.scalar(select(User.session_version)) == 1


def test_same_credential_material_rejects_new_rotation_identity(tmp_path) -> None:
    # Given: a committed material set wrapped in a second rotation identity.
    database_url, _ = _database_with_admin(tmp_path)
    first_bundle = _bundle()
    rotate_all_credentials(RotationRequest(database_url=database_url, bundle=first_bundle))
    replay_bundle = first_bundle.model_copy(update={"rotation_id": uuid4()})

    # When: the material is replayed as a nominally new rotation.
    with pytest.raises(CredentialRotationError, match="credential-material-reused"):
        rotate_all_credentials(RotationRequest(database_url=database_url, bundle=replay_bundle))

    # Then: the committed user version remains exactly one generation ahead.
    with Session(create_engine(database_url)) as session:
        assert session.scalar(select(User.session_version)) == 1
