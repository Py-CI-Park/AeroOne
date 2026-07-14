from __future__ import annotations

import re

from app.modules.admin.permissions import ADMIN_PERMISSIONS, RESOURCE_SAFE_PERMISSIONS

# Merged-state module gate policy for ServiceModule.visibility/required_permission/resource_type/resource_id.
#
# Allowed states:
#   1. visibility == 'admin'          -> required_permission, resource_type, resource_id all None.
#   2. visibility == 'public', ungated -> required_permission, resource_type, resource_id all None.
#   3. visibility == 'public', global gate -> required_permission is a known permission key
#      (e.g. 'admin.ai.manage' or the OpenWebUI launcher gate 'dashboard.openwebui.launch'),
#      resource_type and resource_id both None.
#   4. visibility == 'public', resource gate -> exactly
#      required_permission == 'collections.nsa.read', resource_type == 'collection', resource_id == 'nsa'.
#
# Anything else (partial gates, unknown permissions, resource mismatches, unsafe resource ids,
# or a gate declared alongside 'admin' visibility) is rejected.

_RESOURCE_ID_PATTERN = re.compile(r'^[a-z0-9-]+$')

_KNOWN_PERMISSIONS: set[str] = set(ADMIN_PERMISSIONS) | {
    permission for permissions in RESOURCE_SAFE_PERMISSIONS.values() for permission in permissions
}

_ALLOWED_RESOURCE_GATE = ('collections.nsa.read', 'collection', 'nsa')


def validate_module_gate(
    visibility: str,
    required_permission: str | None,
    resource_type: str | None,
    resource_id: str | None,
) -> str | None:
    """Validate a ServiceModule visibility/gate combination.

    Returns None when the combination is valid, otherwise a human-readable error string.
    """
    if visibility == 'admin':
        if required_permission is not None or resource_type is not None or resource_id is not None:
            return 'Modules with admin visibility must not declare a permission gate'
        return None

    if visibility != 'public':
        return f'Unknown module visibility: {visibility!r}'

    if required_permission is None and resource_type is None and resource_id is None:
        return None

    if required_permission is None:
        return 'Module gate requires required_permission'

    if (resource_type is None) != (resource_id is None):
        return 'Module gate requires resource_type and resource_id together'

    if required_permission not in _KNOWN_PERMISSIONS:
        return f'Unknown required_permission: {required_permission!r}'

    if resource_type is None and resource_id is None:
        return None

    if not _RESOURCE_ID_PATTERN.match(resource_id):
        return f'Unsafe resource_id: {resource_id!r}'

    if (required_permission, resource_type, resource_id) != _ALLOWED_RESOURCE_GATE:
        return 'Unsupported resource gate combination'

    return None
