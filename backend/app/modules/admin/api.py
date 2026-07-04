from __future__ import annotations

from datetime import UTC, datetime
import secrets
import json
from pathlib import Path

import zipfile

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import hash_file_bytes, hash_password
from app.modules.admin.audit import record_admin_audit
from app.modules.admin.models import (
    AdminAuditEvent,
    BackupRecord,
    Group,
    GroupPermission,
    ServiceModule,
    UserPermission,
    AiRequestLog,
)
from app.modules.admin.permissions import ADMIN_PERMISSIONS, list_user_permission_keys
from app.modules.admin.session_fanout import bump_group_members
from app.modules.admin.schemas import (
    AdminSummaryResponse,
    AssetHealthItem,
    AssetHealthResponse,
    AuditEventResponse,
    BackupCreateResponse,
    BackupRecordResponse,
    BackupValidationResponse,
    BackupRestoreDryRunResponse,
    BulkNewsletterRequest,
    BulkNewsletterResponse,
    GroupResponse,
    GroupUpsertRequest,
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
from app.modules.newsletter.services.newsletter_service import NewsletterService
from app.modules.newsletter.services.utils import slugify
from app.modules.read_tracking.models.read_event import NewsletterReadEvent
from app.modules.shared.storage.service import StorageError, StorageService, sha256_for_file

router = APIRouter()

DEFAULT_SERVICE_MODULES = [
    {'key': 'newsletter', 'title': 'Newsletter', 'description': None, 'href': '/newsletters', 'section': 'Newsletter', 'status': 'active', 'badge': 'Active', 'sort_order': 10, 'is_enabled': True, 'is_external': False, 'visibility': 'public'},
    {'key': 'civil-aircraft', 'title': 'Civil Aircraft Spec Catalog', 'description': 'Commercial aircraft specs & market competition analysis.', 'href': '/reports/civil-aircraft', 'section': 'Document', 'status': 'active', 'badge': 'Active', 'sort_order': 20, 'is_enabled': True, 'is_external': False, 'visibility': 'public'},
    {'key': 'document', 'title': 'Document', 'description': 'Browse HTML documents organized in folders.', 'href': '/documents', 'section': 'Document', 'status': 'active', 'badge': 'Active', 'sort_order': 30, 'is_enabled': True, 'is_external': False, 'visibility': 'public'},
    {'key': 'nsa', 'title': 'NSA', 'description': 'Password-protected HTML documents.', 'href': '/nsa', 'section': 'Document', 'status': 'active', 'badge': 'Active', 'sort_order': 40, 'is_enabled': True, 'is_external': False, 'visibility': 'public'},
    {'key': 'viewer', 'title': 'Viewer', 'description': '로컬 Markdown·HTML 파일을 열어 보고 편집 (서버 sanitize 미리보기).', 'href': '/viewer', 'section': 'Development', 'status': 'development', 'badge': 'Active', 'sort_order': 50, 'is_enabled': True, 'is_external': False, 'visibility': 'admin'},
    {'key': 'ai', 'title': 'AeroAI', 'description': '사내 폐쇄망 문서를 근거로 답하는 AI 어시스턴트.', 'href': '/ai', 'section': 'Development', 'status': 'development', 'badge': 'Active', 'sort_order': 60, 'is_enabled': True, 'is_external': False, 'visibility': 'admin'},
    {'key': 'open-notebook', 'title': 'Notebook', 'description': 'NotebookLM 대안 — 소스 정리·요약·벡터 검색 (별도 폐쇄망 앱).', 'href': '', 'section': 'Development', 'status': 'development', 'badge': 'Active', 'sort_order': 70, 'is_enabled': True, 'is_external': True, 'visibility': 'admin'},
    {'key': 'ladder', 'title': 'Ladder', 'description': 'Coffee-bet ladder game (사다리타기).', 'href': '/games/ladder', 'section': 'Development', 'status': 'development', 'badge': 'Active', 'sort_order': 80, 'is_enabled': True, 'is_external': False, 'visibility': 'admin'},
    {'key': 'announcement', 'title': 'Announcement', 'description': 'Company-wide announcements module.', 'href': '#', 'section': 'Development', 'status': 'coming_soon', 'badge': 'Coming soon', 'sort_order': 90, 'is_enabled': False, 'is_external': False, 'visibility': 'admin'},
    {'key': 'schedule', 'title': 'Schedule', 'description': 'Shared calendar & event tracking.', 'href': '#', 'section': 'Development', 'status': 'coming_soon', 'badge': 'Coming soon', 'sort_order': 100, 'is_enabled': False, 'is_external': False, 'visibility': 'admin'},
]


def _serialize_user(db: Session, user: User) -> UserAdminResponse:
    return UserAdminResponse.model_validate(user).model_copy(update={'permissions': sorted(list_user_permission_keys(db, user))})


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
    }


