from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.admin.models import Group, GroupPermission, ResourceGrant, UserGroup, UserPermission
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
    'admin.sessions.read',
    'admin.sessions.purge',
    'admin.resource_grants.read',
    'admin.resource_grants.manage',
    'collections.read',
    'collections.nsa.read',
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


def permissions_for_role(role: str) -> set[str]:
    return set(DEFAULT_ROLE_PERMISSIONS.get(role, set()))


def _active_group_ids(db: Session, user: User) -> list[int]:
    return list(
        db.execute(
            select(UserGroup.group_id)
            .join(Group, Group.id == UserGroup.group_id)
            .where(UserGroup.user_id == user.id, Group.is_active.is_(True))
        ).scalars().all()
    )


def list_user_permission_keys(db: Session, user: User) -> set[str]:
    keys = permissions_for_role(user.role)
    direct = db.execute(select(UserPermission.permission_key).where(UserPermission.user_id == user.id)).scalars().all()
    keys.update(direct)
    group_ids = _active_group_ids(db, user)
    if group_ids:
        group_keys = db.execute(
            select(GroupPermission.permission_key).where(GroupPermission.group_id.in_(group_ids))
        ).scalars().all()
        keys.update(group_keys)
    return keys


def has_permission(db: Session, user: User, permission_key: str) -> bool:
    """Exact global-permission check.

    A read permission NEVER satisfies a write/manage/bulk/sync/purge/restore/reset
    permission: the previous READ_PERMISSION_BY_PREFIX fallback was removed because it
    let a read grant escalate to mutating actions. Global permissions must match exactly.
    ResourceGrant is intentionally NOT consulted here; use has_resource_permission for
    per-resource authorization so a resource grant can never satisfy a global admin action.
    """
    if not user.is_active:
        return False
    return permission_key in list_user_permission_keys(db, user)


def list_user_resource_grants(db: Session, user: User) -> list[tuple[str, str, str]]:
    """Return (resource_type, resource_id, permission_key) tuples effective for the user.

    Combines direct (subject_type='user') grants and grants on the user's ACTIVE groups
    (subject_type='group'). Inactive users get nothing.
    """
    if not user.is_active:
        return []
    conditions = [(ResourceGrant.subject_type == 'user') & (ResourceGrant.subject_id == user.id)]
    group_ids = _active_group_ids(db, user)
    if group_ids:
        conditions.append((ResourceGrant.subject_type == 'group') & (ResourceGrant.subject_id.in_(group_ids)))
    predicate = conditions[0]
    for extra in conditions[1:]:
        predicate = predicate | extra
    rows = db.execute(
        select(ResourceGrant.resource_type, ResourceGrant.resource_id, ResourceGrant.permission_key).where(predicate)
    ).all()
    return [(row[0], row[1], row[2]) for row in rows]


def has_resource_permission(db: Session, user: User, resource_type: str, resource_id: str, permission_key: str) -> bool:
    """Per-resource authorization via ResourceGrant only.

    This never grants a global admin permission; it only answers whether the user (or an
    active group of theirs) holds an explicit grant for (resource_type, resource_id, permission_key).
    """
    if not user.is_active:
        return False
    return (resource_type, resource_id, permission_key) in set(list_user_resource_grants(db, user))
