"""aero work 지식폴더 사용자 소유권 추가."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '20260720_0034'
down_revision = '20260720_0033'
branch_labels = None
depends_on = None



def upgrade() -> None:
    with op.batch_alter_table('aero_work_knowledge_folders') as batch_op:
        batch_op.add_column(sa.Column('owner_id', sa.Integer(), nullable=True))
        batch_op.drop_constraint('uq_aero_work_knowledge_folders_path', type_='unique')
        batch_op.create_unique_constraint('uq_aero_work_folder_owner_path', ['owner_id', 'path'])
    op.execute(
        """
        UPDATE aero_work_knowledge_folders
        SET owner_id = (SELECT MIN(id) FROM users WHERE role = 'admin')
        """
    )



def downgrade() -> None:
    with op.batch_alter_table('aero_work_knowledge_folders') as batch_op:
        batch_op.drop_constraint('uq_aero_work_folder_owner_path', type_='unique')
        batch_op.drop_column('owner_id')
        batch_op.create_unique_constraint('uq_aero_work_knowledge_folders_path', ['path'])
