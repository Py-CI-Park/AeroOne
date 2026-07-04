from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.modules.admin import models as admin_models  # noqa: F401 (register tables)
from app.modules.admin.models import Group, GroupPermission, ResourceGrant, UserGroup, UserPermission
from app.modules.admin.permissions import (
    ADMIN_PERMISSIONS,
    has_permission,
    has_resource_permission,
    list_user_resource_grants,
)
from app.modules.auth.models import User
from app.modules.collections.policy import can_read_collection


@pytest.fixture()
def session():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        yield db
    Base.metadata.drop_all(bind=engine)


def _user(db: Session, *, role: str = 'user', is_active: bool = True) -> User:
    user = User(
        username=f'u{role}{int(is_active)}{db.query(User).count()}',
        password_hash='x',
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.flush()
    return user


def _mutation_permissions_with_corresponding_read() -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for permission_key in sorted(ADMIN_PERMISSIONS):
        if permission_key.endswith('.read'):
            continue
        read_key = f'{permission_key.rsplit(".", 1)[0]}.read'
        if read_key in ADMIN_PERMISSIONS:
            pairs.append((permission_key, read_key))
    return pairs


def test_catalog_read_permissions_do_not_escalate_to_corresponding_mutations(session: Session) -> None:
    pairs = _mutation_permissions_with_corresponding_read()
    assert pairs, 'red-team test must exercise catalog-derived read/mutation pairs'

    for mutation_key, read_key in pairs:
        user = _user(session)
        session.add(UserPermission(user_id=user.id, permission_key=read_key))
        session.flush()

        assert has_permission(session, user, read_key) is True
        assert has_permission(session, user, mutation_key) is False, f'{read_key} escalated to {mutation_key}'


def test_global_looking_resource_grant_does_not_satisfy_global_admin_permission(session: Session) -> None:
    user = _user(session)
    session.add(
        ResourceGrant(
            subject_type='user',
            subject_id=user.id,
            resource_type='global',
            resource_id='*',
            permission_key='admin.users.manage',
        )
    )
    session.flush()

    assert has_permission(session, user, 'admin.users.manage') is False
    assert has_resource_permission(session, user, 'global', '*', 'admin.users.manage') is True


def test_inactive_user_with_direct_admin_and_resource_grants_is_denied(session: Session) -> None:
    user = _user(session, is_active=False)
    session.add(UserPermission(user_id=user.id, permission_key='admin.users.manage'))
    session.add(UserPermission(user_id=user.id, permission_key='collections.nsa.read'))
    session.add(
        ResourceGrant(
            subject_type='user',
            subject_id=user.id,
            resource_type='collection',
            resource_id='nsa',
            permission_key='collections.nsa.read',
        )
    )
    session.flush()

    assert has_permission(session, user, 'admin.users.manage') is False
    assert has_permission(session, user, 'collections.nsa.read') is False
    assert has_resource_permission(session, user, 'collection', 'nsa', 'collections.nsa.read') is False
    assert can_read_collection(session, user, 'nsa') is False


def test_group_deactivation_revokes_permission_and_resource_grant_on_next_check(session: Session) -> None:
    user = _user(session)
    group = Group(key='operators', name='Operators', is_active=True)
    session.add(group)
    session.flush()
    session.add(UserGroup(user_id=user.id, group_id=group.id))
    session.add(GroupPermission(group_id=group.id, permission_key='admin.newsletters.read'))
    session.add(
        ResourceGrant(
            subject_type='group',
            subject_id=group.id,
            resource_type='collection',
            resource_id='nsa',
            permission_key='collections.nsa.read',
        )
    )
    session.flush()

    assert has_permission(session, user, 'admin.newsletters.read') is True
    assert has_resource_permission(session, user, 'collection', 'nsa', 'collections.nsa.read') is True
    assert can_read_collection(session, user, 'nsa') is True

    group.is_active = False
    session.flush()

    assert has_permission(session, user, 'admin.newsletters.read') is False
    assert has_resource_permission(session, user, 'collection', 'nsa', 'collections.nsa.read') is False
    assert can_read_collection(session, user, 'nsa') is False


def test_collection_policy_denies_unknown_spoofed_and_path_like_names(session: Session) -> None:
    admin = _user(session, role='admin')
    granted_user = _user(session)
    session.add(UserPermission(user_id=granted_user.id, permission_key='collections.nsa.read'))
    session.flush()

    for collection in ('secret-vault', '../nsa', 'nsa/', 'NSA'):
        assert can_read_collection(session, admin, collection) is False, f'admin bypass for {collection}'
        assert can_read_collection(session, granted_user, collection) is False, f'grant bypass for {collection}'
        assert can_read_collection(session, None, collection) is False, f'anonymous bypass for {collection}'


def test_list_user_resource_grants_does_not_leak_other_users_or_other_groups(session: Session) -> None:
    user = _user(session)
    other_user = _user(session)
    own_group = Group(key='own-group', name='Own Group', is_active=True)
    other_group = Group(key='other-group', name='Other Group', is_active=True)
    session.add_all([own_group, other_group])
    session.flush()
    session.add(UserGroup(user_id=user.id, group_id=own_group.id))
    session.add(
        ResourceGrant(
            subject_type='user',
            subject_id=user.id,
            resource_type='collection',
            resource_id='nsa',
            permission_key='collections.nsa.read',
        )
    )
    session.add(
        ResourceGrant(
            subject_type='group',
            subject_id=own_group.id,
            resource_type='collection',
            resource_id='civil',
            permission_key='collections.read',
        )
    )
    session.add(
        ResourceGrant(
            subject_type='user',
            subject_id=other_user.id,
            resource_type='collection',
            resource_id='other-user-secret',
            permission_key='collections.nsa.read',
        )
    )
    session.add(
        ResourceGrant(
            subject_type='group',
            subject_id=other_group.id,
            resource_type='collection',
            resource_id='other-group-secret',
            permission_key='collections.nsa.read',
        )
    )
    session.flush()

    grants = set(list_user_resource_grants(session, user))

    assert ('collection', 'nsa', 'collections.nsa.read') in grants
    assert ('collection', 'civil', 'collections.read') in grants
    assert ('collection', 'other-user-secret', 'collections.nsa.read') not in grants
    assert ('collection', 'other-group-secret', 'collections.nsa.read') not in grants
