from __future__ import annotations

import sqlalchemy as sa

from app.db.base import Base
from app.modules.ai import models as ai_models  # noqa: F401


AI_TABLES = {'ai_conversations', 'ai_messages', 'ai_message_citations'}


def _migration_module():
    import importlib.util
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[2]
        / 'alembic'
        / 'versions'
        / '20260613_0003_ai_conversations.py'
    )
    spec = importlib.util.spec_from_file_location('mig_0003', path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_chain_is_pinned_to_read_events():
    module = _migration_module()
    assert module.revision == '20260613_0003'
    assert module.down_revision == '20260603_0002'


def test_models_register_three_tables_on_metadata():
    for table in AI_TABLES:
        assert table in Base.metadata.tables


def test_owner_ip_is_nullable_metadata_column_and_session_indexed():
    conv = Base.metadata.tables['ai_conversations']
    assert conv.c.owner_ip.nullable is True
    assert conv.c.owner_session_id.nullable is False
    indexed = {col.name for index in conv.indexes for col in index.columns}
    assert 'owner_session_id' in indexed
    assert 'owner_ip' in indexed


def test_message_and_citation_cascade_on_delete():
    messages = Base.metadata.tables['ai_messages']
    citations = Base.metadata.tables['ai_message_citations']
    conv_fk = next(iter(messages.c.conversation_id.foreign_keys))
    msg_fk = next(iter(citations.c.message_id.foreign_keys))
    assert conv_fk.ondelete == 'CASCADE'
    assert msg_fk.ondelete == 'CASCADE'


def test_create_all_then_cascade_delete_removes_children():
    engine = sa.create_engine('sqlite://')
    # SQLite 는 기본적으로 FK 를 강제하지 않으므로 명시적으로 켠다.
    sa.event.listen(
        engine,
        'connect',
        lambda dbapi_conn, _rec: dbapi_conn.execute('PRAGMA foreign_keys=ON'),
    )
    Base.metadata.create_all(bind=engine, tables=[Base.metadata.tables[name] for name in AI_TABLES])
    with engine.begin() as conn:
        conv_id = conn.execute(
            sa.text(
                'INSERT INTO ai_conversations (owner_session_id, title) VALUES (:s, :t)'
            ),
            {'s': 'sess-1', 't': '첫 대화'},
        ).lastrowid
        msg_id = conn.execute(
            sa.text(
                'INSERT INTO ai_messages (conversation_id, role, content, seq) '
                'VALUES (:c, :r, :ct, :q)'
            ),
            {'c': conv_id, 'r': 'user', 'ct': '항공기 질문', 'q': 0},
        ).lastrowid
        conn.execute(
            sa.text(
                'INSERT INTO ai_message_citations (message_id, collection, path) '
                'VALUES (:m, :col, :p)'
            ),
            {'m': msg_id, 'col': 'document', 'p': 'a/b.html'},
        )
    with engine.begin() as conn:
        conn.execute(sa.text('DELETE FROM ai_conversations WHERE id = :i'), {'i': conv_id})
    with engine.connect() as conn:
        assert conn.execute(sa.text('SELECT COUNT(*) FROM ai_messages')).scalar() == 0
        assert conn.execute(sa.text('SELECT COUNT(*) FROM ai_message_citations')).scalar() == 0
