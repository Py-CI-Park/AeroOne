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
    op.execute(
        """
        UPDATE aero_work_knowledge_folders
        SET owner_id = (SELECT MIN(id) FROM users WHERE role = 'admin')
        """
    )
    op.execute(
        """
        DELETE FROM aero_work_task_category_files
        WHERE EXISTS (
            SELECT 1
            FROM aero_work_task_categories AS category
            JOIN aero_work_knowledge_files AS file ON file.id = aero_work_task_category_files.file_id
            JOIN aero_work_knowledge_folders AS folder ON folder.id = file.folder_id
            WHERE category.id = aero_work_task_category_files.category_id
              AND (folder.owner_id IS NULL OR folder.owner_id != category.user_id)
        )
        """
    )



def downgrade() -> None:
    with op.batch_alter_table('aero_work_knowledge_folders') as batch_op:
        batch_op.drop_column('owner_id')
