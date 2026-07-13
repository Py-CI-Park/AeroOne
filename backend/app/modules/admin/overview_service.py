from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.admin.models import AdminAuditEvent, AiRequestLog, LoginEvent, ServiceModule, UserSessionActivity
from app.modules.admin.module_access_service import validate_role
from app.modules.auth.models import User
from app.modules.newsletter.models.newsletter import Newsletter
from app.modules.admin.health_service import asset_health, read_tracking_summary

_COMING_STATUSES = ('coming', 'coming-soon', 'coming_soon')


def _window_count(db: Session, model: Any, timestamp_column: Any, *, now: datetime, extra_where: ColumnElement[bool] | None = None) -> dict[str, int]:
    current_start = now - timedelta(hours=24)
    prior_start = now - timedelta(hours=48)

    current_stmt = select(func.count()).select_from(model).where(timestamp_column >= current_start, timestamp_column < now)
    prior_stmt = select(func.count()).select_from(model).where(timestamp_column >= prior_start, timestamp_column < current_start)
    if extra_where is not None:
        current_stmt = current_stmt.where(extra_where)
        prior_stmt = prior_stmt.where(extra_where)

    current = int(db.scalar(current_stmt) or 0)
    prior = int(db.scalar(prior_stmt) or 0)
    return {'current': current, 'prior': prior, 'delta': current - prior}


def build_overview(db: Session, settings: Settings, *, now: datetime | None = None) -> dict[str, Any]:

    now = now or datetime.now(UTC)

    total_users = int(db.scalar(select(func.count(User.id))) or 0)
    active_users = int(db.scalar(select(func.count(User.id)).where(User.is_active.is_(True))) or 0)
    inactive_users = total_users - active_users

    role_counts = {'admin': 0, 'user': 0, 'pending': 0}
    for role, count in db.execute(select(User.role, func.count(User.id)).group_by(User.role)).all():
        role_counts[validate_role(role)] += int(count)

    users_payload = {
        'total': total_users,
        'active': active_users,
        'inactive': inactive_users,
        'roles': role_counts,
        'created': _window_count(db, User, User.created_at, now=now),
    }

    logins_payload = {
        'success': _window_count(db, LoginEvent, LoginEvent.created_at, now=now, extra_where=LoginEvent.status == 'success'),
        'failure': _window_count(db, LoginEvent, LoginEvent.created_at, now=now, extra_where=LoginEvent.status == 'failure'),
        'logout': _window_count(db, LoginEvent, LoginEvent.created_at, now=now, extra_where=LoginEvent.status == 'logout'),
    }

    ai_payload = {
        'total': _window_count(db, AiRequestLog, AiRequestLog.created_at, now=now),
        'failure': _window_count(db, AiRequestLog, AiRequestLog.created_at, now=now, extra_where=AiRequestLog.status == 'error'),
    }

    active_since = now - timedelta(minutes=settings.access_token_ttl_minutes)
    session_user_ids = db.execute(
        select(UserSessionActivity.user_id).where(
            (UserSessionActivity.expires_at.is_(None)) | (UserSessionActivity.expires_at > now),
            UserSessionActivity.last_seen_at >= active_since,
        )
    ).scalars().all()
    active_session_count = len(session_user_ids)
    active_user_count = len(set(session_user_ids))
    sessions_payload = {
        'active_session_count': active_session_count,
        'active_user_count': active_user_count,
        'active_count': active_user_count,
    }

    modules = db.execute(select(ServiceModule).order_by(ServiceModule.sort_order, ServiceModule.id)).scalars().all()
    buckets: dict[str, list[dict[str, str]]] = {'unavailable': [], 'coming': [], 'development': [], 'active': []}
    for module in modules:
        ref = {'key': module.key, 'label': module.title}
        if not module.is_enabled or module.visibility == 'hidden' or module.status == 'hidden':
            buckets['unavailable'].append(ref)
        elif module.status in _COMING_STATUSES:
            buckets['coming'].append(ref)
        elif module.status == 'development':
            buckets['development'].append(ref)
        else:
            buckets['active'].append(ref)
    modules_payload = {'total': len(modules), 'buckets': buckets}

    health = asset_health(db, settings)
    database_kind = settings.database_url.split(':', 1)[0]
    system_payload = {
        'app_version': settings.app_version,
        'app_env': settings.app_env,
        'database_kind': database_kind,
        'newsletter_count': int(db.scalar(select(func.count(Newsletter.id))) or 0),
        'asset_health': {'ok': health.ok, 'missing': health.missing, 'checksum_mismatch': health.checksum_mismatch, 'misconfig': health.misconfig},
        'read_summary': read_tracking_summary(db),
    }

    recent_audit = db.execute(select(AdminAuditEvent).order_by(AdminAuditEvent.created_at.desc()).limit(10)).scalars().all()
    recent_audit_payload = [
        {'id': event.id, 'action': event.action, 'target_type': event.target_type, 'status': event.status, 'created_at': event.created_at}
        for event in recent_audit
    ]

    return {
        'generated_at': now,
        'anchor': now,
        'users': users_payload,
        'logins': logins_payload,
        'ai': ai_payload,
        'sessions': sessions_payload,
        'modules': modules_payload,
        'system': system_payload,
        'recent_audit': recent_audit_payload,
    }
