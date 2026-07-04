from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.admin.permissions import has_permission, has_resource_permission
from app.modules.auth.models import User

# document / civil are public reading surfaces. nsa is operator/granted-only.
PUBLIC_COLLECTIONS: frozenset[str] = frozenset({'document', 'civil'})
KNOWN_COLLECTIONS: frozenset[str] = frozenset({'document', 'civil', 'nsa'})

# Global permissions that grant nsa read (legacy search.nsa.read kept for compatibility).
_NSA_GLOBAL_PERMISSIONS = ('collections.nsa.read', 'search.nsa.read')
# Resource-grant coordinates for per-user/group nsa access.
_NSA_RESOURCE_TYPE = 'collection'
_NSA_RESOURCE_ID = 'nsa'
_NSA_RESOURCE_PERMISSION = 'collections.nsa.read'


def can_read_collection(db: Session, user: User | None, collection: str) -> bool:
    """Single canonical authorization for reading an HTML collection.

    Used by every surface that can surface collection content or references:
    collection list/content/download/search, admin unified search, AI requested
    scopes, AI selected_refs, and RAG/FTS loaders. document/civil stay public.
    nsa requires an active user who is admin, holds a global nsa-read permission,
    or holds an active direct/group ResourceGrant for collection:nsa.
    """
    if collection in PUBLIC_COLLECTIONS:
        return True
    if collection not in KNOWN_COLLECTIONS:
        return False
    # nsa
    if user is None or not user.is_active:
        return False
    if user.role == 'admin':
        return True
    if any(has_permission(db, user, key) for key in _NSA_GLOBAL_PERMISSIONS):
        return True
    return has_resource_permission(db, user, _NSA_RESOURCE_TYPE, _NSA_RESOURCE_ID, _NSA_RESOURCE_PERMISSION)


def readable_collections(db: Session, user: User | None, candidates: list[str]) -> list[str]:
    """Filter a requested collection list down to those the caller may read."""
    return [c for c in candidates if can_read_collection(db, user, c)]
