"""aero work knowledge fts: 청크 키워드 검색용 SQLite FTS5 가상 테이블 신설(G004)

``aero_work_knowledge_chunks`` 본문을 trigram 토크나이저로 색인해 한국어를 포함한
부분일치(substring) 검색을 가능케 한다. 폐쇄망이라 신규 의존 없이 sqlite3 내장 FTS5만
쓰며, 빌드에 trigram 토크나이저가 없으면 unicode61 로 폴백하고, FTS5 자체가 없으면
가상 테이블 생성을 스킵한다(``KnowledgeService`` 가 런타임에 테이블 존재 여부로 감지해
기존 LIKE 폴백 경로를 그대로 쓴다 — 다운그레이드는 항상 안전한 ``DROP TABLE IF EXISTS``).

``aero_work_knowledge_folders.status_detail`` 컬럼은 0020 에서 이미 추가돼 있어(진행률
문자열을 담는 용도로 처음부터 있었다) 여기서 다시 만들지 않는다.
"""

from __future__ import annotations

from alembic import op

revision = "20260719_0031"
down_revision = "20260719_0030"
branch_labels = None
depends_on = None

FTS_TABLE = 'aero_work_chunk_fts'
_TOKENIZERS = ('trigram', 'unicode61')  # 우선순위: trigram(부분일치) → unicode61(폴백)


def _pick_tokenizer(conn) -> str | None:
    """이 sqlite3 빌드가 실제로 지원하는 FTS5 토크나이저를 감지한다(둘 다 없으면 None)."""

    for tokenizer in _TOKENIZERS:
        probe = f'{FTS_TABLE}_probe_{tokenizer}'
        try:
            conn.exec_driver_sql(
                f"CREATE VIRTUAL TABLE {probe} USING fts5(content, tokenize='{tokenizer}')"
            )
        except Exception:  # noqa: BLE001 — sqlite3 빌드마다 예외 종류가 다를 수 있어 폭넓게 흡수
            continue
        else:
            conn.exec_driver_sql(f'DROP TABLE {probe}')
            return tokenizer
    return None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != 'sqlite':
        return  # FTS5 는 sqlite 전용 — 다른 DB 는 스킵하고 LIKE 폴백만 사용
    tokenizer = _pick_tokenizer(bind)
    if tokenizer is None:
        return  # FTS5 자체 미지원 → 가상 테이블 생성 스킵(런타임 LIKE 폴백)
    op.execute(
        f"CREATE VIRTUAL TABLE {FTS_TABLE} USING fts5(content, rel_path, tokenize='{tokenizer}')"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != 'sqlite':
        return
    op.execute(f'DROP TABLE IF EXISTS {FTS_TABLE}')
