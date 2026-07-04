from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PermissionResponse(BaseModel):
    key: str


class UserAdminResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str | None = None
    role: str
    is_active: bool
    session_version: int = 0
    permissions: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    last_login_at: datetime | None = None


class UserCreateRequest(BaseModel):
    username: str
    password: str
    email: str | None = None
    role: Literal['admin', 'user', 'pending'] = 'user'
    is_active: bool = True


class UserUpdateRequest(BaseModel):
    email: str | None = None
    role: Literal['admin', 'user', 'pending'] | None = None
    is_active: bool | None = None
    permissions: list[str] | None = None


class PasswordResetRequest(BaseModel):
    temporary_password: str


class GroupResponse(BaseModel):
    id: int
    key: str
    name: str
    description: str | None = None
    is_active: bool
    permissions: list[str] = Field(default_factory=list)


class GroupUpsertRequest(BaseModel):
    key: str
    name: str
    description: str | None = None
    is_active: bool = True
    permissions: list[str] = Field(default_factory=list)


class AuditEventResponse(BaseModel):
    id: int
    actor_user_id: int | None = None
    actor_username: str | None = None
    actor_role: str | None = None
    action: str
    target_type: str
    target_id: str | None = None
    method: str | None = None
    path: str | None = None
    status: str
    ip_address: str | None = None
    user_agent: str | None = None
    request_id: str | None = None
    before_json: str | None = None
    after_json: str | None = None
    metadata_json: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ServiceModuleResponse(BaseModel):
    id: int
    key: str
    title: str
    description: str | None = None
    href: str
    section: str
    status: str
    badge: str
    sort_order: int
    is_enabled: bool
    is_external: bool
    visibility: str = 'public'
    required_permission: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ServiceModuleUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    href: str | None = None
    section: str | None = None
    status: Literal['active', 'development', 'coming_soon', 'hidden'] | None = None
    badge: str | None = None
    sort_order: int | None = None
    is_enabled: bool | None = None
    is_external: bool | None = None
    visibility: Literal['public', 'admin'] | None = None
    required_permission: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None


class ServiceModuleCreateRequest(BaseModel):
    key: str
    title: str
    description: str | None = None
    href: str = '#'
    section: str = 'Development'
    status: Literal['active', 'development', 'coming_soon', 'hidden'] = 'development'
    badge: str = 'Active'
    sort_order: int = 0
    is_enabled: bool = True
    is_external: bool = False
    visibility: Literal['public', 'admin'] = 'admin'
    required_permission: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None


class AdminSummaryResponse(BaseModel):
    app_version: str
    app_env: str
    database_url: str
    db_ok: bool
    newsletter_total: int
    latest_newsletter_title: str | None = None
    active_modules: int
    coming_soon_modules: int
    asset_health: dict[str, int]
    read_summary: dict[str, int]
    ai_status: dict[str, Any]
    recent_audit_events: list[AuditEventResponse]


class AssetHealthItem(BaseModel):
    newsletter_id: int
    newsletter_title: str
    asset_type: str
    file_path: str
    exists: bool
    file_size: int | None = None
    checksum: str | None = None
    expected_checksum: str | None = None
    ok: bool
    status: Literal['ok', 'missing', 'checksum_mismatch', 'misconfig'] = 'ok'
    resolved_root: str | None = None
    resolved_path: str | None = None
    root_kind: str
    remediation: str
    error_code: str | None = None


class AssetHealthResponse(BaseModel):
    ok: int
    missing: int
    checksum_mismatch: int
    misconfig: int = 0
    items: list[AssetHealthItem]

class ConfigHealthItem(BaseModel):
    kind: str
    resolved_path: str
    exists: bool
    readable: bool


class ConfigHealthResponse(BaseModel):
    roots: list[ConfigHealthItem]


class BackupRecordResponse(BaseModel):
    id: int
    filename: str
    sha256: str
    file_size: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BackupCreateResponse(BackupRecordResponse):
    manifest: dict[str, Any]


class BackupValidationResponse(BaseModel):
    filename: str
    valid: bool
    issues: list[str] = Field(default_factory=list)
    manifest: dict[str, Any] | None = None



class BackupRestoreDryRunResponse(BaseModel):
    filename: str
    valid: bool
    compatible: bool
    issues: list[str] = Field(default_factory=list)
    would_restore: list[str] = Field(default_factory=list)
    manifest: dict[str, Any] | None = None

class UnifiedSearchResult(BaseModel):
    source: str
    title: str
    snippet: str
    url: str
    score: float = 1.0


class UnifiedSearchResponse(BaseModel):
    query: str
    results: list[UnifiedSearchResult]
    degraded: bool = False
    reason: str | None = None


class BulkNewsletterRequest(BaseModel):
    ids: list[int]
    action: Literal['publish', 'archive', 'draft']


class BulkNewsletterResponse(BaseModel):
    updated: int
