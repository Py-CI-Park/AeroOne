from __future__ import annotations

from app.modules.collections.search_service import CollectionSearchResult, CollectionSearchUnavailable


def test_ai_status_reports_model_available(client, monkeypatch) -> None:
    def fake_status(self):
        return {
            'enabled': True,
            'base_url': 'http://ollama.test:11434',
            'model': 'gemma4:12b',
            'reachable': True,
            'model_available': True,
            'status': 'ok',
            'detail': None,
        }

    monkeypatch.setattr('app.modules.ai.service.AiChatService.status', fake_status)

    response = client.get('/api/v1/ai/status')

    assert response.status_code == 200
    assert response.json()['model'] == 'gemma4:12b'
    assert response.json()['status'] == 'ok'


def test_ai_chat_uses_default_document_civil_scope_and_returns_citations(client, monkeypatch) -> None:
    captured = {}

    def fake_chat(self, messages, roots, use_search, limit):
        captured['collections'] = [root.collection for root in roots]
        captured['use_search'] = use_search
        captured['limit'] = limit
        return '검색 근거 기반 답변', [
            CollectionSearchResult(
                collection='document',
                path='항공/정비.html',
                name='정비',
                folder='항공',
                snippet='정비 절차 근거',
                navigation_url='/documents?path=%ED%95%AD%EA%B3%B5%2F%EC%A0%95%EB%B9%84.html',
                score=-1.0,
            )
        ]

    monkeypatch.setattr('app.modules.ai.service.AiChatService.chat', fake_chat)

    response = client.post(
        '/api/v1/ai/chat',
        json={
            'messages': [{'role': 'user', 'content': '정비 절차 찾아줘'}],
            'use_search': True,
            'limit': 4,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert captured == {'collections': ['document', 'civil'], 'use_search': True, 'limit': 4}
    assert payload['model'] == 'gemma4:12b'
    assert payload['message'] == {'role': 'assistant', 'content': '검색 근거 기반 답변'}
    assert payload['citations'][0]['navigation_url'].startswith('/documents?path=')


def test_ai_chat_allows_explicit_nsa_scope_for_unlocked_flow(client, monkeypatch) -> None:
    captured = {}

    def fake_chat(self, messages, roots, use_search, limit):
        captured['collections'] = [root.collection for root in roots]
        return 'nsa answer', []

    monkeypatch.setattr('app.modules.ai.service.AiChatService.chat', fake_chat)

    response = client.post(
        '/api/v1/ai/chat',
        json={
            'messages': [{'role': 'user', 'content': 'NSA 질의'}],
            'use_search': True,
            'collections': ['nsa'],
        },
    )

    assert response.status_code == 200
    assert captured['collections'] == ['nsa']


def test_ai_chat_degrades_to_plain_chat_when_collection_search_unavailable(client, monkeypatch) -> None:
    def fake_search(self, roots, query, managed_storage_root, limit=20):
        raise CollectionSearchUnavailable('SQLite FTS5 is unavailable')

    def fake_ollama_chat(self, messages, citations=None):
        assert citations == []
        return '검색 없이 답변'

    monkeypatch.setattr('app.modules.collections.search_service.HtmlCollectionSearchService.search', fake_search)
    monkeypatch.setattr('app.modules.ai.service.OllamaClient.chat', fake_ollama_chat)

    response = client.post(
        '/api/v1/ai/chat',
        json={
            'messages': [{'role': 'user', 'content': '질문'}],
            'use_search': True,
        },
    )

    assert response.status_code == 200
    assert response.json()['message']['content'] == '검색 없이 답변'
    assert response.json()['citations'] == []


def test_ai_chat_rejects_unknown_collection(client) -> None:
    response = client.post(
        '/api/v1/ai/chat',
        json={
            'messages': [{'role': 'user', 'content': '질문'}],
            'collections': ['secrets'],
        },
    )

    # Pydantic literal validation rejects before route collection resolution.
    assert response.status_code == 422
