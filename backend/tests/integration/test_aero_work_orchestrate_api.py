"""업무대화 오케스트레이션 REST — 발화→인텐트 실행 통합 검증(실 앱 HTTP 스택)."""

from __future__ import annotations


def _orchestrate(csrf_client, utterance: str):
    resp = csrf_client.post('/api/v1/aero-work/orchestrate', json={'utterance': utterance})
    assert resp.status_code == 200, resp.text
    return resp.json()['results']


def test_orchestrate_anonymous_rejected(client) -> None:
    assert client.post('/api/v1/aero-work/orchestrate', json={'utterance': 'x'}).status_code == 401


def test_orchestrate_requires_csrf(client) -> None:
    assert client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'}).status_code == 200
    resp = client.post('/api/v1/aero-work/orchestrate', json={'utterance': '내일 회의 등록'})
    assert resp.status_code == 403


def test_schedule_create_then_list_then_delete(csrf_client) -> None:
    created = _orchestrate(csrf_client, '내일 오전 10시 주간회의 일정 등록해줘')
    assert created[0]['kind'] == 'schedule.create'
    assert created[0]['events'] and '주간회의' in created[0]['events'][0]['title']

    listed = _orchestrate(csrf_client, '이번 주 일정 알려줘')
    assert listed[0]['kind'] == 'schedule.list'
    assert any('주간회의' in event['title'] for event in listed[0]['events'])

    deleted = _orchestrate(csrf_client, '내일 주간회의 일정 삭제해줘')
    assert deleted[0]['kind'] == 'schedule.delete'
    assert '주간회의' in deleted[0]['summary']


def test_document_intent_recognized(csrf_client) -> None:
    results = _orchestrate(csrf_client, '청사 에너지 절감 방안을 1페이지 보고서로 작성해줘')
    assert results[0]['kind'] == 'document'
    assert results[0]['document']['format'] == 'onepage'


def test_help_intent(csrf_client) -> None:
    results = _orchestrate(csrf_client, '문서작성 어떻게 하는지 알려줘')
    assert results[0]['kind'] == 'help'
    assert results[0]['summary']


def test_multi_intent_schedule_and_document(csrf_client) -> None:
    results = _orchestrate(csrf_client, '내일 오후 2시 부서 워크숍 등록하고 그 내용으로 보고서 작성해줘')
    kinds = [item['kind'] for item in results]
    assert kinds == ['schedule.create', 'document']
    assert results[0]['events']


def test_knowledge_intent_returns_gracefully(csrf_client) -> None:
    # 색인된 폴더가 없어도 200 + kind=knowledge (Ollama 유무와 무관하게 graceful).
    results = _orchestrate(csrf_client, '예산 편성 근거 찾아줘')
    assert results[0]['kind'] == 'knowledge'
    assert results[0]['summary']


def test_chat_history_persists_exchanges(csrf_client, client) -> None:
    _orchestrate(csrf_client, '내일 오전 9시 히스토리 회의 등록해줘')

    history = csrf_client.get('/api/v1/aero-work/chat/history')
    assert history.status_code == 200, history.text
    items = history.json()['items']
    assert items and items[0]['utterance'] == '내일 오전 9시 히스토리 회의 등록해줘'
    assert items[0]['results'][0]['kind'] == 'schedule.create'
    assert items[0]['results'][0]['events'][0]['title'].startswith('히스토리')


def test_chat_sessions_flow(csrf_client) -> None:
    # 세션 미지정 → 자동 생성(제목=발화 40자)
    first = csrf_client.post('/api/v1/aero-work/orchestrate', json={'utterance': '이번 주 일정 알려줘'})
    assert first.status_code == 200, first.text
    session_id = first.json()['session_id']
    assert session_id is not None

    sessions = csrf_client.get('/api/v1/aero-work/chat/sessions').json()['sessions']
    assert sessions[0]['id'] == session_id
    assert sessions[0]['title'].startswith('이번 주 일정')

    # 같은 세션 이어가기
    second = csrf_client.post(
        '/api/v1/aero-work/orchestrate',
        json={'utterance': '문서작성 어떻게 하는지 알려줘', 'session_id': session_id},
    )
    assert second.json()['session_id'] == session_id
    history = csrf_client.get(f'/api/v1/aero-work/chat/history?session_id={session_id}').json()['items']
    assert len(history) == 2

    # 새 세션은 분리
    third = csrf_client.post('/api/v1/aero-work/orchestrate', json={'utterance': '예산 근거 찾아줘'})
    other_id = third.json()['session_id']
    assert other_id != session_id
    assert len(csrf_client.get(f'/api/v1/aero-work/chat/history?session_id={other_id}').json()['items']) == 1

    # 세션 삭제 → 메시지도 제거
    assert csrf_client.delete(f'/api/v1/aero-work/chat/sessions/{session_id}').status_code == 204
    assert csrf_client.get(f'/api/v1/aero-work/chat/history?session_id={session_id}').json()['items'] == []
