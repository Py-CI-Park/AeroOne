from __future__ import annotations

from datetime import UTC, datetime, timedelta
import secrets
import json
from pathlib import Path

import zipfile

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import hash_file_bytes, hash_password
from app.modules.admin.audit import record_admin_audit
from app.modules.admin.models import (
    AdminAuditEvent,
    BackupRecord,
    Group,
    GroupPermission,
    ResourceGrant,
    ServiceModule,
    UserGroup,
    UserPermission,
    AiRequestLog,
    LoginEvent,
    UserSessionActivity,
)
from app.modules.admin.permissions import ADMIN_PERMISSIONS, DEFAULT_ROLE_PERMISSIONS, has_permission, has_resource_permission, list_user_permission_keys
from app.modules.admin.session_fanout import bump_authorization_session_versions, bump_group_members, users_affected_by_resource_grant
from app.modules.admin.schemas import (
    AdminSummaryResponse,
    AssetHealthItem,
    AssetHealthResponse,
    ConfigHealthItem,
    ConfigHealthResponse,
    ConnectedUsersResponse,
    SessionPurgeResponse,
    AuditEventResponse,
    BackupCreateResponse,
    BackupRecordResponse,
    BackupValidationResponse,
    BackupRestoreDryRunResponse,
    BulkNewsletterRequest,
    BulkNewsletterResponse,
    GroupResponse,
    GroupUpsertRequest,
    RbacMatrixUserResponse,
    ResourceGrantCreateRequest,
    ResourceGrantResponse,
    PermissionResponse,
    ServiceModuleResponse,
    ServiceModuleCreateRequest,
    ServiceModuleUpdateRequest,
    UnifiedSearchResponse,
    UnifiedSearchResult,
    UserAdminResponse,
    UserCreateRequest,
    UserUpdateRequest,
    PasswordResetRequest,
)
from app.modules.ai.service import AiChatService
from app.modules.auth.dependencies import get_current_user, get_db, get_optional_user, get_settings, require_csrf, require_permission
from app.modules.auth.models import User
from app.modules.auth.repositories import UserRepository
from app.modules.collections.search_service import CollectionSearchRoot, CollectionSearchUnavailable, HtmlCollectionSearchService
from app.modules.collections.policy import can_read_collection
from app.modules.newsletter.models.newsletter import AssetType, Newsletter
from app.modules.newsletter.repositories.newsletter_repository import NewsletterRepository
from app.modules.read_tracking.models.read_event import NewsletterReadEvent
from app.modules.shared.storage.service import StorageError, StorageService, sha256_for_file

router = APIRouter()

DEFAULT_SERVICE_MODULES = [
    {'key': 'newsletter', 'title': 'Newsletter', 'description': None, 'href': '/newsletters', 'section': 'Newsletter', 'status': 'active', 'badge': 'Active', 'sort_order': 10, 'is_enabled': True, 'is_external': False, 'visibility': 'public', 'required_permission': None, 'resource_type': None, 'resource_id': None},
    {'key': 'civil-aircraft', 'title': 'Civil Aircraft Spec Catalog', 'description': 'Commercial aircraft specs & market competition analysis.', 'href': '/reports/civil-aircraft', 'section': 'Document', 'status': 'active', 'badge': 'Active', 'sort_order': 20, 'is_enabled': True, 'is_external': False, 'visibility': 'public', 'required_permission': None, 'resource_type': None, 'resource_id': None},
    {'key': 'document', 'title': 'Document', 'description': 'Browse HTML documents organized in folders.', 'href': '/documents', 'section': 'Document', 'status': 'active', 'badge': 'Active', 'sort_order': 30, 'is_enabled': True, 'is_external': False, 'visibility': 'public', 'required_permission': None, 'resource_type': None, 'resource_id': None},
    {'key': 'nsa', 'title': 'NSA', 'description': 'Password-protected HTML documents.', 'href': '/nsa', 'section': 'Document', 'status': 'active', 'badge': 'Active', 'sort_order': 40, 'is_enabled': True, 'is_external': False, 'visibility': 'public', 'required_permission': 'collections.nsa.read', 'resource_type': 'collection', 'resource_id': 'nsa'},
    {'key': 'viewer', 'title': 'Viewer', 'description': '로컬 Markdown·HTML 파일을 열어 보고 편집 (서버 sanitize 미리보기).', 'href': '/viewer', 'section': 'Development', 'status': 'development', 'badge': 'Active', 'sort_order': 50, 'is_enabled': True, 'is_external': False, 'visibility': 'admin', 'required_permission': None, 'resource_type': None, 'resource_id': None},
    {'key': 'ai', 'title': 'AeroAI', 'description': '사내 폐쇄망 문서를 근거로 답하는 AI 어시스턴트.', 'href': '/ai', 'section': 'Development', 'status': 'development', 'badge': 'Active', 'sort_order': 60, 'is_enabled': True, 'is_external': False, 'visibility': 'admin', 'required_permission': None, 'resource_type': None, 'resource_id': None},
    {'key': 'open-notebook', 'title': 'Notebook', 'description': 'NotebookLM 대안 — 소스 정리·요약·벡터 검색 (별도 폐쇄망 앱).', 'href': '', 'section': 'Development', 'status': 'development', 'badge': 'Active', 'sort_order': 70, 'is_enabled': True, 'is_external': True, 'visibility': 'admin', 'required_permission': None, 'resource_type': None, 'resource_id': None},
    {'key': 'ladder', 'title': 'Ladder', 'description': 'Coffee-bet ladder game (사다리타기).', 'href': '/games/ladder', 'section': 'Development', 'status': 'development', 'badge': 'Active', 'sort_order': 80, 'is_enabled': True, 'is_external': False, 'visibility': 'admin', 'required_permission': None, 'resource_type': None, 'resource_id': None},
    {'key': 'announcement', 'title': 'Announcement', 'description': 'Company-wide announcements module.', 'href': '#', 'section': 'Development', 'status': 'coming_soon', 'badge': 'Coming soon', 'sort_order': 90, 'is_enabled': False, 'is_external': False, 'visibility': 'admin', 'required_permission': None, 'resource_type': None, 'resource_id': None},
    {'key': 'schedule', 'title': 'Schedule', 'description': 'Shared calendar & event tracking.', 'href': '#', 'section': 'Development', 'status': 'coming_soon', 'badge': 'Coming soon', 'sort_order': 100, 'is_enabled': False, 'is_external': False, 'visibility': 'admin', 'required_permission': None, 'resource_type': None, 'resource_id': None},
]


