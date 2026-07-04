"""connected user session and login metadata"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260704_0007"
down_revision = "20260704_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'login_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_login_events_created_at', 'login_events', ['created_at'])
    op.create_index('ix_login_events_status', 'login_events', ['status'])
    op.create_index('ix_login_events_user_id', 'login_events', ['user_id'])
    op.create_table(
        'user_session_activity',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('session_hash', sa.String(length=64), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('user_id', 'session_hash', name='uq_user_session_activity_user_hash'),
    )
    op.create_index('ix_user_session_activity_user_id', 'user_session_activity', ['user_id'])
    op.create_index('ix_user_session_activity_last_seen_at', 'user_session_activity', ['last_seen_at'])
    op.create_index('ix_user_session_activity_expires_at', 'user_session_activity', ['expires_at'])
    op.create_index('ix_user_session_activity_session_hash', 'user_session_activity', ['session_hash'])


def downgrade() -> None:
    op.drop_index('ix_user_session_activity_session_hash', table_name='user_session_activity')
    op.drop_index('ix_user_session_activity_expires_at', table_name='user_session_activity')
    op.drop_index('ix_user_session_activity_last_seen_at', table_name='user_session_activity')
    op.drop_index('ix_user_session_activity_user_id', table_name='user_session_activity')
    op.drop_table('user_session_activity')
    op.drop_index('ix_login_events_user_id', table_name='login_events')
    op.drop_index('ix_login_events_status', table_name='login_events')
    op.drop_index('ix_login_events_created_at', table_name='login_events')
    op.drop_table('login_events')
