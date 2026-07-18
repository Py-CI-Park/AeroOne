from __future__ import annotations

from app.core.config import get_settings
from app.core.security import hash_password
from app.modules.admin.models import UserPermission
from app.modules.auth.models import User
from app.modules.collections.search_service import CollectionSearchResult


def _sse_frames(text: str) -> list[tuple[str, dict]]:
    import json

    frames: list[tuple[str, dict]] = []
    for block in text.split('\n\n'):
        block = block.strip('\n')
        if not block:
            continue
        event = None
        data = None
        for line in block.split('\n'):
            if line.startswith('event:'):
                event = line[len('event:'):].strip()
            elif line.startswith('data:'):
                data = json.loads(line[len('data:'):].strip())
        assert event is not None and data is not None, f'malformed SSE block: {block!r}'
        frames.append((event, data))
    return frames


def _stream(client, **body):
    payload = {'messages': [{'role': 'user', 'content': '질문'}]}
    payload.update(body)
    return client.post('/api/v1/ai/chat/stream', json=payload)


def test_stream_frame_order_citations_then_delta_then_done(client, monkeypatch) -> None:
    citation = CollectionSearchResult(
        collection='document',
        path='항공/정비.html',
        name='정비',
        folder='항공',
        snippet='정비 절차 근거',
        navigation_url='/documents?path=%ED%95%AD%EA%B3%B5%2F%EC%A0%95%EB%B9%84.html',
        score=-1.0,
    )

    def fake_chat_stream(self, messages, roots, use_search, limit, **kwargs):
        yield ('citations', [citation])
        yield ('delta', '안')
        yield ('delta', '녕')
        yield ('final', '안녕')

    monkeypatch.setattr('app.modules.ai.service.AiChatService.chat_stream', fake_chat_stream)

    response = _stream(client, use_search=True)
    assert response.status_code == 200
    assert response.headers['content-type'].startswith('text/event-stream')
    assert response.headers['cache-control'] == 'no-store'

    frames = _sse_frames(response.text)
    kinds = [event for event, _ in frames]
    assert kinds == ['citations', 'delta', 'delta', 'done']
    assert frames[0][1]['citations'][0]['navigation_url'].startswith('/documents?path=')
    assert frames[1][1] == {'content': '안'}
    assert frames[2][1] == {'content': '녕'}
    assert frames[3][1]['model']
    assert frames[3][1]['persisted'] is False
    assert frames[3][1]['conversation_id'] is None


def test_stream_omits_citations_frame_when_no_citations(client, monkeypatch) -> None:
    def fake_chat_stream(self, messages, roots, use_search, limit, **kwargs):
        yield ('citations', [])
        yield ('delta', '답')
        yield ('final', '답')

    monkeypatch.setattr('app.modules.ai.service.AiChatService.chat_stream', fake_chat_stream)

    response = _stream(client)
    assert response.status_code == 200
    kinds = [event for event, _ in _sse_frames(response.text)]
    assert kinds == ['delta', 'done']


def test_stream_think_block_not_leaked_across_chunk_boundary(client, monkeypatch) -> None:
    # 청크 경계에 여는/닫는 태그가 걸쳐 있어도(<thi|nk>secret</th|ink> 처럼 분할) 절대 노출되지 않는다.
    chunks = ['hello <thi', 'nk>secret</th', 'ink> world']

    def fake_ollama_chat_stream(self, messages, citations=None):
        yield from chunks

    monkeypatch.setattr('app.modules.ai.service.OllamaClient.chat_stream', fake_ollama_chat_stream)

    response = _stream(client)
    assert response.status_code == 200
    frames = _sse_frames(response.text)
    deltas = [data['content'] for event, data in frames if event == 'delta']
    full_visible = ''.join(deltas)
    assert 'secret' not in full_visible
    assert 'think' not in full_visible.lower()
    assert full_visible == 'hello  world'

    done = [data for event, data in frames if event == 'done'][0]
    assert done['persisted'] is False


