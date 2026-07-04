from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.modules.admin.models import UserGroup
from app.modules.auth.models import User


def bump_authorization_session_versions(db: Session, user_ids: Iterable[int | None]) -> int:
    """Invalidate active sessions for the given users by bumping session_version.

    Call this after ANY authorization-affecting change so effective permissions/resources
    cannot go stale: direct permission changes, role/active changes, group membership
    changes, group active-flag or group permission changes, and ResourceGrant CRUD.
    Returns the number of distinct users bumped.
    """
    ids = sorted({int(uid) for uid in user_ids if uid is not None})
    if not ids:
        return 0
    db.execute(update(User).where(User.id.in_(ids)).values(session_version=User.session_version + 1))
    return len(ids)


def users_in_group(db: Session, group_id: int) -> list[int]:
    return list(db.execute(select(UserGroup.user_id).where(UserGroup.group_id == group_id)).scalars().all())


def users_affected_by_resource_grant(db: Session, subject_type: str, subject_id: int) -> list[int]:
    """Resolve which users a resource-grant change affects.

    A 'user' grant affects that user; a 'group' grant affects every member of the group.
    """
    if subject_type == 'user':
        return [int(subject_id)]
    if subject_type == 'group':
        return users_in_group(db, int(subject_id))
    return []


def bump_group_members(db: Session, group_id: int) -> int:
    return bump_authorization_session_versions(db, users_in_group(db, group_id))