def _connected_user_retention_days(settings: Settings) -> int:
    return min(max(int(settings.connected_user_retention_days), 30), 90)


def _read_tracking_summary(db: Session) -> dict[str, int]:
    row = db.execute(select(func.count(NewsletterReadEvent.id), func.coalesce(func.sum(NewsletterReadEvent.read_count), 0))).one()
    return {'rows': int(row[0] or 0), 'total_reads': int(row[1] or 0)}


def _serialize_user(db: Session, user: User) -> UserAdminResponse:
    return UserAdminResponse.model_validate(user).model_copy(update={'permissions': sorted(list_user_permission_keys(db, user))})


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _required_text(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'{field_name} is required')
    return cleaned


def _serialize_resource_grant(grant: ResourceGrant) -> ResourceGrantResponse:
    return ResourceGrantResponse.model_validate(grant)


def _resource_grant_snapshot(grant: ResourceGrant) -> dict[str, object]:
    return {
        'id': grant.id,
        'subject_type': grant.subject_type,
        'subject_id': grant.subject_id,
        'resource_type': grant.resource_type,
        'resource_id': grant.resource_id,
        'permission_key': grant.permission_key,
    }


def _validate_resource_grant_resource(payload: ResourceGrantCreateRequest) -> None:
    policy_error = payload.resource_policy_error()
    if policy_error is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=policy_error)


def _validate_resource_grant_subject(db: Session, subject_type: str, subject_id: int) -> None:
    if subject_type == 'user' and db.get(User, subject_id) is not None:
        return
    if subject_type == 'group' and db.get(Group, subject_id) is not None:
        return
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'{subject_type.title()} subject not found')


def _build_rbac_matrix_user(db: Session, user: User) -> RbacMatrixUserResponse:
    role_permissions = sorted(DEFAULT_ROLE_PERMISSIONS.get(user.role, set()))
    direct_permissions = sorted(db.execute(select(UserPermission.permission_key).where(UserPermission.user_id == user.id)).scalars().all())
    group_rows = db.execute(
        select(Group.key, GroupPermission.permission_key)
        .join(UserGroup, UserGroup.group_id == Group.id)
        .join(GroupPermission, GroupPermission.group_id == Group.id)
        .where(UserGroup.user_id == user.id, Group.is_active.is_(True))
        .order_by(Group.key, GroupPermission.permission_key)
    ).all()
    group_permissions = [{'group': row[0], 'key': row[1]} for row in group_rows]
    effective: dict[str, set[str]] = {}
    for key in role_permissions:
        effective.setdefault(key, set()).add(f'role:{user.role}')
    for key in direct_permissions:
        effective.setdefault(key, set()).add('direct')
    for row in group_permissions:
        effective.setdefault(row['key'], set()).add(f"group:{row['group']}")
    group_ids = db.execute(select(UserGroup.group_id, Group.key).join(Group, Group.id == UserGroup.group_id).where(UserGroup.user_id == user.id, Group.is_active.is_(True))).all()
    resource_grants = [
        {'resource_type': row.resource_type, 'resource_id': row.resource_id, 'permission_key': row.permission_key, 'source': 'user'}
        for row in db.execute(select(ResourceGrant).where(ResourceGrant.subject_type == 'user', ResourceGrant.subject_id == user.id)).scalars().all()
    ]
    for group_id, group_key in group_ids:
        for row in db.execute(select(ResourceGrant).where(ResourceGrant.subject_type == 'group', ResourceGrant.subject_id == group_id)).scalars().all():
            resource_grants.append({'resource_type': row.resource_type, 'resource_id': row.resource_id, 'permission_key': row.permission_key, 'source': f'group:{group_key}'})
    return RbacMatrixUserResponse(user_id=user.id, username=user.username, role=user.role, role_permissions=role_permissions, direct_permissions=direct_permissions, group_permissions=group_permissions, effective_permissions=[{'key': key, 'sources': sorted(sources)} for key, sources in sorted(effective.items())], resource_grants=sorted(resource_grants, key=lambda item: (item['resource_type'], item['resource_id'], item['permission_key'], item['source'])))

def _serialize_group(db: Session, group: Group) -> GroupResponse:
    perms = db.execute(select(GroupPermission.permission_key).where(GroupPermission.group_id == group.id)).scalars().all()
    return GroupResponse(
        id=group.id,
        key=group.key,
        name=group.name,
        description=group.description,
        is_active=group.is_active,
        permissions=sorted(perms),
    )


def _ensure_service_modules(db: Session) -> None:
    existing_count = db.scalar(select(func.count(ServiceModule.id))) or 0
    if existing_count:
        return
    for row in DEFAULT_SERVICE_MODULES:
        db.add(ServiceModule(**row))
    db.flush()