def test_stream_whitespace_variant_think_tag_not_leaked_live(client, monkeypatch) -> None:
    # G003 회귀: '< think >' 처럼 꺾쇠 안에 공백이 들어간 변형 태그도 비스트리밍 정규식과
    # 동등하게 절대 노출되지 않아야 한다(전체 라이브 /chat/stream 경로로 확인).
    chunks = ['hello < thi', 'nk >secret</  think  > world']

    def fake_ollama_chat_stream(self, messages, citations=None):
        yield from chunks

    monkeypatch.setattr('app.modules.ai.service.OllamaClient.chat_stream', fake_ollama_chat_stream)

    response = _stream(client)
    assert response.status_code == 200
    frames = _sse_frames(response.text)
    deltas = [data['content'] for event, data in frames if event == 'delta']
    full_visible = ''.join(deltas)
    assert 'secret' not in full_visible
    assert 'think' not in full_visible.lower()
    assert full_visible == 'hello  world'


def test_stream_persists_once_after_completion_and_hides_attachment_content(client, monkeypatch) -> None:
    get_settings().ai_persistence_enabled = True
    try:
        def fake_chat_stream(self, messages, roots, use_search, limit, **kwargs):
            assert kwargs['attachments'] and kwargs['attachments'][0].name == 'notes.txt'
            yield ('citations', [])
            yield ('delta', '첨부 기반 답변')
            yield ('final', '첨부 기반 답변')

        monkeypatch.setattr('app.modules.ai.service.AiChatService.chat_stream', fake_chat_stream)

        response = _stream(
            client,
            attachments=[{'name': 'notes.txt', 'content': '극비 첨부 원문 내용'}],
        )
        assert response.status_code == 200
        frames = _sse_frames(response.text)
        done = [data for event, data in frames if event == 'done'][0]
        assert done['persisted'] is True
        assert done['conversation_id'] is not None
        assert 'ai_session' in response.cookies

        detail = client.get(f"/api/v1/ai/conversations/{done['conversation_id']}")
        assert detail.status_code == 200
        messages = detail.json()['messages']
        # 정확히 한 턴(user+assistant)만 append_turn 됐다 — persist-once 보장(중복 저장 없음).
        assert len(messages) == 2
        user_message = next(m for m in messages if m['role'] == 'user')
        assert '[첨부: notes.txt]' in user_message['content']
        assert '극비 첨부 원문 내용' not in user_message['content']
    finally:
        get_settings().ai_persistence_enabled = False


def test_stream_unknown_conversation_id_returns_404_before_streaming(client, monkeypatch) -> None:
    # /chat 과 동일 계약: 미존재 conversation_id 는 새 대화를 만들지 않고 스트림 시작 전 404.
    get_settings().ai_persistence_enabled = True
    try:
        def fake_chat_stream(self, messages, roots, use_search, limit, **kwargs):
            yield ('citations', [])
            yield ('delta', '답')
            yield ('final', '답')

        monkeypatch.setattr('app.modules.ai.service.AiChatService.chat_stream', fake_chat_stream)

        response = _stream(client, conversation_id=999999)
        assert response.status_code == 404

        listing = client.get('/api/v1/ai/conversations')
        assert listing.json()['conversations'] == []
    finally:
        get_settings().ai_persistence_enabled = False


def test_stream_error_frame_on_ollama_unavailable_maps_to_503(client, monkeypatch) -> None:
    from app.modules.ai.service import OllamaUnavailable

    def fake_chat_stream(self, messages, roots, use_search, limit, **kwargs):
        yield ('citations', [])
        yield ('delta', '일부 답변')
        raise OllamaUnavailable('connection refused')

    monkeypatch.setattr('app.modules.ai.service.AiChatService.chat_stream', fake_chat_stream)

    response = _stream(client)
    assert response.status_code == 200  # 헤더가 이미 커밋된 뒤이므로 HTTP status 는 200 유지.
    frames = _sse_frames(response.text)
    kinds = [event for event, _ in frames]
    assert kinds == ['delta', 'error']
    assert frames[-1][1]['status'] == 503
    assert 'connection refused' in frames[-1][1]['detail']


