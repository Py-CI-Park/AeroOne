"""ai provider config, operation journal, module launcher kind"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260714_0011"
down_revision = "20260712_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('service_modules', sa.Column('launcher_kind', sa.String(length=20), nullable=False, server_default='none'))
    with op.batch_alter_table('service_modules') as batch_op:
        batch_op.create_check_constraint(
            'ck_service_modules_launcher_kind',
            "launcher_kind IN ('none', 'open_notebook', 'open_webui')",
        )

    ai_provider_config = op.create_table(
        'ai_provider_config',
        sa.Column('singleton_id', sa.Integer(), nullable=False),
        sa.Column('selected_kind', sa.String(length=20), nullable=False, server_default='ollama'),
        sa.Column('compatible_state', sa.String(length=20), nullable=False, server_default='absent'),
        sa.Column('compatible_canonical_url', sa.String(length=500), nullable=True),
        sa.Column('compatible_display_url', sa.String(length=500), nullable=True),
        sa.Column('compatible_model', sa.String(length=160), nullable=True),
        sa.Column('compatible_generation', sa.String(length=60), nullable=True),
        sa.Column('compatible_credential_ref', sa.String(length=64), nullable=True),
        sa.Column('compatible_credential_binding_version', sa.Integer(), nullable=True),
        sa.Column('compatible_test_proof_ref', sa.String(length=64), nullable=True),
        sa.Column('compatible_test_proof_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('compatible_test_proof_canonical_url', sa.String(length=500), nullable=True),
        sa.Column('compatible_test_proof_model', sa.String(length=160), nullable=True),
        sa.Column('compatible_test_proof_generation', sa.String(length=60), nullable=True),
        sa.Column('config_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint('singleton_id = 1', name='ck_ai_provider_config_singleton'),
        sa.CheckConstraint("selected_kind IN ('ollama', 'openai_compatible')", name='ck_ai_provider_config_selected_kind'),
        sa.CheckConstraint(
            "compatible_state IN ('absent', 'unverified', 'verified')",
            name='ck_ai_provider_config_compatible_state',
        ),
        sa.CheckConstraint(
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
        sa.CheckConstraint(
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
        sa.PrimaryKeyConstraint('singleton_id'),
    )
    op.bulk_insert(
        ai_provider_config,
        [{'singleton_id': 1, 'selected_kind': 'ollama', 'compatible_state': 'absent', 'config_version': 1}],
    )

    op.create_table(
        'ai_provider_operation_journal',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('operation', sa.String(length=20), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('result', sa.String(length=20), nullable=False),
        sa.Column('reason_code', sa.String(length=80), nullable=True),
        sa.Column('actor_user_id', sa.Integer(), nullable=True),
        sa.Column('config_version_before', sa.Integer(), nullable=True),
        sa.Column('config_version_after', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "operation IN ('select', 'test', 'rotate', 'delete', 'reconcile')",
            name='ck_ai_provider_operation_journal_operation',
        ),
        sa.CheckConstraint("kind IN ('ollama', 'openai_compatible')", name='ck_ai_provider_operation_journal_kind'),
        sa.CheckConstraint("result IN ('success', 'failure')", name='ck_ai_provider_operation_journal_result'),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )

    bind = op.get_bind()
    # Idempotent repair: existing 'open-notebook' module gets the launcher tag without
    # otherwise touching its visibility/status (port 8502, unchanged behavior).
    bind.execute(
        sa.text(
            "UPDATE service_modules SET launcher_kind = 'open_notebook' "
            "WHERE key = 'open-notebook' AND launcher_kind != 'open_notebook'"
        )
    )

    # Create-or-repair 'open-webui': public visibility, exact global permission gate,
    # no resource_type/resource_id, no real href (launch is out-of-band, browser host port 8080).
    existing_open_webui = bind.execute(sa.text("SELECT id FROM service_modules WHERE key = 'open-webui'")).first()
    if existing_open_webui is None:
        bind.execute(
            sa.text(
                "INSERT INTO service_modules "
                "(key, title, description, href, section, status, badge, sort_order, is_enabled, is_external, "
                "visibility, launcher_kind, required_permission, resource_type, resource_id) "
                "VALUES "
                "('open-webui', 'Open WebUI', "
                "'Same-origin AI chat console launcher (browser host port 8080).', "
                "'#', 'Development', 'active', 'Active', 75, 1, 1, "
                "'public', 'open_webui', 'dashboard.openwebui.launch', NULL, NULL)"
            )
        )
    else:
        bind.execute(
            sa.text(
                "UPDATE service_modules SET "
                "visibility = 'public', launcher_kind = 'open_webui', "
                "required_permission = 'dashboard.openwebui.launch', "
                "resource_type = NULL, resource_id = NULL, href = '#', is_external = 1 "
                "WHERE key = 'open-webui'"
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    # DB metadata only: the row this migration created/repaired is removed; external
    # credentials (DPAPI-protected material referenced elsewhere) are never touched here.
    bind.execute(sa.text("DELETE FROM service_modules WHERE key = 'open-webui'"))
    op.drop_table('ai_provider_operation_journal')
    op.drop_table('ai_provider_config')
    with op.batch_alter_table('service_modules') as batch_op:
        batch_op.drop_constraint('ck_service_modules_launcher_kind', type_='check')
        batch_op.drop_column('launcher_kind')