def _backup_root(settings: Settings) -> Path:
    root = settings.managed_storage_root / 'admin_backups'
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def _safe_module_snapshot(module: ServiceModule) -> dict[str, object]:
    return {
        'key': module.key,
        'title': module.title,
        'description': module.description,
        'href': module.href,
        'section': module.section,
        'status': module.status,
        'badge': module.badge,
        'sort_order': module.sort_order,
        'is_enabled': module.is_enabled,
        'is_external': module.is_external,
        'visibility': module.visibility,
        'required_permission': module.required_permission,
        'resource_type': module.resource_type,
        'resource_id': module.resource_id,
    }


def _asset_root(storage: StorageService, asset_type: AssetType) -> tuple[str, Path]:
    if asset_type == AssetType.MARKDOWN:
        return 'markdown', storage.managed_root
    return 'import', storage.import_root


def _asset_path(storage: StorageService, asset_type: AssetType, relative_path: str) -> Path:
    if asset_type == AssetType.MARKDOWN:
        return storage.resolve_managed_relative_path(relative_path)
    return storage.resolve_external_relative_path(relative_path)


def _path_readable(path: Path) -> bool:
    try:
        if not path.exists():
            return False
        if path.is_dir():
            next(path.iterdir(), None)
        else:
            with path.open('rb'):
                pass
        return True
    except OSError:
        return False


def _root_missing_remediation(root: Path) -> str:
    return f'루트 경로 {root}를 확인하세요. _database/storage 위치를 가리켜야 하며 환경변수 override 오설정을 점검하세요.'


def _config_health(settings: Settings) -> ConfigHealthResponse:
    roots = [
        ('storage', settings.storage_root_path),
        ('import', settings.import_root),
        ('document', settings.document_root_path),
        ('civil', settings.civil_aircraft_root_path),
        ('nsa', settings.nsa_root_path),
        ('markdown', settings.markdown_root),
        ('thumbnails', settings.thumbnails_root),
    ]
    return ConfigHealthResponse(
        roots=[
            ConfigHealthItem(kind=kind, resolved_path=str(path), exists=path.exists(), readable=_path_readable(path))
            for kind, path in roots
        ]
    )

def _asset_health(db: Session, settings: Settings) -> AssetHealthResponse:
    storage = StorageService(settings)
    newsletters = NewsletterRepository(db).list_admin()
    items: list[AssetHealthItem] = []
    missing = 0
    mismatch = 0
    misconfig = 0
    ok_count = 0
    for newsletter in newsletters:
        for asset in newsletter.assets:
            root_kind, root = _asset_root(storage, asset.asset_type)
            exists = False
            size: int | None = None
            actual_checksum: str | None = None
            ok = False
            status_value: str = 'missing'
            error_code: str | None = 'FILE_NOT_FOUND'
            remediation = '해석된 자산 경로에 파일이 없습니다. 가져오기 루트와 DB 파일 경로를 확인하세요.'
            resolved_path: Path | None = None
            if not root.exists() or not root.is_dir() or not _path_readable(root):
                status_value = 'misconfig'
                error_code = 'ROOT_MISSING'
                remediation = _root_missing_remediation(root)
            else:
                try:
                    resolved_path = _asset_path(storage, asset.asset_type, asset.file_path)
                    exists = resolved_path.exists()
                    if exists:
                        data = resolved_path.read_bytes()
                        size = len(data)
                        actual_checksum = hash_file_bytes(data)
                        ok = not asset.checksum or asset.checksum == actual_checksum
                        if ok:
                            status_value = 'ok'
                            error_code = None
                            remediation = '정상입니다.'
                        else:
                            status_value = 'checksum_mismatch'
                            error_code = 'CHECKSUM_MISMATCH'
                            remediation = '파일은 있지만 DB 체크섬과 다릅니다. 원본 파일 변경 여부를 확인하고 재가져오기를 실행하세요.'
                    else:
                        status_value = 'missing'
                        error_code = 'FILE_NOT_FOUND'
                except StorageError:
                    status_value = 'misconfig'
                    error_code = 'PATH_ESCAPE'
                    remediation = 'DB 파일 경로가 허용된 루트 밖을 가리킵니다. 경로 값을 수정하거나 재가져오기 하세요.'
                except OSError:
                    exists = False
                    ok = False
                    status_value = 'missing'
                    error_code = 'FILE_NOT_FOUND'
            if status_value == 'ok':
                ok_count += 1
            elif status_value == 'missing':
                missing += 1
            elif status_value == 'checksum_mismatch':
                mismatch += 1
            else:
                misconfig += 1
            items.append(
                AssetHealthItem(
                    newsletter_id=newsletter.id,
                    newsletter_title=newsletter.title,
                    asset_type=asset.asset_type.value,
                    file_path=asset.file_path,
                    exists=exists,
                    file_size=size,
                    checksum=actual_checksum,
                    expected_checksum=asset.checksum,
                    ok=ok,
                    status=status_value,
                    resolved_root=str(root),
                    resolved_path=str(resolved_path) if resolved_path is not None else None,
                    root_kind=root_kind,
                    remediation=remediation,
                    error_code=error_code,
                )
            )
    return AssetHealthResponse(ok=ok_count, missing=missing, checksum_mismatch=mismatch, misconfig=misconfig, items=items)


def _user_can_access_module(db: Session, user: User | None, module: ServiceModule) -> bool:
    required_permission = module.required_permission
    if not required_permission:
        return True
    if user is None:
        return False
    if has_permission(db, user, required_permission):
        return True
    if module.resource_type and module.resource_id and has_resource_permission(db, user, module.resource_type, module.resource_id, required_permission):
        return True
    if module.resource_type == 'collection' and module.resource_id:
        return can_read_collection(db, user, module.resource_id)
    return False