def test_stream_error_frame_on_empty_answer_maps_to_502(client, monkeypatch) -> None:
    from app.modules.ai.service import OllamaEmptyResponse

    def fake_chat_stream(self, messages, roots, use_search, limit, **kwargs):
        yield ('citations', [])
        raise OllamaEmptyResponse('empty after reasoning')

    monkeypatch.setattr('app.modules.ai.service.AiChatService.chat_stream', fake_chat_stream)

    response = _stream(client)
    assert response.status_code == 200
    frames = _sse_frames(response.text)
    assert frames[-1][0] == 'error'
    assert frames[-1][1]['status'] == 502


def test_stream_attachments_exceeding_count_limit_returns_422(client) -> None:
    attachments = [{'name': f'a{i}.txt', 'content': 'x'} for i in range(6)]
    response = _stream(client, attachments=attachments)
    assert response.status_code == 422


def test_stream_attachments_exceeding_total_chars_limit_returns_422(client) -> None:
    attachments = [{'name': 'big.txt', 'content': 'x' * 200_001}]
    response = _stream(client, attachments=attachments)
    assert response.status_code == 422


def test_stream_attachment_with_disallowed_extension_returns_422(client) -> None:
    attachments = [{'name': 'payload.exe', 'content': 'x'}]
    response = _stream(client, attachments=attachments)
    assert response.status_code == 422


def test_stream_compatible_selected_without_ai_use_returns_403_before_streaming(client, app, monkeypatch) -> None:
    from app.modules.ai.provider_config_service import ProviderConfigService
    from app.modules.admin.schemas import AiProviderConfigResponse
    from datetime import UTC, datetime

    with app.state.db.session() as session:
        user = User(username='no-ai-use-stream', password_hash=hash_password('password'), role='pending', is_active=True)
        session.add(user)
        session.commit()

    login = client.post('/api/v1/auth/login', json={'username': 'no-ai-use-stream', 'password': 'password'})
    assert login.status_code == 200

    monkeypatch.setattr(
        ProviderConfigService,
        'get_state',
        lambda self: AiProviderConfigResponse(
            selected_kind='openai_compatible',
            compatible_state='verified',
            compatible_display_url='https://provider.example',
            compatible_model='gpt-x',
            compatible_generation='2024-01',
            compatible_test_proof_at=datetime.now(UTC),
            compatible_test_proof_model='gpt-x',
            config_version=3,
            updated_at=datetime.now(UTC),
        ),
    )

    called = {'chat_stream': False}

    def fake_chat_stream(self, *args, **kwargs):
        called['chat_stream'] = True
        yield ('final', 'should not run')

    monkeypatch.setattr('app.modules.ai.service.AiChatService.chat_stream', fake_chat_stream)

    response = _stream(client)
    assert response.status_code == 403
    assert response.json()['detail'] == 'ai_use_required'
    assert response.headers['content-type'].startswith('application/json')
    assert called['chat_stream'] is False


def test_stream_compatible_selected_with_ai_use_permission_allowed(client, app, monkeypatch) -> None:
    from app.modules.ai.provider_config_service import ProviderConfigService
    from app.modules.admin.schemas import AiProviderConfigResponse
    from datetime import UTC, datetime

    with app.state.db.session() as session:
        user = User(username='ai-use-stream', password_hash=hash_password('password'), role='user', is_active=True)
        session.add(user)
        session.flush()
        session.add(UserPermission(user_id=user.id, permission_key='ai.use'))
        session.commit()

    login = client.post('/api/v1/auth/login', json={'username': 'ai-use-stream', 'password': 'password'})
    assert login.status_code == 200

    monkeypatch.setattr(
        ProviderConfigService,
        'get_state',
        lambda self: AiProviderConfigResponse(
            selected_kind='openai_compatible',
            compatible_state='verified',
            compatible_display_url='https://provider.example',
            compatible_model='gpt-x',
            compatible_generation='2024-01',
            compatible_test_proof_at=datetime.now(UTC),
            compatible_test_proof_model='gpt-x',
            config_version=3,
            updated_at=datetime.now(UTC),
        ),
    )

    def fake_chat_stream(self, messages, roots, use_search, limit, **kwargs):
        yield ('citations', [])
        yield ('delta', 'compatible answer')
        yield ('final', 'compatible answer')

    monkeypatch.setattr('app.modules.ai.service.AiChatService.chat_stream', fake_chat_stream)

    response = _stream(client)
    assert response.status_code == 200
    frames = _sse_frames(response.text)
    deltas = [data['content'] for event, data in frames if event == 'delta']
    assert deltas == ['compatible answer']
    assert frames[-1][0] == 'done'


