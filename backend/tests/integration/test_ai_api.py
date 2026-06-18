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

    def fake_chat(self, messages, roots, use_search, limit, **kwargs):
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

    def fake_chat(self, messages, roots, use_search, limit, **kwargs):
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


def test_ai_chat_empty_model_response_maps_to_502(client, monkeypatch) -> None:
    # 모델이 빈/추론-only 응답을 준 경우는 연결 다운(503)과 구분해 502 로 떨어진다.
    from app.modules.ai.service import OllamaEmptyResponse

    def fake_chat(self, messages, roots, use_search, limit, **kwargs):
        raise OllamaEmptyResponse('Ollama returned an empty answer (no content after reasoning).')

    monkeypatch.setattr('app.modules.ai.service.AiChatService.chat', fake_chat)
    response = client.post(
        '/api/v1/ai/chat',
        json={'messages': [{'role': 'user', 'content': '안녕'}], 'use_search': False},
    )
    assert response.status_code == 502
    assert 'empty' in response.json()['detail'].lower()


def test_ai_chat_connection_down_maps_to_503_distinct_from_empty(client, monkeypatch) -> None:
    from app.modules.ai.service import OllamaUnavailable

    def fake_chat(self, messages, roots, use_search, limit, **kwargs):
        raise OllamaUnavailable('connection refused')

    monkeypatch.setattr('app.modules.ai.service.AiChatService.chat', fake_chat)
    response = client.post(
        '/api/v1/ai/chat',
        json={'messages': [{'role': 'user', 'content': '안녕'}], 'use_search': False},
    )
    assert response.status_code == 503


def test_ollama_client_strips_think_block_and_guards_empty(settings, monkeypatch) -> None:
    import pytest

    from app.modules.ai.schemas import AiChatMessage
    from app.modules.ai.service import OllamaClient, OllamaEmptyResponse

    ollama = OllamaClient(settings)

    # think:false 를 무시하고 <think> 블록이 본문에 섞여 와도 실제 답변만 반환한다.
    monkeypatch.setattr(
        ollama,
        '_json_request',
        lambda *a, **k: {'message': {'content': '<think>추론 과정</think>\n실제 답변입니다'}},
    )
    assert ollama.chat([AiChatMessage(role='user', content='질문')]) == '실제 답변입니다'

    # 추론-only(본문이 think 뿐) → 빈 답변 → OllamaEmptyResponse(연결 오류 아님).
    monkeypatch.setattr(
        ollama,
        '_json_request',
        lambda *a, **k: {'message': {'content': '<think>추론만 있고 답변 없음</think>'}},
    )
    with pytest.raises(OllamaEmptyResponse):
        ollama.chat([AiChatMessage(role='user', content='질문')])


def test_ollama_client_retries_once_when_first_answer_is_reasoning_only(settings, monkeypatch) -> None:
    from app.modules.ai.schemas import AiChatMessage
    from app.modules.ai.service import OllamaClient

    ollama = OllamaClient(settings)
    calls = []

    def fake_json_request(method, path, body, timeout):
        calls.append(body)
        if len(calls) == 1:
            return {'message': {'content': '<think>추론만 있음</think>'}}
        return {'message': {'content': '최종 답변입니다'}}

    monkeypatch.setattr(ollama, '_json_request', fake_json_request)

    assert ollama.chat([AiChatMessage(role='user', content='질문')]) == '최종 답변입니다'
    assert len(calls) == 2
    assert '최종 답변만 작성' in calls[1]['messages'][0]['content']
