"""aero work knowledge: 지식폴더/파일/청크 3층 색인 테이블 신설

Aero Work P2 '내 지식폴더' — 지정 폴더를 복사 없이 in-place 색인하고 Ollama 임베딩으로
벡터 검색하기 위한 영속 테이블. 임베딩은 청크당 JSON float 리스트(Text)로 저장해 SQLite
단일 파일 정책과 정합한다. 파일 시그니처(mtime+size)로 증분 동기화한다.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260719_0020"
down_revision = "20260718_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'aero_work_knowledge_folders',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('path', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('status_detail', sa.Text(), nullable=False, server_default=''),
        sa.Column('file_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('chunk_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_indexed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('path', name='uq_aero_work_knowledge_folders_path'),
    )
    op.create_table(
        'aero_work_knowledge_files',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'folder_id',
            sa.Integer(),
            sa.ForeignKey('aero_work_knowledge_folders.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('rel_path', sa.Text(), nullable=False),
        sa.Column('signature', sa.String(length=80), nullable=False),
        sa.Column('chunk_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('indexed_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        'ix_aero_work_knowledge_files_folder_id', 'aero_work_knowledge_files', ['folder_id']
    )
    op.create_table(
        'aero_work_knowledge_chunks',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'file_id',
            sa.Integer(),
            sa.ForeignKey('aero_work_knowledge_files.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('chunk_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', sa.Text(), nullable=False),
    )
    op.create_index(
        'ix_aero_work_knowledge_chunks_file_id', 'aero_work_knowledge_chunks', ['file_id']
    )


def downgrade() -> None:
    op.drop_index('ix_aero_work_knowledge_chunks_file_id', table_name='aero_work_knowledge_chunks')
    op.drop_table('aero_work_knowledge_chunks')
    op.drop_index('ix_aero_work_knowledge_files_folder_id', table_name='aero_work_knowledge_files')
    op.drop_table('aero_work_knowledge_files')
    op.drop_table('aero_work_knowledge_folders')