def test_stream_retries_once_when_no_visible_delta_before_empty_final(client, monkeypatch) -> None:
    # 가시 delta 가 전혀 없었던 상태(think 전용 응답)에서 최종본이 비면 1회 재시도한다.
    calls = {'count': 0}

    def fake_ollama_chat_stream(self, messages, citations=None):
        calls['count'] += 1
        if calls['count'] == 1:
            yield '<think>reasoning only, nothing visible</think>'
        else:
            assert any(
                message.role == 'system' and '추론 과정이나 <think>' in message.content
                for message in messages
            )
            yield 'final visible answer'

    monkeypatch.setattr('app.modules.ai.service.OllamaClient.chat_stream', fake_ollama_chat_stream)

    response = _stream(client)
    assert response.status_code == 200
    frames = _sse_frames(response.text)
    deltas = [data['content'] for event, data in frames if event == 'delta']
    assert deltas == ['final visible answer']
    assert calls['count'] == 2
    assert frames[-1][0] == 'done'


def test_stream_does_not_retry_once_visible_delta_already_sent_before_empty_final(client, monkeypatch) -> None:
    # 이미 가시 delta 가 나간 뒤라면(공백 한 글자라도) 재시도하지 않고 기존 502 empty-answer
    # 경로를 그대로 탄다. strip() 후 빈 최종본이 되는 경우를 만들기 위해 공백 delta 를 쓴다
    # (실제 텍스트 delta 는 strip 후에도 비지 않으므로 재현이 불가능하다 — 이 케이스는 오직
    # visible_count>0 인데 최종본이 빈 경계 상황을 시험하기 위한 것이다).
    calls = {'count': 0}

    def fake_ollama_chat_stream(self, messages, citations=None):
        calls['count'] += 1
        yield ' '
        yield '<think>the rest is only reasoning</think>'

    monkeypatch.setattr('app.modules.ai.service.OllamaClient.chat_stream', fake_ollama_chat_stream)

    response = _stream(client)
    assert response.status_code == 200
    frames = _sse_frames(response.text)
    kinds = [event for event, _ in frames]
    assert kinds == ['delta', 'error']
    assert frames[-1][1]['status'] == 502
    assert calls['count'] == 1


def test_stream_client_abort_logs_aborted_request(app, monkeypatch) -> None:
    from starlette.responses import StreamingResponse

    from app.core.config import get_settings
    from app.db.session import get_db_session
    from app.modules.admin.models import AiRequestLog
    from app.modules.ai.api.public import chat_stream_with_ai
    from app.modules.ai.schemas import AiChatRequest

    def fake_chat_stream(self, messages, roots, use_search, limit, **kwargs):
        yield ('citations', [])
        for i in range(1000):
            yield ('delta', f'chunk-{i}')

    monkeypatch.setattr('app.modules.ai.service.AiChatService.chat_stream', fake_chat_stream)

    # StreamingResponse 는 sync 제너레이터를 iterate_in_threadpool 로 감싸 실제 진행을 별도
    # 스레드로 넘긴다 — 원본 sync 제너레이터에 직접 close() 를 걸어 결정적으로(스레드/이벤트
    # 루프 경합 없이) GeneratorExit 을 재현하기 위해 래핑 직전의 content 인자를 가로챈다.
    captured: dict[str, object] = {}
    original_init = StreamingResponse.__init__

    def capturing_init(self, content, *args, **kwargs):
        captured['gen'] = content
        return original_init(self, content, *args, **kwargs)

    monkeypatch.setattr(StreamingResponse, '__init__', capturing_init)

    class _FakeRequest:
        cookies: dict[str, str] = {}
        client = None

    db = next(get_db_session())
    try:
        chat_stream_with_ai(
            payload=AiChatRequest(messages=[{'role': 'user', 'content': '질문'}]),
            request=_FakeRequest(),
            settings=get_settings(),
            db=db,
            current_user=None,
        )

        raw_generator = captured['gen']
        next(raw_generator)  # citations 프레임까지 진행시켜 for 루프 안에서 멈춰 세운다.
        raw_generator.close()  # 클라이언트 연결 종료(GeneratorExit)를 시뮬레이션한다.

        rows = db.query(AiRequestLog).filter(AiRequestLog.status == 'aborted').all()
        assert len(rows) == 1
        assert rows[0].error_code == 'ClientAborted'
    finally:
        db.close()

