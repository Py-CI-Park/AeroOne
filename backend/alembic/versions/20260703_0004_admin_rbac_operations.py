"""admin rbac audit and operations console"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260703_0004"
down_revision = "20260613_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('session_version', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('created_by_user_id', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('password_changed_at', sa.DateTime(timezone=True), nullable=True))

    op.add_column('categories', sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('categories', sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('tags', sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('tags', sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()))

    op.add_column('newsletters', sa.Column('status', sa.String(length=30), nullable=False, server_default='published'))
    op.add_column('newsletters', sa.Column('status_changed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('newsletters', sa.Column('status_changed_by_user_id', sa.Integer(), nullable=True))
    bind = op.get_bind()
    bind.execute(sa.text("UPDATE newsletters SET status = CASE WHEN is_active = 1 THEN 'published' ELSE 'archived' END"))

    op.create_table(
        'groups',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('key', sa.String(length=80), nullable=False, unique=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        'user_groups',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('group_id', sa.Integer(), sa.ForeignKey('groups.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        'user_permissions',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('permission_key', sa.String(length=120), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        'group_permissions',
        sa.Column('group_id', sa.Integer(), sa.ForeignKey('groups.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('permission_key', sa.String(length=120), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        'resource_grants',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('subject_type', sa.String(length=20), nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=False),
        sa.Column('resource_id', sa.String(length=255), nullable=False),
        sa.Column('permission_key', sa.String(length=120), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('subject_type', 'subject_id', 'resource_type', 'resource_id', 'permission_key', name='uq_resource_grant'),
    )
    op.create_table(
        'admin_audit_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('actor_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('actor_username', sa.String(length=100), nullable=True),
        sa.Column('actor_role', sa.String(length=50), nullable=True),
        sa.Column('action', sa.String(length=120), nullable=False),
        sa.Column('target_type', sa.String(length=80), nullable=False),
        sa.Column('target_id', sa.String(length=120), nullable=True),
        sa.Column('method', sa.String(length=12), nullable=True),
        sa.Column('path', sa.String(length=500), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='success'),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('request_id', sa.String(length=100), nullable=True),
        sa.Column('before_json', sa.Text(), nullable=True),
        sa.Column('after_json', sa.Text(), nullable=True),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_admin_audit_events_action', 'admin_audit_events', ['action'])

    service_modules = op.create_table(
        'service_modules',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('key', sa.String(length=80), nullable=False, unique=True),
        sa.Column('title', sa.String(length=160), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('href', sa.String(length=500), nullable=False, server_default='#'),
        sa.Column('section', sa.String(length=80), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='active'),
        sa.Column('badge', sa.String(length=60), nullable=False, server_default='Active'),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('is_external', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.bulk_insert(
        service_modules,
        [
            {'key': 'newsletter', 'title': 'Newsletter', 'description': None, 'href': '/newsletters', 'section': 'Newsletter', 'status': 'active', 'badge': 'Active', 'sort_order': 10, 'is_enabled': True, 'is_external': False},
            {'key': 'civil-aircraft', 'title': 'Civil Aircraft Spec Catalog', 'description': 'Commercial aircraft specs & market competition analysis.', 'href': '/reports/civil-aircraft', 'section': 'Document', 'status': 'active', 'badge': 'Active', 'sort_order': 20, 'is_enabled': True, 'is_external': False},
            {'key': 'document', 'title': 'Document', 'description': 'Browse HTML documents organized in folders.', 'href': '/documents', 'section': 'Document', 'status': 'active', 'badge': 'Active', 'sort_order': 30, 'is_enabled': True, 'is_external': False},
            {'key': 'nsa', 'title': 'NSA', 'description': 'Password-protected HTML documents.', 'href': '/nsa', 'section': 'Document', 'status': 'active', 'badge': 'Active', 'sort_order': 40, 'is_enabled': True, 'is_external': False},
            {'key': 'viewer', 'title': 'Viewer', 'description': '로컬 Markdown·HTML 파일을 열어 보고 편집 (서버 sanitize 미리보기).', 'href': '/viewer', 'section': '개발중', 'status': 'development', 'badge': 'Active', 'sort_order': 50, 'is_enabled': True, 'is_external': False},
            {'key': 'ai', 'title': 'AeroAI', 'description': '사내 폐쇄망 문서를 근거로 답하는 AI 어시스턴트.', 'href': '/ai', 'section': '개발중', 'status': 'development', 'badge': 'Active', 'sort_order': 60, 'is_enabled': True, 'is_external': False},
            {'key': 'open-notebook', 'title': 'Notebook', 'description': 'NotebookLM 대안 — 소스 정리·요약·벡터 검색 (별도 폐쇄망 앱).', 'href': '', 'section': '개발중', 'status': 'development', 'badge': 'Active', 'sort_order': 70, 'is_enabled': True, 'is_external': True},
            {'key': 'ladder', 'title': 'Ladder', 'description': 'Coffee-bet ladder game (사다리타기).', 'href': '/games/ladder', 'section': '개발중', 'status': 'development', 'badge': 'Active', 'sort_order': 80, 'is_enabled': True, 'is_external': False},
            {'key': 'announcement', 'title': 'Announcement', 'description': 'Company-wide announcements module.', 'href': '#', 'section': '개발중', 'status': 'coming_soon', 'badge': 'Coming soon', 'sort_order': 90, 'is_enabled': False, 'is_external': False},
            {'key': 'schedule', 'title': 'Schedule', 'description': 'Shared calendar & event tracking.', 'href': '#', 'section': '개발중', 'status': 'coming_soon', 'badge': 'Coming soon', 'sort_order': 100, 'is_enabled': False, 'is_external': False},
        ],
    )

    op.create_table(
        'backup_records',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('filename', sa.String(length=255), nullable=False, unique=True),
        sa.Column('file_path', sa.String(length=1000), nullable=False),
        sa.Column('sha256', sa.String(length=128), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('manifest_json', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='created'),
        sa.Column('created_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        'ai_request_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('request_id', sa.String(length=64), nullable=False, unique=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('session_hash', sa.String(length=64), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('model', sa.String(length=160), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('error_code', sa.String(length=80), nullable=True),
        sa.Column('conversation_id', sa.Integer(), nullable=True),
        sa.Column('citation_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('collection_scope', sa.String(length=120), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        'ai_message_feedback',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('conversation_id', sa.Integer(), nullable=True),
        sa.Column('message_id', sa.Integer(), nullable=True),
        sa.Column('rating', sa.String(length=20), nullable=False),
        sa.Column('reason', sa.String(length=500), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('ai_message_feedback')
    op.drop_table('ai_request_logs')
    op.drop_table('backup_records')
    op.drop_table('service_modules')
    op.drop_index('ix_admin_audit_events_action', table_name='admin_audit_events')
    op.drop_table('admin_audit_events')
    op.drop_table('resource_grants')
    op.drop_table('group_permissions')
    op.drop_table('user_permissions')
    op.drop_table('user_groups')
    op.drop_table('groups')
    op.drop_column('newsletters', 'status_changed_by_user_id')
    op.drop_column('newsletters', 'status_changed_at')
    op.drop_column('newsletters', 'status')
    op.drop_column('tags', 'is_active')
    op.drop_column('tags', 'sort_order')
    op.drop_column('categories', 'is_active')
    op.drop_column('categories', 'sort_order')
    op.drop_column('users', 'password_changed_at')
    op.drop_column('users', 'created_by_user_id')
    op.drop_column('users', 'session_version')
