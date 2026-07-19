"""aero work task category file index: 파일 id 단독 인덱스 추가(G003 L2)

``aero_work_task_category_files`` 는 복합 PK(category_id, file_id)만 있어, "이 파일이 어느
분류에 속하는가"(file_id 단독 조회 — 예: 파일 삭제 전 영향 분류 확인, 지식위키의 파일별 역참조)
질의가 복합 PK 인덱스의 선두 컬럼이 아닌 file_id 로 들어와 풀스캔이 난다. file_id 단독 인덱스를
추가해 이 방향 조회를 인덱스 스캔으로 바꾼다(가역 — downgrade 로 인덱스만 제거).
"""

from __future__ import annotations

from alembic import op

revision = "20260719_0030"
down_revision = "20260719_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        'ix_aero_work_task_category_files_file_id',
        'aero_work_task_category_files',
        ['file_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_aero_work_task_category_files_file_id', table_name='aero_work_task_category_files')