@router.get('/service-modules/public', response_model=list[ServiceModuleResponse])
def public_service_modules(db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)) -> list[ServiceModuleResponse]:
    _ensure_service_modules(db)
    modules = db.execute(select(ServiceModule).order_by(ServiceModule.sort_order, ServiceModule.id)).scalars().all()
    is_operator = bool(user and user.role == 'admin')
    if not is_operator:
        # Non-operators only see public-audience modules. Development/coming-soon
        # surfaces are operator-only and never leak to the anonymous dashboard.
        modules = [
            module
            for module in modules
            if module.visibility == 'public' and module.is_enabled and _user_can_access_module(db, user, module)
        ]
    return [ServiceModuleResponse.model_validate(module) for module in modules]


@router.get('/dashboard', response_model=AdminSummaryResponse, dependencies=[Depends(require_permission('admin.audit.read'))])
def admin_summary(settings: Settings = Depends(get_settings), db: Session = Depends(get_db)) -> AdminSummaryResponse:
    _ensure_service_modules(db)
    health = _asset_health(db, settings)
    latest = db.execute(select(Newsletter).order_by(Newsletter.published_at.desc().nullslast(), Newsletter.created_at.desc())).scalars().first()
    modules = db.execute(select(ServiceModule)).scalars().all()
    read_summary = _read_tracking_summary(db)
    audits = db.execute(select(AdminAuditEvent).order_by(AdminAuditEvent.created_at.desc()).limit(10)).scalars().all()
    ai_status = AiChatService(settings).status()
    return AdminSummaryResponse(
        app_version=settings.app_version,
        app_env=settings.app_env,
        database_url=settings.database_url,
        db_ok=True,
        newsletter_total=db.scalar(select(func.count(Newsletter.id))) or 0,
        latest_newsletter_title=latest.title if latest else None,
        active_modules=sum(1 for module in modules if module.is_enabled),
        coming_soon_modules=sum(1 for module in modules if module.status == 'coming_soon'),
        asset_health={'ok': health.ok, 'missing': health.missing, 'checksum_mismatch': health.checksum_mismatch, 'misconfig': health.misconfig},
        read_summary=read_summary,
        ai_status=ai_status,
        recent_audit_events=[AuditEventResponse.model_validate(event) for event in audits],
    )


@router.get('/sessions', response_model=ConnectedUsersResponse, dependencies=[Depends(require_permission('admin.sessions.read'))])
def connected_sessions(settings: Settings = Depends(get_settings), db: Session = Depends(get_db)) -> ConnectedUsersResponse:
    now = datetime.now(UTC)
    active_since = now - timedelta(minutes=settings.access_token_ttl_minutes)
    sessions = db.execute(
        select(UserSessionActivity.user_id, User.username, func.max(UserSessionActivity.last_seen_at))
        .join(User, User.id == UserSessionActivity.user_id)
        .where(UserSessionActivity.last_seen_at >= active_since)
        .group_by(UserSessionActivity.user_id, User.username)
        .order_by(func.max(UserSessionActivity.last_seen_at).desc())
    ).all()
    events = db.execute(select(LoginEvent).order_by(LoginEvent.created_at.desc(), LoginEvent.id.desc()).limit(25)).scalars().all()
    failure_count = db.scalar(select(func.count(LoginEvent.id)).where(LoginEvent.status == 'failure')) or 0
    return ConnectedUsersResponse(
        active_sessions=[{'user_id': row[0], 'username': row[1], 'last_seen_at': row[2]} for row in sessions],
        active_count=len(sessions),
        recent_login_events=events,
        login_failure_count=int(failure_count),
        read_tracking_summary=_read_tracking_summary(db),
    )


@router.post('/sessions/purge', response_model=SessionPurgeResponse, dependencies=[Depends(require_permission('admin.sessions.purge')), Depends(require_csrf)])
def purge_connected_sessions(request: Request, settings: Settings = Depends(get_settings), db: Session = Depends(get_db), actor: User = Depends(get_current_user)) -> SessionPurgeResponse:
    cutoff = datetime.now(UTC) - timedelta(days=_connected_user_retention_days(settings))
    login_result = db.execute(delete(LoginEvent).where(LoginEvent.created_at < cutoff))
    session_result = db.execute(delete(UserSessionActivity).where(UserSessionActivity.last_seen_at < cutoff))
    counts = {
        'login_events_deleted': int(login_result.rowcount or 0),
        'session_activity_deleted': int(session_result.rowcount or 0),
    }
    record_admin_audit(db, actor=actor, action='admin.sessions.purge', target_type='session_activity', target_id=None, request=request, metadata=counts)
    db.flush()
    return SessionPurgeResponse(**counts)


@router.get('/permissions', response_model=list[PermissionResponse], dependencies=[Depends(require_permission('admin.rbac.read'))])
def list_permissions() -> list[PermissionResponse]:
    return [PermissionResponse(key=key) for key in sorted(ADMIN_PERMISSIONS)]


@router.get('/users', response_model=list[UserAdminResponse], dependencies=[Depends(require_permission('admin.users.read'))])
def list_users(db: Session = Depends(get_db)) -> list[UserAdminResponse]:
    users = db.execute(select(User).order_by(User.id)).scalars().all()
    return [_serialize_user(db, user) for user in users]


def _has_other_active_admin(db: Session, user: User) -> bool:
    rows = db.execute(select(User).where(User.id != user.id, User.is_active.is_(True), User.role == 'admin')).scalars().all()
    return any('admin.rbac.manage' in list_user_permission_keys(db, row) for row in rows)


