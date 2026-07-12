from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Request
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.admin.models import AiRequestLog, LoginEvent, ServiceModule, UserSessionActivity
from app.modules.auth.models import User
from app.modules.auth.session_hash import hash_session_token

_LATEST_LIMIT = 20

_LOGIN_EVENT_MAP = {
    'success': ('login', 'success'),
    'failure': ('login', 'failure'),
    'logout': ('logout', 'success'),
}

_AI_REQUEST_MAP = {
    'ok': 'completed',
    'error': 'failed',
}

_VALID_ROLES = {'admin', 'user', 'pending'}


def _rfc3339(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    else:
        value = value.astimezone(UTC)
    return value.isoformat().replace('+00:00', 'Z')


def _resolve_role(role: str | None) -> str:
    return role if role in _VALID_ROLES else 'pending'


def build_activity_payload(db: Session, current_user: User, request: Request, settings: Settings) -> dict:
    now = datetime.now(UTC)
    token = request.cookies.get(settings.admin_session_cookie_name)
    current_hash = hash_session_token(token) if token else None

    session_rows = (
        db.execute(
            select(UserSessionActivity)
            .where(
                UserSessionActivity.user_id == current_user.id,
                or_(UserSessionActivity.expires_at.is_(None), UserSessionActivity.expires_at > now),
            )
            .order_by(UserSessionActivity.last_seen_at.desc(), UserSessionActivity.id.desc())
            .limit(_LATEST_LIMIT)
        )
        .scalars()
        .all()
    )
    active_sessions = []
    for row in session_rows:
        is_current = current_hash is not None and row.session_hash == current_hash
        active_sessions.append(
            {
                'state': 'current' if is_current else 'active',
                'last_activity_at': _rfc3339(row.last_seen_at),
                'device_label': '현재 기기' if is_current else '다른 활성 기기',
            }
        )

    login_rows = (
        db.execute(
            select(LoginEvent)
            .where(LoginEvent.user_id == current_user.id)
            .order_by(LoginEvent.created_at.desc(), LoginEvent.id.desc())
            .limit(_LATEST_LIMIT)
        )
        .scalars()
        .all()
    )
    auth_events = []
    for row in login_rows:
        mapped = _LOGIN_EVENT_MAP.get(row.status)
        if mapped is None:
            continue
        kind, outcome = mapped
        auth_events.append({'kind': kind, 'outcome': outcome, 'occurred_at': _rfc3339(row.created_at)})

    ai_rows = (
        db.execute(
            select(AiRequestLog)
            .where(AiRequestLog.user_id == current_user.id)
            .order_by(AiRequestLog.created_at.desc(), AiRequestLog.id.desc())
            .limit(_LATEST_LIMIT)
        )
        .scalars()
        .all()
    )
    ai_requests = []
    for row in ai_rows:
        mapped_status = _AI_REQUEST_MAP.get(row.status)
        if mapped_status is None:
            continue
        ai_requests.append({'status': mapped_status, 'module_key': None, 'occurred_at': _rfc3339(row.created_at)})

    module_rows = (
        db.execute(select(ServiceModule).order_by(ServiceModule.sort_order.asc(), ServiceModule.key.asc())).scalars().all()
    )
    accessible_modules = [{'key': row.key, 'label': row.title} for row in module_rows]

    return {
        'identity': {
            'username': current_user.username,
            'display_name': current_user.display_name,
            'role': _resolve_role(current_user.role),
        },
        'active_sessions': active_sessions,
        'auth_events': auth_events,
        'ai_requests': ai_requests,
        'accessible_modules': accessible_modules,
    }
