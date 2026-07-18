from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from app.modules.admin.permissions import ADMIN_PERMISSIONS, RESOURCE_SAFE_PERMISSIONS, is_resource_safe_permission, is_valid_resource_id


class PermissionResponse(BaseModel):
    key: str


class UserAdminResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str | None = None
    display_name: str | None = None
    role: str
    is_active: bool
    session_version: int = 0
    permissions: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    last_login_at: datetime | None = None


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256)
    email: str | None = None
    display_name: str | None = None
    role: Literal['admin', 'user', 'pending'] = 'user'
    is_active: bool = True


class UserUpdateRequest(BaseModel):
    email: str | None = None
    display_name: str | None = None
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


class ResourceGrantCreateRequest(BaseModel):
    subject_type: Literal['user', 'group']
    subject_id: int
    resource_type: str
    resource_id: str
    permission_key: str
    def resource_policy_error(self) -> str | None:
        if self.resource_type not in RESOURCE_SAFE_PERMISSIONS:
            return 'Invalid resource grant resource_type'
        if not is_valid_resource_id(self.resource_id):
            return 'Invalid resource grant resource_id'
        if self.permission_key in ADMIN_PERMISSIONS and not is_resource_safe_permission(self.resource_type, self.permission_key):
            return 'Invalid resource grant permission_key'
        if not is_resource_safe_permission(self.resource_type, self.permission_key):
            return 'Invalid resource grant permission_key'
        return None


class ResourceGrantResponse(ResourceGrantCreateRequest):
    id: int
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class RbacGroupPermissionSource(BaseModel):
    group: str
    key: str


class RbacEffectivePermissionSource(BaseModel):
    key: str
    sources: list[str]


class RbacResourceGrantSource(BaseModel):
    resource_type: str
    resource_id: str
    permission_key: str
    source: str


class RbacMatrixUserResponse(BaseModel):
    user_id: int
    username: str
    role: str
    role_permissions: list[str]
    direct_permissions: list[str]
    group_permissions: list[RbacGroupPermissionSource]
    effective_permissions: list[RbacEffectivePermissionSource]
    resource_grants: list[RbacResourceGrantSource]


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
    launcher_kind: str = 'none'
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
    launcher_kind: Literal['none', 'open_notebook', 'open_webui'] | None = None
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
    launcher_kind: Literal['none', 'open_notebook', 'open_webui'] = 'none'
    required_permission: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None


class ConnectedSessionResponse(BaseModel):
    user_id: int
    username: str
    last_seen_at: datetime


class LoginEventResponse(BaseModel):
    id: int
    user_id: int | None = None
    username: str
    ip_address: str | None = None
    user_agent: str | None = None
    status: Literal['success', 'failure', 'logout']
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConnectedUsersResponse(BaseModel):
    active_sessions: list[ConnectedSessionResponse]
    active_session_count: int
    active_user_count: int
    active_count: int
    recent_login_events: list[LoginEventResponse]
    login_failure_count: int
    read_tracking_summary: dict[str, int]


class SessionPurgeResponse(BaseModel):
    login_events_deleted: int
    session_activity_deleted: int


class AdminOverviewWindowCount(BaseModel):
    current: int
    prior: int
    delta: int


class AdminOverviewUsers(BaseModel):
    total: int
    active: int
    inactive: int
    roles: dict[str, int]
    created: AdminOverviewWindowCount


class AdminOverviewLogins(BaseModel):
    success: AdminOverviewWindowCount
    failure: AdminOverviewWindowCount
    logout: AdminOverviewWindowCount


class AdminOverviewAi(BaseModel):
    total: AdminOverviewWindowCount
    failure: AdminOverviewWindowCount


class AdminOverviewSessions(BaseModel):
    active_session_count: int
    active_user_count: int
    active_count: int


class AdminOverviewModuleRef(BaseModel):
    key: str
    label: str


class AdminOverviewModuleBuckets(BaseModel):
    unavailable: list[AdminOverviewModuleRef]
    coming: list[AdminOverviewModuleRef]
    development: list[AdminOverviewModuleRef]
    active: list[AdminOverviewModuleRef]


class AdminOverviewModules(BaseModel):
    total: int
    buckets: AdminOverviewModuleBuckets


class AdminOverviewSystem(BaseModel):
    app_version: str
    app_env: str
    database_kind: str
    newsletter_count: int
    asset_health: dict[str, int]
    read_summary: dict[str, int]


class AdminOverviewAuditEvent(BaseModel):
    id: int
    action: str
    target_type: str | None = None
    status: str
    created_at: datetime