@router.post('/users', response_model=UserAdminResponse, dependencies=[Depends(require_permission('admin.users.manage')), Depends(require_csrf)])
def create_user(payload: UserCreateRequest, request: Request, db: Session = Depends(get_db), actor: User = Depends(get_current_user)) -> UserAdminResponse:
    username = _required_text(payload.username, 'username')
    if not payload.password.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='password is required')
    if UserRepository(db).get_by_username(username):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='User already exists')
    user = User(
        username=username,
        email=_optional_text(payload.email),
        display_name=_optional_text(payload.display_name),
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=payload.is_active,
        session_version=0,
    )
    db.add(user)
    db.flush()
    record_admin_audit(
        db,
        actor=actor,
        action='user.create',
        target_type='user',
        target_id=user.id,
        request=request,
        after={'username': user.username, 'role': user.role, 'is_active': user.is_active, 'email': user.email, 'display_name': user.display_name},
    )
    return _serialize_user(db, user)


@router.patch('/users/{user_id}', response_model=UserAdminResponse, dependencies=[Depends(require_permission('admin.users.manage')), Depends(require_csrf)])
def update_user(user_id: int, payload: UserUpdateRequest, request: Request, db: Session = Depends(get_db), actor: User = Depends(get_current_user)) -> UserAdminResponse:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
    before = {'role': user.role, 'is_active': user.is_active, 'email': user.email, 'display_name': user.display_name, 'permissions': sorted(list_user_permission_keys(db, user))}
    fields_set = payload.model_fields_set
    new_role = payload.role if payload.role is not None else user.role
    new_active = payload.is_active if payload.is_active is not None else user.is_active
    if user.id == actor.id and (not new_active or new_role != user.role):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Self lockout is not allowed')
    would_remove_admin = user.is_active and user.role == 'admin' and (not new_active or new_role != 'admin')
    if would_remove_admin and not _has_other_active_admin(db, user):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='At least one active admin must remain')
    if 'email' in fields_set:
        user.email = _optional_text(payload.email)
    if 'display_name' in fields_set:
        user.display_name = _optional_text(payload.display_name)
    user.role = new_role
    user.is_active = new_active
    if payload.permissions is not None:
        db.query(UserPermission).filter(UserPermission.user_id == user.id).delete(synchronize_session=False)
        for key in sorted(set(payload.permissions)):
            if key not in ADMIN_PERMISSIONS:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'Unknown permission: {key}')
            db.add(UserPermission(user_id=user.id, permission_key=key))
    user.session_version += 1
    db.flush()
    after = {'role': user.role, 'is_active': user.is_active, 'email': user.email, 'display_name': user.display_name, 'permissions': sorted(list_user_permission_keys(db, user))}
    record_admin_audit(db, actor=actor, action='user.update', target_type='user', target_id=user.id, request=request, before=before, after=after)
    return _serialize_user(db, user)


@router.post('/users/{user_id}/password-reset', response_model=UserAdminResponse, dependencies=[Depends(require_permission('admin.users.reset_password')), Depends(require_csrf)])
def reset_user_password(user_id: int, payload: PasswordResetRequest, request: Request, db: Session = Depends(get_db), actor: User = Depends(get_current_user)) -> UserAdminResponse:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
    user.password_hash = hash_password(payload.temporary_password)
    user.session_version += 1
    db.flush()
    record_admin_audit(db, actor=actor, action='user.password_reset', target_type='user', target_id=user.id, request=request, metadata={'temporary_password': '[REDACTED]'})
    return _serialize_user(db, user)


@router.get('/groups', response_model=list[GroupResponse], dependencies=[Depends(require_permission('admin.rbac.read'))])
def list_groups(db: Session = Depends(get_db)) -> list[GroupResponse]:
    groups = db.execute(select(Group).order_by(Group.key)).scalars().all()
    return [_serialize_group(db, group) for group in groups]


@router.post('/groups', response_model=GroupResponse, dependencies=[Depends(require_permission('admin.rbac.manage')), Depends(require_csrf)])
def upsert_group(payload: GroupUpsertRequest, request: Request, db: Session = Depends(get_db), actor: User = Depends(get_current_user)) -> GroupResponse:
    group = db.scalar(select(Group).where(Group.key == payload.key))
    before = None
    if group is None:
        group = Group(key=payload.key, name=payload.name)
        db.add(group)
        action = 'group.create'
    else:
        before = _serialize_group(db, group).model_dump()
        action = 'group.update'
    group.name = payload.name
    group.description = payload.description
    group.is_active = payload.is_active
    db.flush()
    db.query(GroupPermission).filter(GroupPermission.group_id == group.id).delete(synchronize_session=False)
    for key in sorted(set(payload.permissions)):
        if key not in ADMIN_PERMISSIONS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'Unknown permission: {key}')
        db.add(GroupPermission(group_id=group.id, permission_key=key))
    db.flush()
    # Group active-flag/permission changes affect every member's effective permissions;
    # bump their session_version so stale sessions cannot keep old authorization.
    bump_group_members(db, group.id)
    after = _serialize_group(db, group).model_dump()
    record_admin_audit(db, actor=actor, action=action, target_type='group', target_id=group.id, request=request, before=before, after=after)
    return _serialize_group(db, group)




@router.get('/rbac-matrix', response_model=list[RbacMatrixUserResponse], dependencies=[Depends(require_permission('admin.rbac.read'))])
def get_rbac_matrix(db: Session = Depends(get_db)) -> list[RbacMatrixUserResponse]:
    users = db.execute(select(User).order_by(User.id)).scalars().all()
    return [_build_rbac_matrix_user(db, user) for user in users]


@router.get('/resource-grants', response_model=list[ResourceGrantResponse], dependencies=[Depends(require_permission('admin.resource_grants.read'))])
def list_resource_grants(subject_type: str | None = None, subject_id: int | None = None, db: Session = Depends(get_db)) -> list[ResourceGrantResponse]:
    stmt = select(ResourceGrant).order_by(ResourceGrant.id)
    if subject_type is not None:
        if subject_type not in {'user', 'group'}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid subject_type')
        stmt = stmt.where(ResourceGrant.subject_type == subject_type)
    if subject_id is not None:
        stmt = stmt.where(ResourceGrant.subject_id == subject_id)
    return [_serialize_resource_grant(grant) for grant in db.execute(stmt).scalars().all()]