def test_stream_persist_failure_emits_done_with_persist_error_and_logs(client, monkeypatch) -> None:
    # M2 회귀: 영속화가 실패해도 스트림은 done{persisted:false, persist_error}로 계약을 지키고
    # AiRequestLog 에 PersistFailed 1건을 남긴다(스트림 절단 금지).
    from app.modules.ai.repositories import AiConversationRepository

    get_settings().ai_persistence_enabled = True
    try:
        def fake_chat_stream(self, messages, roots, use_search, limit, **kwargs):
            yield ('citations', [])
            yield ('delta', '답')
            yield ('final', '답')

        monkeypatch.setattr('app.modules.ai.service.AiChatService.chat_stream', fake_chat_stream)

        def boom(self, *args, **kwargs):
            raise RuntimeError('disk full')

        monkeypatch.setattr(AiConversationRepository, 'append_turn', boom)

        response = _stream(client)
        assert response.status_code == 200
        frames = _sse_frames(response.text)
        done = [data for event, data in frames if event == 'done'][0]
        assert done['persisted'] is False
        assert done['persist_error']
        assert not [1 for event, _ in frames if event == 'error']

        from app.modules.admin.models import AiRequestLog
        from sqlalchemy import select
        from app.db.session import get_session_factory
        with get_session_factory()() as session:
            rows = session.scalars(select(AiRequestLog).order_by(AiRequestLog.id.desc())).all()
            assert rows and rows[0].status == 'error' and rows[0].error_code == 'PersistFailed'
    finally:
        get_settings().ai_persistence_enabled = False


def test_stream_conversation_deleted_mid_stream_does_not_create_new_conversation(client, monkeypatch) -> None:
    # M2 회귀: 스트림 중 대화가 삭제되면 새 대화를 만들지 않고 persisted:false 로 종결한다.
    get_settings().ai_persistence_enabled = True
    try:
        def fake_chat_stream_first(self, messages, roots, use_search, limit, **kwargs):
            yield ('citations', [])
            yield ('delta', '첫 답')
            yield ('final', '첫 답')

        monkeypatch.setattr('app.modules.ai.service.AiChatService.chat_stream', fake_chat_stream_first)
        first = _stream(client)
        assert first.status_code == 200
        first_done = [d for e, d in _sse_frames(first.text) if e == 'done'][0]
        conversation_id = first_done['conversation_id']
        assert conversation_id is not None

        # 스트림 도중(제너레이터 진행 중) 대화가 삭제되는 레이스를 재현한다.
        def fake_chat_stream_deleting(self, messages, roots, use_search, limit, **kwargs):
            yield ('citations', [])
            delete = client.delete(f'/api/v1/ai/conversations/{conversation_id}')
            assert delete.status_code == 200
            yield ('delta', '둘째 답')
            yield ('final', '둘째 답')

        monkeypatch.setattr('app.modules.ai.service.AiChatService.chat_stream', fake_chat_stream_deleting)
        second = _stream(client, conversation_id=conversation_id)
        assert second.status_code == 200
        done = [d for e, d in _sse_frames(second.text) if e == 'done'][0]
        assert done['persisted'] is False

        listing = client.get('/api/v1/ai/conversations')
        assert listing.json()['conversations'] == []
    finally:
        get_settings().ai_persistence_enabled = False
