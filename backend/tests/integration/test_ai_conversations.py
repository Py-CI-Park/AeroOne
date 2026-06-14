from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.modules.collections.search_service import CollectionSearchResult


def _enable_persistence() -> None:
    get_settings().ai_persistence_enabled = True


def _mock_chat(monkeypatch, answer: str = 'AI 응답입니다', citations=None) -> None:
    cits = citations if citations is not None else []

    def fake_chat(self, messages, roots, use_search, limit, **kwargs):
        return answer, cits

    monkeypatch.setattr('app.modules.ai.service.AiChatService.chat', fake_chat)


def _chat(client: TestClient, content: str, **extra):
    body = {'messages': [{'role': 'user', 'content': content}]}
    body.update(extra)
    return client.post('/api/v1/ai/chat', json=body)


def test_chat_does_not_persist_when_flag_off(client, monkeypatch) -> None:
    _mock_chat(monkeypatch)
    response = _chat(client, '엔진 정비 절차')
    assert response.status_code == 200
    payload = response.json()
    assert payload['persisted'] is False
    assert payload['conversation_id'] is None
    # 목록도 비어 있어야 한다(저장 안 함).
    listing = client.get('/api/v1/ai/conversations')
    assert listing.status_code == 200
    assert listing.json()['conversations'] == []


def test_chat_persists_and_lists_with_auto_title(client, monkeypatch) -> None:
    _enable_persistence()
    _mock_chat(monkeypatch, answer='정비 답변')
    response = _chat(client, '엔진 정비 절차 알려줘')
    assert response.status_code == 200
    payload = response.json()
    assert payload['persisted'] is True
    assert payload['conversation_id'] is not None
    # 세션 쿠키가 발급된다(host-only: Domain 미설정).
    assert 'ai_session' in response.cookies

    listing = client.get('/api/v1/ai/conversations')
    convs = listing.json()['conversations']
    assert len(convs) == 1
    assert convs[0]['title'] == '엔진 정비 절차 알려줘'
    assert convs[0]['id'] == payload['conversation_id']


def test_temporary_chat_is_not_persisted(client, monkeypatch) -> None:
    _enable_persistence()
    _mock_chat(monkeypatch)
    response = _chat(client, '민감한 일회성 질문', temporary=True)
    assert response.status_code == 200
    assert response.json()['persisted'] is False
    assert client.get('/api/v1/ai/conversations').json()['conversations'] == []


def test_detail_includes_messages_and_citations(client, monkeypatch) -> None:
    _enable_persistence()
    _mock_chat(
        monkeypatch,
        answer='근거 기반 답변',
        citations=[
            CollectionSearchResult(
                collection='document',
                path='항공/정비.html',
                name='정비',
                folder='항공',
                snippet='정비 근거',
                navigation_url='/documents?path=x',
                score=-1.0,
            )
        ],
    )
    conv_id = _chat(client, '정비 질문').json()['conversation_id']
    detail = client.get(f'/api/v1/ai/conversations/{conv_id}')
    assert detail.status_code == 200
    body = detail.json()
    roles = [m['role'] for m in body['messages']]
    assert roles == ['user', 'assistant']
    assistant = body['messages'][1]
    assert assistant['content'] == '근거 기반 답변'
    assert assistant['citations'][0]['collection'] == 'document'
    assert assistant['citations'][0]['navigation_url'] == '/documents?path=x'


def test_pin_archive_and_title_update(client, monkeypatch) -> None:
    _enable_persistence()
    _mock_chat(monkeypatch)
    conv_id = _chat(client, '질문').json()['conversation_id']
    patched = client.patch(
        f'/api/v1/ai/conversations/{conv_id}',
        json={'is_pinned': True, 'title': '고정된 대화'},
    )
    assert patched.status_code == 200
    assert patched.json()['is_pinned'] is True
    assert patched.json()['title'] == '고정된 대화'

    # 보관하면 기본 목록에서 빠지고 include_archived 로만 보인다.
    client.patch(f'/api/v1/ai/conversations/{conv_id}', json={'is_archived': True})
    assert client.get('/api/v1/ai/conversations').json()['conversations'] == []
    archived = client.get('/api/v1/ai/conversations?include_archived=true').json()['conversations']
    assert len(archived) == 1


def test_delete_conversation(client, monkeypatch) -> None:
    _enable_persistence()
    _mock_chat(monkeypatch)
    conv_id = _chat(client, '삭제될 대화').json()['conversation_id']
    assert client.delete(f'/api/v1/ai/conversations/{conv_id}').status_code == 200
    assert client.get(f'/api/v1/ai/conversations/{conv_id}').status_code == 404
    assert client.get('/api/v1/ai/conversations').json()['conversations'] == []


def test_session_isolation_same_ip_different_cookie(app, monkeypatch) -> None:
    """동일 IP(testclient)·상이 쿠키 두 클라이언트는 서로의 대화를 보지 못한다(404/빈목록)."""
    _enable_persistence()
    _mock_chat(monkeypatch)
    client_a = TestClient(app)
    client_b = TestClient(app)

    conv_id = _chat(client_a, 'A 의 대화').json()['conversation_id']
    assert conv_id is not None

    # B 는 별도 세션 쿠키 → A 의 대화를 못 본다.
    assert client_b.get('/api/v1/ai/conversations').json()['conversations'] == []
    assert client_b.get(f'/api/v1/ai/conversations/{conv_id}').status_code == 404
    assert client_b.delete(f'/api/v1/ai/conversations/{conv_id}').status_code == 404
    assert client_b.patch(
        f'/api/v1/ai/conversations/{conv_id}', json={'is_pinned': True}
    ).status_code == 404

    # A 는 여전히 본인 대화를 본다.
    assert len(client_a.get('/api/v1/ai/conversations').json()['conversations']) == 1


def test_chat_with_unknown_conversation_id_is_404(client, monkeypatch) -> None:
    _enable_persistence()
    _mock_chat(monkeypatch)
    response = _chat(client, '존재하지 않는 대화', conversation_id=999999)
    assert response.status_code == 404


def test_delete_leaves_no_orphan_messages(app, monkeypatch) -> None:
    """대화 삭제 시 메시지/citation 이 고아로 남지 않아야 한다(프라이버시·교차노출 방지)."""
    from sqlalchemy import text

    _enable_persistence()
    _mock_chat(
        monkeypatch,
        answer='삭제 대상 답변',
        citations=[
            CollectionSearchResult(
                collection='document',
                path='a.html',
                name='a',
                folder='',
                snippet='s',
                navigation_url='/documents?path=a',
                score=-1.0,
            )
        ],
    )
    client = TestClient(app)
    conv_id = _chat(client, '삭제될 대화').json()['conversation_id']

    # 삭제 전: 메시지/citation 존재.
    with app.state.db.session() as session:
        assert session.execute(text('SELECT COUNT(*) FROM ai_messages')).scalar() == 2
        assert session.execute(text('SELECT COUNT(*) FROM ai_message_citations')).scalar() == 1

    assert client.delete(f'/api/v1/ai/conversations/{conv_id}').status_code == 200

    # 삭제 후: 고아 0 (운영 엔진 PRAGMA foreign_keys=ON + ORM cascade).
    with app.state.db.session() as session:
        assert session.execute(text('SELECT COUNT(*) FROM ai_messages')).scalar() == 0
        assert session.execute(text('SELECT COUNT(*) FROM ai_message_citations')).scalar() == 0
        assert session.execute(text('SELECT COUNT(*) FROM ai_conversations')).scalar() == 0
