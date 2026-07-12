from __future__ import annotations

import sqlalchemy as sa
import pytest
from sqlalchemy.orm import Session

from app.db.base import Base
from app.modules.ai import models as ai_models  # noqa: F401  (register tables)
from app.modules.ai.repositories import AiConversationRepository


@pytest.fixture()
def session() -> Session:
    engine = sa.create_engine('sqlite://')
    sa.event.listen(
        engine,
        'connect',
        lambda dbapi_conn, _rec: dbapi_conn.execute('PRAGMA foreign_keys=ON'),
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Base.metadata.tables['ai_conversations'],
            Base.metadata.tables['ai_messages'],
            Base.metadata.tables['ai_message_citations'],
        ],
    )
    with Session(engine) as db:
        yield db


def test_list_is_scoped_to_session_not_owner_ip(session: Session) -> None:
    repo = AiConversationRepository(session)
    # 동일 owner_ip 를 공유하지만 세션이 다른 두 대화.
    repo.create_conversation('session-A', '10.0.0.5', 'A 대화')
    repo.create_conversation('session-B', '10.0.0.5', 'B 대화')
    session.commit()

    a = repo.list_conversations('session-A')
    b = repo.list_conversations('session-B')
    assert [c.title for c in a] == ['A 대화']
    assert [c.title for c in b] == ['B 대화']
    # owner_ip 가 같아도 교차 조회되지 않는다(스코프=세션 단독).
    assert all(c.owner_session_id == 'session-A' for c in a)


def test_get_and_mutations_reject_foreign_session(session: Session) -> None:
    repo = AiConversationRepository(session)
    conv = repo.create_conversation('owner', '10.0.0.5', '원 대화')
    session.commit()

    assert repo.get_conversation('intruder', conv.id) is None
    assert repo.update_conversation('intruder', conv.id, is_pinned=True) is None
    assert repo.delete_conversation('intruder', conv.id) is False
    # 본인 세션은 정상 동작.
    assert repo.get_conversation('owner', conv.id) is not None


def test_append_turn_orders_messages_and_bumps_updated_at(session: Session) -> None:
    repo = AiConversationRepository(session)
    conv = repo.create_conversation('owner', None, '대화')
    session.commit()
    original_updated = conv.updated_at

    repo.append_turn(
        conv,
        user_content='질문1',
        assistant_content='답변1',
        citations=[{'collection': 'document', 'path': 'a.html', 'name': 'a', 'folder': '', 'snippet': 's', 'navigation_url': '/documents?path=a'}],
    )
    repo.append_turn(conv, user_content='질문2', assistant_content='답변2', citations=[])
    session.commit()

    loaded = repo.get_conversation('owner', conv.id)
    assert [(m.role, m.seq) for m in loaded.messages] == [
        ('user', 0), ('assistant', 1), ('user', 2), ('assistant', 3)
    ]
    # 첫 응답에만 citation 1개.
    assistant_first = loaded.messages[1]
    assert len(assistant_first.citations) == 1
    assert assistant_first.citations[0].collection == 'document'
    assert loaded.updated_at >= original_updated


def test_owner_ip_stored_but_nullable(session: Session) -> None:
    repo = AiConversationRepository(session)
    with_ip = repo.create_conversation('s1', '203.0.113.9', 't1')
    without_ip = repo.create_conversation('s2', None, 't2')
    session.commit()
    assert with_ip.owner_ip == '203.0.113.9'
    assert without_ip.owner_ip is None