def _asset_path(storage: StorageService, asset_type: AssetType, relative_path: str) -> Path:
    if asset_type == AssetType.MARKDOWN:
        return storage.resolve_managed_relative_path(relative_path)
    return storage.resolve_external_relative_path(relative_path)


def _asset_health(db: Session, settings: Settings) -> AssetHealthResponse:
    storage = StorageService(settings)
    newsletters = NewsletterRepository(db).list_admin()
    items: list[AssetHealthItem] = []
    missing = 0
    mismatch = 0
    ok_count = 0
    for newsletter in newsletters:
        for asset in newsletter.assets:
            exists = False
            size: int | None = None
            actual_checksum: str | None = None
            ok = False
            try:
                path = _asset_path(storage, asset.asset_type, asset.file_path)
                exists = path.exists()
                if exists:
                    data = path.read_bytes()
                    size = len(data)
                    actual_checksum = hash_file_bytes(data)
                    ok = not asset.checksum or asset.checksum == actual_checksum
            except (StorageError, OSError):
                exists = False
                ok = False
            if ok:
                ok_count += 1
            elif not exists:
                missing += 1
            else:
                mismatch += 1
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
                )
            )
    return AssetHealthResponse(ok=ok_count, missing=missing, checksum_mismatch=mismatch, items=items)


@router.get('/service-modules/public', response_model=list[ServiceModuleResponse])
def public_service_modules(db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)) -> list[ServiceModuleResponse]:
    _ensure_service_modules(db)
    modules = db.execute(select(ServiceModule).order_by(ServiceModule.sort_order, ServiceModule.id)).scalars().all()
    is_operator = bool(user and user.role == 'admin')
    if not is_operator:
        # Non-operators only see public-audience modules. Development/coming-soon
        # surfaces are operator-only and never leak to the anonymous dashboard.
        modules = [module for module in modules if module.visibility == 'public' and module.is_enabled]
    return [ServiceModuleResponse.model_validate(module) for module in modules]


@router.get('/dashboard', response_model=AdminSummaryResponse, dependencies=[Depends(require_permission('admin.audit.read'))])
def admin_summary(settings: Settings = Depends(get_settings), db: Session = Depends(get_db)) -> AdminSummaryResponse:
    _ensure_service_modules(db)
    health = _asset_health(db, settings)
    latest = db.execute(select(Newsletter).order_by(Newsletter.published_at.desc().nullslast(), Newsletter.created_at.desc())).scalars().first()
    modules = db.execute(select(ServiceModule)).scalars().all()
    read_rows = db.execute(select(func.count(NewsletterReadEvent.id), func.coalesce(func.sum(NewsletterReadEvent.read_count), 0))).one()
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
        asset_health={'ok': health.ok, 'missing': health.missing, 'checksum_mismatch': health.checksum_mismatch},
        read_summary={'rows': int(read_rows[0] or 0), 'total_reads': int(read_rows[1] or 0)},
        ai_status=ai_status,
        recent_audit_events=[AuditEventResponse.model_validate(event) for event in audits],
    )


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
    if UserRepository(db).get_by_username(payload.username):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='User already exists')
    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=payload.is_active,
        session_version=0,
    )
    db.add(user)
    db.flush()
    record_admin_audit(db, actor=actor, action='user.create', target_type='user', target_id=user.id, request=request, after={'username': user.username, 'role': user.role, 'is_active': user.is_active})
    return _serialize_user(db, user)


@router.patch('/users/{user_id}', response_model=UserAdminResponse, dependencies=[Depends(require_permission('admin.users.manage')), Depends(require_csrf)])
def update_user(user_id: int, payload: UserUpdateRequest, request: Request, db: Session = Depends(get_db), actor: User = Depends(get_current_user)) -> UserAdminResponse:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
    before = {'role': user.role, 'is_active': user.is_active, 'email': user.email, 'permissions': sorted(list_user_permission_keys(db, user))}
    new_role = payload.role if payload.role is not None else user.role
    new_active = payload.is_active if payload.is_active is not None else user.is_active
    if user.id == actor.id and (not new_active or new_role != user.role):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Self lockout is not allowed')
    would_remove_admin = user.is_active and user.role == 'admin' and (not new_active or new_role != 'admin')
    if would_remove_admin and not _has_other_active_admin(db, user):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='At least one active admin must remain')
    if payload.email is not None:
        user.email = payload.email
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
    after = {'role': user.role, 'is_active': user.is_active, 'email': user.email, 'permissions': sorted(list_user_permission_keys(db, user))}
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