class AdminOverviewResponse(BaseModel):
    generated_at: datetime
    anchor: datetime
    users: AdminOverviewUsers
    logins: AdminOverviewLogins
    ai: AdminOverviewAi
    sessions: AdminOverviewSessions
    modules: AdminOverviewModules
    system: AdminOverviewSystem
    recent_audit: list[AdminOverviewAuditEvent]


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


AiProviderKind = Literal['ollama', 'openai_compatible']
AiProviderCompatibleState = Literal['absent', 'unverified', 'verified']
AiProviderOperation = Literal['select', 'test', 'rotate', 'delete', 'reconcile']


class AiProviderConfigResponse(BaseModel):
    """Safe-result read model for the singleton AI provider configuration.

    Never includes the compatible credential ref, its binding version, or any
    ciphertext/raw upstream detail — those stay server-internal.
    """

    selected_kind: AiProviderKind
    compatible_state: AiProviderCompatibleState
    compatible_display_url: str | None = None
    compatible_model: str | None = None
    compatible_generation: str | None = None
    compatible_test_proof_at: datetime | None = None
    compatible_test_proof_model: str | None = None
    config_version: int
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AiProviderCompatibleWriteRequest(BaseModel):
    """Frozen, write-only submission of OpenAI-compatible connection + credential material.

    `api_key` is never echoed back by any response schema and is excluded from repr to
    avoid accidental logging. `expected_config_version` is carried in the body (never a
    query parameter) so optimistic-concurrency checks apply to the same CSRF-protected,
    schema-validated payload.
    """

    model_config = ConfigDict(frozen=True)

    canonical_url: str = Field(min_length=1, max_length=500)
    display_url: str = Field(min_length=1, max_length=500)
    model: str = Field(min_length=1, max_length=160)
    generation: str = Field(min_length=1, max_length=60)
    # repr 배제는 Field(repr=False) 대신 __repr_args__ 재정의로 보장한다 — FastAPI 가
    # body 필드마다 TypeAdapter(Annotated[type, field_info]) 를 만들 때 repr 이 비지원
    # 문맥이 되어 pydantic 2.12 UnsupportedFieldAttributeWarning 이 났다.
    api_key: str = Field(min_length=1)
    expected_config_version: int

    def __repr_args__(self):  # noqa: ANN204 - pydantic 시그니처 준수
        # api_key 는 어떤 repr/str 출력에도 노출하지 않는다(우발 로깅 방지).
        # [주의] 이 배제는 repr/str 한정이다 — api_key 자체가 422 검증 실패하면 FastAPI
        # 기본 RequestValidationError 가 제출값을 input 으로 클라이언트에 되돌린다(제출한
        # 관리자 본인에게만). 검증 오류 로깅 핸들러를 도입한다면 이 라우트의 input 마스킹 필수.
        return [(key, value) for key, value in super().__repr_args__() if key != 'api_key']


class AiProviderCompatibleTestRequest(BaseModel):
    """Probe the exact persisted compatible candidate.

    The API key is loaded only from the DPAPI credential store. It is deliberately
    absent from this request so a connection check never retransmits or re-persists
    secret material.
    """

    model_config = ConfigDict(frozen=True)

    canonical_url: str = Field(min_length=1, max_length=500)
    model: str = Field(min_length=1, max_length=160)
    generation: str = Field(min_length=1, max_length=60)


class AiProviderTestResultResponse(BaseModel):
    """Safe-result of a candidate test: outcome + the exact binding it was proven against.

    Never includes the candidate api_key or any raw upstream request/response body.
    """

    success: bool
    reason_code: str | None = None
    tested_at: datetime
    canonical_url: str
    model: str
    generation: str


class AiProviderSelectionRequest(BaseModel):
    selected_kind: AiProviderKind
    expected_config_version: int


class AiProviderCompatibleRotateRequest(AiProviderCompatibleWriteRequest):
    """Frozen, write-only rotation of the compatible credential; optimistic-locked via
    the inherited body-carried `expected_config_version`."""


class AiProviderCompatibleDeleteRequest(BaseModel):
    expected_config_version: int


class AiProviderActivateRequest(BaseModel):
    """Body-carried optimistic version for activation; never a query parameter."""

    expected_config_version: int


class AiProviderReconcileResponse(BaseModel):
    reconciled: bool
    compatible_state: AiProviderCompatibleState
    config_version: int


class AiProviderOperationJournalResponse(BaseModel):
    id: int
    operation: AiProviderOperation
    kind: AiProviderKind
    result: Literal['success', 'failure']
    reason_code: str | None = None
    actor_user_id: int | None = None
    config_version_before: int | None = None
    config_version_after: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