@router.post('/resource-grants', response_model=ResourceGrantResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission('admin.resource_grants.manage')), Depends(require_csrf)])
def create_resource_grant(payload: ResourceGrantCreateRequest, request: Request, db: Session = Depends(get_db), actor: User = Depends(get_current_user)) -> ResourceGrantResponse:
    _validate_resource_grant_subject(db, payload.subject_type, payload.subject_id)
    _validate_resource_grant_resource(payload)
    grant = ResourceGrant(**payload.model_dump())
    db.add(grant)
    try:
        db.flush()
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Resource grant already exists') from exc
    bump_authorization_session_versions(db, users_affected_by_resource_grant(db, grant.subject_type, grant.subject_id))
    record_admin_audit(db, actor=actor, action='resource_grant.create', target_type='resource_grant', target_id=grant.id, request=request, after=_resource_grant_snapshot(grant))
    return _serialize_resource_grant(grant)


@router.delete('/resource-grants/{grant_id}', status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permission('admin.resource_grants.manage')), Depends(require_csrf)])
def delete_resource_grant(grant_id: int, request: Request, db: Session = Depends(get_db), actor: User = Depends(get_current_user)) -> Response:
    grant = db.get(ResourceGrant, grant_id)
    if grant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Resource grant not found')
    before = _resource_grant_snapshot(grant)
    affected_user_ids = users_affected_by_resource_grant(db, grant.subject_type, grant.subject_id)
    db.delete(grant)
    db.flush()
    bump_authorization_session_versions(db, affected_user_ids)
    record_admin_audit(db, actor=actor, action='resource_grant.delete', target_type='resource_grant', target_id=grant_id, request=request, before=before)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post('/users/{user_id}/groups/{group_id}', response_model=UserAdminResponse, dependencies=[Depends(require_permission('admin.rbac.manage')), Depends(require_csrf)])
def add_user_group(user_id: int, group_id: int, request: Request, db: Session = Depends(get_db), actor: User = Depends(get_current_user)) -> UserAdminResponse:
    user = db.get(User, user_id)
    group = db.get(Group, group_id)
    if user is None or group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User or group not found')
    if db.get(UserGroup, {'user_id': user_id, 'group_id': group_id}) is None:
        db.add(UserGroup(user_id=user_id, group_id=group_id))
        bump_authorization_session_versions(db, [user_id])
        db.flush()
        record_admin_audit(db, actor=actor, action='user_group.add', target_type='user', target_id=user_id, request=request, after={'group_id': group_id, 'group_key': group.key})
    return _serialize_user(db, user)


@router.delete('/users/{user_id}/groups/{group_id}', response_model=UserAdminResponse, dependencies=[Depends(require_permission('admin.rbac.manage')), Depends(require_csrf)])
def remove_user_group(user_id: int, group_id: int, request: Request, db: Session = Depends(get_db), actor: User = Depends(get_current_user)) -> UserAdminResponse:
    user = db.get(User, user_id)
    membership = db.get(UserGroup, {'user_id': user_id, 'group_id': group_id})
    group = db.get(Group, group_id)
    if user is None or group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User or group not found')
    if membership is not None:
        db.delete(membership)
        db.flush()
        bump_authorization_session_versions(db, [user_id])
        record_admin_audit(db, actor=actor, action='user_group.remove', target_type='user', target_id=user_id, request=request, before={'group_id': group_id, 'group_key': group.key})
    return _serialize_user(db, user)


@router.get('/audit-events', response_model=list[AuditEventResponse], dependencies=[Depends(require_permission('admin.audit.read'))])
def list_audit_events(limit: int = 100, db: Session = Depends(get_db)) -> list[AuditEventResponse]:
    limit = min(max(limit, 1), 500)
    events = db.execute(select(AdminAuditEvent).order_by(AdminAuditEvent.created_at.desc()).limit(limit)).scalars().all()
    return [AuditEventResponse.model_validate(event) for event in events]


@router.get('/service-modules', response_model=list[ServiceModuleResponse], dependencies=[Depends(require_permission('admin.dashboard.manage'))])
def list_service_modules(db: Session = Depends(get_db)) -> list[ServiceModuleResponse]:
    _ensure_service_modules(db)
    modules = db.execute(select(ServiceModule).order_by(ServiceModule.sort_order, ServiceModule.id)).scalars().all()
    return [ServiceModuleResponse.model_validate(module) for module in modules]


@router.post('/service-modules', response_model=ServiceModuleResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission('admin.dashboard.manage')), Depends(require_csrf)])
def create_service_module(payload: ServiceModuleCreateRequest, request: Request, db: Session = Depends(get_db), actor: User = Depends(get_current_user)) -> ServiceModuleResponse:
    if db.scalar(select(ServiceModule).where(ServiceModule.key == payload.key)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Service module key already exists')
    module = ServiceModule(**payload.model_dump())
    db.add(module)
    db.flush()
    record_admin_audit(db, actor=actor, action='service_module.create', target_type='service_module', target_id=module.key, request=request, after=_safe_module_snapshot(module))
    return ServiceModuleResponse.model_validate(module)


@router.delete('/service-modules/{module_id}', status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permission('admin.dashboard.manage')), Depends(require_csrf)])
def delete_service_module(module_id: int, request: Request, db: Session = Depends(get_db), actor: User = Depends(get_current_user)) -> Response:
    module = db.get(ServiceModule, module_id)
    if module is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Service module not found')
    before = _safe_module_snapshot(module)
    db.delete(module)
    db.flush()
    record_admin_audit(db, actor=actor, action='service_module.delete', target_type='service_module', target_id=before['key'], request=request, before=before)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch('/service-modules/{module_id}', response_model=ServiceModuleResponse, dependencies=[Depends(require_permission('admin.dashboard.manage')), Depends(require_csrf)])
