from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.admin.models import Group, GroupPermission, UserGroup, UserPermission
from app.modules.auth.models import User

ADMIN_PERMISSIONS: set[str] = {
    'admin.users.read',
    'admin.users.manage',
    'admin.users.reset_password',
    'admin.rbac.read',
    'admin.rbac.manage',
    'admin.audit.read',
    'admin.dashboard.manage',
    'admin.newsletters.read',
    'admin.newsletters.write',
    'admin.newsletters.bulk',
    'admin.newsletters.sync',
    'admin.taxonomy.read',
    'admin.taxonomy.manage',
    'admin.read_tracking.read',
    'admin.read_tracking.purge',
    'admin.backup.read',
    'admin.backup.create',
    'admin.restore.execute',
    'admin.ai.read',
    'admin.ai.manage',
    'search.nsa.read',
    'search.use',
    'ai.use',
    'ai.history.manage_own',
}

DEFAULT_ROLE_PERMISSIONS: dict[str, set[str]] = {
    'admin': set(ADMIN_PERMISSIONS),
    'user': {'search.use', 'ai.use', 'ai.history.manage_own'},
    'pending': set(),
}

READ_PERMISSION_BY_PREFIX = {
    'admin.newsletters.': 'admin.newsletters.read',
    'admin.taxonomy.': 'admin.taxonomy.read',
    'admin.backup.': 'admin.backup.read',
    'admin.ai.': 'admin.ai.read',
    'admin.users.': 'admin.users.read',
    'admin.rbac.': 'admin.rbac.read',
}


def permissions_for_role(role: str) -> set[str]:
    return set(DEFAULT_ROLE_PERMISSIONS.get(role, set()))


def list_user_permission_keys(db: Session, user: User) -> set[str]:
    keys = permissions_for_role(user.role)
    direct = db.execute(select(UserPermission.permission_key).where(UserPermission.user_id == user.id)).scalars().all()
    keys.update(direct)
    group_keys = db.execute(
        select(GroupPermission.permission_key)
        .join(UserGroup, UserGroup.group_id == GroupPermission.group_id)
        .join(Group, Group.id == UserGroup.group_id)
        .where(UserGroup.user_id == user.id, Group.is_active.is_(True))
    ).scalars().all()
    keys.update(group_keys)
    return keys


def has_permission(db: Session, user: User, permission_key: str) -> bool:
    if not user.is_active:
        return False
    keys = list_user_permission_keys(db, user)
    if permission_key in keys:
        return True
    return any(permission_key.startswith(prefix) and read_key in keys for prefix, read_key in READ_PERMISSION_BY_PREFIX.items())
