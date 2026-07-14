from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, false, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Group(Base):
    __tablename__ = 'groups'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class UserGroup(Base):
    __tablename__ = 'user_groups'

    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey('groups.id', ondelete='CASCADE'), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class UserPermission(Base):
    __tablename__ = 'user_permissions'

    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    permission_key: Mapped[str] = mapped_column(String(120), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class GroupPermission(Base):
    __tablename__ = 'group_permissions'

    group_id: Mapped[int] = mapped_column(ForeignKey('groups.id', ondelete='CASCADE'), primary_key=True)
    permission_key: Mapped[str] = mapped_column(String(120), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ResourceGrant(Base):
    __tablename__ = 'resource_grants'
    __table_args__ = (UniqueConstraint('subject_type', 'subject_id', 'resource_type', 'resource_id', 'permission_key', name='uq_resource_grant'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_type: Mapped[str] = mapped_column(String(20), nullable=False)
    subject_id: Mapped[int] = mapped_column(Integer, nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(255), nullable=False)
    permission_key: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AdminAuditEvent(Base):
    __tablename__ = 'admin_audit_events'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    actor_username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    action: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    method: Mapped[str | None] = mapped_column(String(12), nullable=True)
    path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default='success')
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    before_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class LoginEvent(Base):
    __tablename__ = 'login_events'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), index=True, nullable=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False, server_default=func.now())


class UserSessionActivity(Base):
    __tablename__ = 'user_session_activity'
    __table_args__ = (
        UniqueConstraint('user_id', 'session_hash', name='uq_user_session_activity_user_hash'),
        Index('ix_user_session_activity_user_id', 'user_id'),
        Index('ix_user_session_activity_last_seen_at', 'last_seen_at'),
        Index('ix_user_session_activity_expires_at', 'expires_at'),
        Index('ix_user_session_activity_session_hash', 'session_hash'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    session_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ServiceModule(Base):
    __tablename__ = 'service_modules'
    __table_args__ = (
        CheckConstraint("launcher_kind IN ('none', 'open_notebook', 'open_webui')", name='ck_service_modules_launcher_kind'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    href: Mapped[str] = mapped_column(String(500), nullable=False, server_default='#')
    section: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default='active')
    badge: Mapped[str] = mapped_column(String(60), nullable=False, server_default='Active')
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default='0')
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
    is_external: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, server_default='public')
    launcher_kind: Mapped[str] = mapped_column(String(20), nullable=False, server_default='none')
    required_permission: Mapped[str | None] = mapped_column(String(120), nullable=True)
    resource_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class BackupRecord(Base):
    __tablename__ = 'backup_records'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    sha256: Mapped[str] = mapped_column(String(128), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, server_default='0')
    manifest_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default='created')
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AiRequestLog(Base):
    __tablename__ = 'ai_request_logs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    session_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    model: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    conversation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    citation_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default='0')
    collection_scope: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AiMessageFeedback(Base):
    __tablename__ = 'ai_message_feedback'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AiProviderConfig(Base):
    """Singleton AI provider selection + independent OpenAI-compatible provider state.

    Never stores API keys/ciphertext/raw upstream request-response detail. Compatible
    credential material is protected by DPAPI elsewhere and referenced here only via an
    opaque `compatible_credential_ref`; `compatible_credential_binding_version` records
    which immutable DPAPI purpose/binding scheme protected that ref and MUST NOT change
    for a given ref once written. `config_version` is an optimistic-concurrency counter
    bumped on every write. Activation of `selected_kind = 'openai_compatible'` is gated
    by a durable, exact-bound test proof: the persisted proof's canonical_url/model/
    generation must equal the currently configured compatible_* values.
    """

    __tablename__ = 'ai_provider_config'
    __table_args__ = (
        CheckConstraint('singleton_id = 1', name='ck_ai_provider_config_singleton'),
        CheckConstraint("selected_kind IN ('ollama', 'openai_compatible')", name='ck_ai_provider_config_selected_kind'),
        CheckConstraint("compatible_state IN ('absent', 'unverified', 'verified')", name='ck_ai_provider_config_compatible_state'),
        CheckConstraint(
            "(compatible_state = 'absent' "
            "AND compatible_canonical_url IS NULL AND compatible_display_url IS NULL "
            "AND compatible_model IS NULL AND compatible_generation IS NULL "
            "AND compatible_credential_ref IS NULL AND compatible_credential_binding_version IS NULL) "
            "OR "
            "(compatible_state != 'absent' "
            "AND compatible_canonical_url IS NOT NULL AND compatible_display_url IS NOT NULL "
            "AND compatible_model IS NOT NULL AND compatible_generation IS NOT NULL "
            "AND compatible_credential_ref IS NOT NULL AND compatible_credential_binding_version IS NOT NULL)",
            name='ck_ai_provider_config_compatible_coherence',
        ),
        CheckConstraint(
            "(compatible_state = 'verified' "
            "AND compatible_test_proof_ref IS NOT NULL AND compatible_test_proof_at IS NOT NULL "
            "AND compatible_test_proof_canonical_url IS NOT NULL AND compatible_test_proof_model IS NOT NULL "
            "AND compatible_test_proof_generation IS NOT NULL) "
            "OR "
            "(compatible_state != 'verified' "
            "AND compatible_test_proof_ref IS NULL AND compatible_test_proof_at IS NULL "
            "AND compatible_test_proof_canonical_url IS NULL AND compatible_test_proof_model IS NULL "
            "AND compatible_test_proof_generation IS NULL)",
            name='ck_ai_provider_config_test_proof_coherence',
        ),
    )

    singleton_id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    selected_kind: Mapped[str] = mapped_column(String(20), nullable=False, server_default='ollama')
    compatible_state: Mapped[str] = mapped_column(String(20), nullable=False, server_default='absent')
    compatible_canonical_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    compatible_display_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    compatible_model: Mapped[str | None] = mapped_column(String(160), nullable=True)
    compatible_generation: Mapped[str | None] = mapped_column(String(60), nullable=True)
    compatible_credential_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    compatible_credential_binding_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    compatible_test_proof_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    compatible_test_proof_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    compatible_test_proof_canonical_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    compatible_test_proof_model: Mapped[str | None] = mapped_column(String(160), nullable=True)
    compatible_test_proof_generation: Mapped[str | None] = mapped_column(String(60), nullable=True)
    config_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default='1')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class AiProviderOperationJournal(Base):
    """Metadata-only audit trail for AI provider operations.

    Records that a select/test/rotate/delete/reconcile operation happened and its safe
    result, never candidate material (no keys, no raw URLs beyond what is already
    canonical/public, no request/response bodies).
    """

    __tablename__ = 'ai_provider_operation_journal'
    __table_args__ = (
        CheckConstraint(
            "operation IN ('select', 'test', 'rotate', 'delete', 'reconcile')",
            name='ck_ai_provider_operation_journal_operation',
        ),
        CheckConstraint("kind IN ('ollama', 'openai_compatible')", name='ck_ai_provider_operation_journal_kind'),
        CheckConstraint("result IN ('success', 'failure')", name='ck_ai_provider_operation_journal_result'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    operation: Mapped[str] = mapped_column(String(20), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    result: Mapped[str] = mapped_column(String(20), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    config_version_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    config_version_after: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