def update_service_module(module_id: int, payload: ServiceModuleUpdateRequest, request: Request, db: Session = Depends(get_db), actor: User = Depends(get_current_user)) -> ServiceModuleResponse:
    _ensure_service_modules(db)
    module = db.get(ServiceModule, module_id)
    if module is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Service module not found')
    before = _safe_module_snapshot(module)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(module, field, value)
    db.flush()
    record_admin_audit(db, actor=actor, action='service_module.update', target_type='service_module', target_id=module.key, request=request, before=before, after=_safe_module_snapshot(module))
    return ServiceModuleResponse.model_validate(module)


@router.get('/newsletters/assets/health', response_model=AssetHealthResponse, dependencies=[Depends(require_permission('admin.newsletters.read'))])
def newsletter_asset_health(settings: Settings = Depends(get_settings), db: Session = Depends(get_db)) -> AssetHealthResponse:
    return _asset_health(db, settings)


@router.get('/config/health', response_model=ConfigHealthResponse, dependencies=[Depends(require_permission('admin.audit.read'))])
def config_health(settings: Settings = Depends(get_settings)) -> ConfigHealthResponse:
    return _config_health(settings)


@router.post('/newsletters/bulk', response_model=BulkNewsletterResponse, dependencies=[Depends(require_permission('admin.newsletters.bulk')), Depends(require_csrf)])
def bulk_newsletter_update(payload: BulkNewsletterRequest, request: Request, db: Session = Depends(get_db), actor: User = Depends(get_current_user)) -> BulkNewsletterResponse:
    status_map = {'publish': 'published', 'archive': 'archived', 'draft': 'draft'}
    new_status = status_map[payload.action]
    newsletters = db.execute(select(Newsletter).where(Newsletter.id.in_(payload.ids))).scalars().all()
    for newsletter in newsletters:
        newsletter.status = new_status
        newsletter.is_active = new_status == 'published'
        newsletter.status_changed_at = func.now()
        newsletter.status_changed_by_user_id = actor.id
    db.flush()
    record_admin_audit(db, actor=actor, action='newsletter.bulk', target_type='newsletter', request=request, metadata={'ids': payload.ids, 'action': payload.action, 'updated': len(newsletters)})
    return BulkNewsletterResponse(updated=len(newsletters))


@router.get('/backups', response_model=list[BackupRecordResponse], dependencies=[Depends(require_permission('admin.backup.read'))])
def list_backups(db: Session = Depends(get_db)) -> list[BackupRecordResponse]:
    rows = db.execute(select(BackupRecord).order_by(BackupRecord.created_at.desc())).scalars().all()
    return [BackupRecordResponse.model_validate(row) for row in rows]


def _create_manifest(settings: Settings, filename: str) -> dict[str, object]:
    return {
        'schema_version': 1,
        'app_version': settings.app_version,
        'created_at': datetime.now(UTC).isoformat(),
        'filename': filename,
        'included_roots': ['sqlite_database', 'storage/markdown', 'storage/thumbnails'],
        'notes': 'AeroOne admin backup excludes public/static roots and validates checksums before download.',
    }


