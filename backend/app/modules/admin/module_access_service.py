from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.admin.models import ServiceModule
from app.modules.admin.permissions import has_permission, has_resource_permission
from app.modules.auth.models import User

VALID_ROLES = frozenset({'admin', 'user', 'pending'})


def validate_role(role: str | None) -> str:
    """Return a stored role only when it belongs to the public role domain."""
    if role not in VALID_ROLES:
        raise ValueError(f'Unsupported stored user role: {role!r}')
    return role


def user_can_access_module(db: Session, user: User | None, module: ServiceModule) -> bool:
    """Apply the complete service-module audience and authorization policy."""
    if not module.is_enabled or module.visibility == 'hidden' or module.status == 'hidden':
        return False
    if module.visibility == 'admin':
        # 발급된 활성 로그인 계정(admin·user)은 개발중 섹션을 포함한 전체 대시보드를 본다.
        # 익명·pending 은 여전히 admin-가시성 카드를 볼 수 없다.
        return bool(user and user.is_active and validate_role(user.role) in ('admin', 'user'))
    if module.visibility != 'public':
        return False
    if not module.required_permission:
        return not module.resource_type and not module.resource_id
    if user is None:
        return False
    validate_role(user.role)
    if has_permission(db, user, module.required_permission):
        return True
    if module.resource_type and module.resource_id and has_resource_permission(
        db, user, module.resource_type, module.resource_id, module.required_permission
    ):
        return True
    return False


def accessible_module_refs(db: Session, user: User | None, modules: list[ServiceModule]) -> list[dict[str, str]]:
    """Return only authorized module metadata in deterministic order."""
    if user is not None:
        validate_role(user.role)
    return [
        {'key': module.key, 'label': module.title}
        for module in sorted(modules, key=lambda item: (item.sort_order, item.key))
        if user_can_access_module(db, user, module)
    ]
