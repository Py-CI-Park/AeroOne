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
    permissions_for_role,
)
from app.modules.collections.policy import can_read_collection
from app.modules.auth.models import User

MUTATION_PERMISSIONS = [
    'admin.newsletters.write',
    'admin.newsletters.bulk',
    'admin.newsletters.sync',
    'admin.read_tracking.purge',
    'admin.restore.execute',
    'admin.users.manage',
    'admin.users.reset_password',
    'admin.rbac.manage',
]


@pytest.fixture()
def session():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        yield db
    Base.metadata.drop_all(bind=engine)


def _user(db: Session, *, role: str = 'user', is_active: bool = True) -> User:
    user = User(username=f'u{role}{int(is_active)}{db.query(User).count()}', password_hash='x', role=role, is_active=is_active)
    db.add(user)
    db.flush()
    return user


def test_read_permission_never_satisfies_mutations(session: Session) -> None:
    user = _user(session)
    session.add(UserPermission(user_id=user.id, permission_key='admin.newsletters.read'))
    session.flush()
    assert has_permission(session, user, 'admin.newsletters.read') is True
    for key in MUTATION_PERMISSIONS:
        assert has_permission(session, user, key) is False, f'read must not satisfy {key}'


def test_resource_grant_never_satisfies_global_admin(session: Session) -> None:
    user = _user(session)
    session.add(ResourceGrant(subject_type='user', subject_id=user.id, resource_type='collection', resource_id='nsa', permission_key='collections.nsa.read'))
    session.flush()
    # Resource grant is not a global permission.
    assert has_permission(session, user, 'collections.nsa.read') is False
    assert has_permission(session, user, 'admin.users.manage') is False
    # But it is a valid resource permission.
    assert has_resource_permission(session, user, 'collection', 'nsa', 'collections.nsa.read') is True
    assert ('collection', 'nsa', 'collections.nsa.read') in set(list_user_resource_grants(session, user))


def test_inactive_user_denied_everything(session: Session) -> None:
    user = _user(session, role='admin', is_active=False)
    session.add(ResourceGrant(subject_type='user', subject_id=user.id, resource_type='collection', resource_id='nsa', permission_key='collections.nsa.read'))
    session.flush()
    assert has_permission(session, user, 'admin.users.read') is False
    assert has_resource_permission(session, user, 'collection', 'nsa', 'collections.nsa.read') is False
    assert can_read_collection(session, user, 'nsa') is False


def test_active_group_grants_read_only(session: Session) -> None:
    user = _user(session)
    group = Group(key='editors', name='Editors', is_active=True)
    session.add(group)
    session.flush()
    session.add(UserGroup(user_id=user.id, group_id=group.id))
    session.add(GroupPermission(group_id=group.id, permission_key='admin.newsletters.read'))
    session.flush()
    assert has_permission(session, user, 'admin.newsletters.read') is True
    assert has_permission(session, user, 'admin.newsletters.write') is False


def test_inactive_group_grants_nothing(session: Session) -> None:
    user = _user(session)
    group = Group(key='dormant', name='Dormant', is_active=False)
    session.add(group)
    session.flush()
    session.add(UserGroup(user_id=user.id, group_id=group.id))
    session.add(GroupPermission(group_id=group.id, permission_key='admin.newsletters.read'))
    session.add(ResourceGrant(subject_type='group', subject_id=group.id, resource_type='collection', resource_id='nsa', permission_key='collections.nsa.read'))
    session.flush()
    assert has_permission(session, user, 'admin.newsletters.read') is False
    assert has_resource_permission(session, user, 'collection', 'nsa', 'collections.nsa.read') is False


def test_admin_role_has_all_admin_permissions(session: Session) -> None:
    admin = _user(session, role='admin')
    for key in MUTATION_PERMISSIONS + ['admin.users.read', 'collections.nsa.read', 'admin.resource_grants.manage']:
        assert has_permission(session, admin, key) is True

def test_leantime_permissions_admin_default_not_user_default(session: Session) -> None:
    leantime_keys = {'admin.leantime.read', 'admin.leantime.manage', 'leantime.read'}
    assert leantime_keys.issubset(ADMIN_PERMISSIONS)

    admin = _user(session, role='admin')
    for key in leantime_keys:
        assert has_permission(session, admin, key) is True

    assert leantime_keys.isdisjoint(permissions_for_role('user'))

def test_office_permissions_are_admin_only(session: Session) -> None:
    admin = _user(session, role='admin')
    plain = _user(session)
    for key in ('office.use', 'admin.office.manage'):
        assert has_permission(session, admin, key) is True
        assert has_permission(session, plain, key) is False


def test_can_read_collection_matrix(session: Session) -> None:
    # public collections readable even anonymously
    assert can_read_collection(session, None, 'document') is True
    assert can_read_collection(session, None, 'civil') is True
    # nsa blocked for anonymous and plain users
    assert can_read_collection(session, None, 'nsa') is False
    plain = _user(session)
    assert can_read_collection(session, plain, 'nsa') is False
    # admin allowed
    admin = _user(session, role='admin')
    assert can_read_collection(session, admin, 'nsa') is True
    # user with direct global nsa read allowed
    perm_user = _user(session)
    session.add(UserPermission(user_id=perm_user.id, permission_key='collections.nsa.read'))
    session.flush()
    assert can_read_collection(session, perm_user, 'nsa') is True
    # user with legacy search.nsa.read allowed (compatibility)
    legacy_user = _user(session)
    session.add(UserPermission(user_id=legacy_user.id, permission_key='search.nsa.read'))
    session.flush()
    assert can_read_collection(session, legacy_user, 'nsa') is True
    # user with resource grant allowed
    grant_user = _user(session)
    session.add(ResourceGrant(subject_type='user', subject_id=grant_user.id, resource_type='collection', resource_id='nsa', permission_key='collections.nsa.read'))
    session.flush()
    assert can_read_collection(session, grant_user, 'nsa') is True
    # unknown collection denied
    assert can_read_collection(session, admin, 'secret-vault') is False