@router.post('/backups', response_model=BackupCreateResponse, dependencies=[Depends(require_permission('admin.backup.create')), Depends(require_csrf)])
def create_backup(request: Request, settings: Settings = Depends(get_settings), db: Session = Depends(get_db), actor: User = Depends(get_current_user)) -> BackupCreateResponse:
    root = _backup_root(settings)
    stamp = datetime.now(UTC).strftime('%Y%m%d-%H%M%S-%f')
    filename = f'aeroone-backup-{stamp}-{secrets.token_hex(4)}.zip'
    target = root / filename
    tmp_target = root / f'.{filename}.tmp'
    manifest = _create_manifest(settings, filename)
    with zipfile.ZipFile(tmp_target, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
        sqlite_path = settings.sqlite_path
        if sqlite_path and sqlite_path.exists():
            archive.write(sqlite_path, 'sqlite/aeroone.db')
        for base, arc_prefix in [(settings.markdown_root, 'storage/markdown/newsletters'), (settings.thumbnails_root, 'storage/thumbnails')]:
            if not base.exists():
                continue
            for path in base.rglob('*'):
                if path.is_symlink() or not path.is_file():
                    continue
                rel = path.relative_to(base).as_posix()
                archive.write(path, f'{arc_prefix}/{rel}')
    digest = sha256_for_file(tmp_target)
    record = BackupRecord(
        filename=filename,
        file_path=str(target),
        sha256=digest,
        file_size=tmp_target.stat().st_size,
        manifest_json=json.dumps(manifest, ensure_ascii=False, sort_keys=True),
        created_by_user_id=actor.id,
    )
    db.add(record)
    db.flush()
    record_admin_audit(db, actor=actor, action='backup.create', target_type='backup', target_id=filename, request=request, after={'filename': filename, 'sha256': digest})
    tmp_target.replace(target)
    return BackupCreateResponse(**BackupRecordResponse.model_validate(record).model_dump(), manifest=manifest)


def _validate_backup_file(path: Path, expected_sha: str | None = None) -> BackupValidationResponse:
    issues: list[str] = []
    manifest: dict[str, object] | None = None
    if not path.exists():
        return BackupValidationResponse(filename=path.name, valid=False, issues=['backup file is missing'])
    if expected_sha and sha256_for_file(path) != expected_sha:
        issues.append('sha256 mismatch')
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if 'manifest.json' not in names:
                issues.append('manifest.json missing')
            else:
                manifest = json.loads(archive.read('manifest.json').decode('utf-8'))
            seen: set[str] = set()
            for name in names:
                pure = Path(name)
                if name in seen:
                    issues.append(f'duplicate path: {name}')
                seen.add(name)
                if pure.is_absolute() or '..' in pure.parts or ':' in name:
                    issues.append(f'unsafe path: {name}')
    except (zipfile.BadZipFile, OSError, json.JSONDecodeError) as exc:
        issues.append(str(exc))
    return BackupValidationResponse(filename=path.name, valid=not issues, issues=issues, manifest=manifest)


@router.post('/backups/{backup_id}/validate', response_model=BackupValidationResponse, dependencies=[Depends(require_permission('admin.backup.read')), Depends(require_csrf)])
def validate_backup(backup_id: int, request: Request, db: Session = Depends(get_db), actor: User = Depends(get_current_user)) -> BackupValidationResponse:
    record = db.get(BackupRecord, backup_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Backup not found')
    result = _validate_backup_file(Path(record.file_path), record.sha256)
    record_admin_audit(db, actor=actor, action='backup.validate', target_type='backup', target_id=record.filename, request=request, metadata=result.model_dump())
    return result


@router.post('/backups/{backup_id}/restore/dry-run', response_model=BackupRestoreDryRunResponse, dependencies=[Depends(require_permission('admin.restore.execute')), Depends(require_csrf)])
def dry_run_restore_backup(backup_id: int, request: Request, db: Session = Depends(get_db), actor: User = Depends(get_current_user)) -> BackupRestoreDryRunResponse:
    record = db.get(BackupRecord, backup_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Backup not found')
    validation = _validate_backup_file(Path(record.file_path), record.sha256)
    issues = list(validation.issues)
    manifest = validation.manifest
    if manifest is None:
        issues.append('manifest unavailable for restore dry-run')
    elif manifest.get('schema_version') != 1:
        issues.append('unsupported backup manifest schema')
    compatible = validation.valid and not issues
    would_restore: list[str] = []
    if compatible and manifest:
        would_restore = [str(item) for item in manifest.get('included_roots', [])]
    result = BackupRestoreDryRunResponse(
        filename=record.filename,
        valid=validation.valid,
        compatible=compatible,
        issues=issues,
        would_restore=would_restore,
        manifest=manifest,
    )
    record_admin_audit(db, actor=actor, action='backup.restore_dry_run', target_type='backup', target_id=record.filename, request=request, metadata=result.model_dump())
    return result


@router.get('/backups/{backup_id}/download', dependencies=[Depends(require_permission('admin.backup.create'))])
def download_backup(backup_id: int, db: Session = Depends(get_db)) -> FileResponse:
    record = db.get(BackupRecord, backup_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Backup not found')
    path = Path(record.file_path)
    if not path.exists() or _validate_backup_file(path, record.sha256).valid is False:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Backup validation failed')
    return FileResponse(path, media_type='application/zip', filename=record.filename)


@router.get('/read-events.csv', dependencies=[Depends(require_permission('admin.read_tracking.read'))])
def export_read_events_csv(db: Session = Depends(get_db)) -> PlainTextResponse:
    rows = db.execute(select(NewsletterReadEvent).order_by(NewsletterReadEvent.last_seen_at.desc())).scalars().all()
    lines = ['newsletter_id,client_ip,read_count,first_seen_at,last_seen_at']
    for row in rows:
        lines.append(f'{row.newsletter_id},{row.client_ip},{row.read_count},{row.first_seen_at},{row.last_seen_at}')
    return PlainTextResponse('\n'.join(lines) + '\n', media_type='text/csv; charset=utf-8')


@router.get('/search', response_model=UnifiedSearchResponse)
def unified_search(q: str, include_nsa: bool = False, db: Session = Depends(get_db), settings: Settings = Depends(get_settings), user: User | None = Depends(get_current_user)) -> UnifiedSearchResponse:
    if len(q.strip()) < 2:
        return UnifiedSearchResponse(query=q, results=[])
    collections = ['document', 'civil']
    if include_nsa and can_read_collection(db, user, 'nsa'):
        collections.append('nsa')
    roots_by_key = {'document': settings.document_root_path, 'civil': settings.civil_aircraft_root_path, 'nsa': settings.nsa_root_path}
    roots = [CollectionSearchRoot(collection=key, root=roots_by_key[key]) for key in collections]
    try:
        collection_results = HtmlCollectionSearchService().search(roots, q, settings.managed_storage_root, limit=20)
        degraded = False
        reason = None
    except CollectionSearchUnavailable as exc:
        collection_results = []
        degraded = True
        reason = str(exc)
    newsletter_rows = NewsletterRepository(db).list_public(q=q)[:20]
    results = [
        UnifiedSearchResult(source='newsletter', title=item.title, snippet=item.description or item.summary or '', url=f'/newsletters/{item.slug}', score=1.0)
        for item in newsletter_rows
    ]
    results.extend(
        UnifiedSearchResult(source=result.collection, title=result.name, snippet=result.snippet, url=result.navigation_url, score=result.score)
        for result in collection_results
    )
    return UnifiedSearchResponse(query=q, results=results[:30], degraded=degraded, reason=reason)


@router.get('/ai/status', dependencies=[Depends(require_permission('admin.ai.read'))])
def admin_ai_status(settings: Settings = Depends(get_settings), db: Session = Depends(get_db)) -> dict[str, object]:
    status_payload = AiChatService(settings).status()
    logs_total = db.scalar(select(func.count(AiRequestLog.id))) or 0
    failures = db.scalar(select(func.count(AiRequestLog.id)).where(AiRequestLog.status != 'ok')) or 0
    return {'status': status_payload, 'request_logs_total': logs_total, 'request_failures': failures}
