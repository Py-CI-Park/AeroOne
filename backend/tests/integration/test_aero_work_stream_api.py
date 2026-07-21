"""Aero Work SSE 스트리밍 라우트 — 실 앱 HTTP 스택(라우팅·CSRF·인증) 통합 검증.

``streaming.stream_answer``/``stream_compose`` 주입점을 monkeypatch 해 실 LLM 없이
결정적으로 돈다(hits→delta→done 프레임 순서, done JSON 파싱, 익명/CSRF 게이트).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import app.modules.aero_work.api as aero_api


def _sse_frames(text: str) -> list[tuple[str, object]]:
    frames: list[tuple[str, object]] = []
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


class _FakeEmbedder:
    """route 가 생성하는 OllamaEmbedder 를 대체하는 결정적 bag-of-vocab 임베더."""

    model = 'fake-embed'
    VOCAB = ('travel', 'expense', 'security', 'usb', 'export', 'meeting')

    def __init__(self, settings=None) -> None:  # noqa: ANN001 (route 시그니처 호환)
        pass

    def embed_one(self, text: str) -> list[float]:
        low = text.lower()
        return [float(low.count(term)) for term in self.VOCAB]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_one(text) for text in texts]


@pytest.fixture()
def fake_embedder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aero_api, 'build_embedder', lambda _settings, _db: _FakeEmbedder())


@pytest.fixture()
def kb_dir(tmp_path: Path) -> Path:
    root = tmp_path / 'kb'
    root.mkdir()
    (root / 'security.md').write_text('security pledge: usb export is banned', encoding='utf-8')
    return root


def _register_and_index(csrf_client, kb_dir: Path) -> int:
    created = csrf_client.post('/api/v1/aero-work/knowledge/folders', json={'name': '규정', 'path': str(kb_dir)})
    assert created.status_code == 201, created.text
    folder_id = created.json()['id']
    reindex = csrf_client.post(f'/api/v1/aero-work/knowledge/folders/{folder_id}/reindex?inline=true')
    assert reindex.status_code == 200, reindex.text
    return folder_id


def _fake_stream_answer(settings, db, query, hits, *, force_local=False, chat_stream=None):
    yield ('delta', '보안')
    yield ('delta', '서약 안내입니다.')
    yield ('done', '보안서약 안내입니다.')


def _fake_stream_compose(
    settings, db, *, fmt, title, instruction, previous_paragraphs=None, force_local=False, chat_stream=None
):
    yield ('delta', '- 목표를 설정함\n')
    yield ('delta', '후속 조치를 수립함')
    yield ('done', ['목표를 설정함', '후속 조치를 수립함'])


# ---- 익명·CSRF 게이트 ----


def test_answer_stream_anonymous_rejected(client) -> None:
    resp = client.post('/api/v1/aero-work/knowledge/answer/stream', json={'query': 'usb'})
    assert resp.status_code == 401


def test_answer_stream_requires_csrf(client) -> None:
    assert client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'}).status_code == 200
    resp = client.post('/api/v1/aero-work/knowledge/answer/stream', json={'query': 'usb'})
    assert resp.status_code == 403


def test_compose_stream_anonymous_rejected(client) -> None:
    resp = client.post(
        '/api/v1/aero-work/document/compose/stream',
        json={'title': 't', 'instruction': '지시', 'format': 'onepage'},
    )
    assert resp.status_code == 401


def test_compose_stream_requires_csrf(client) -> None:
    assert client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'}).status_code == 200
    resp = client.post(
        '/api/v1/aero-work/document/compose/stream',
        json={'title': 't', 'instruction': '지시', 'format': 'onepage'},
    )
    assert resp.status_code == 403


# ---- 지식 근거 답변 스트림 ----


def test_answer_stream_frame_order_hits_then_delta_then_done(
    csrf_client, fake_embedder, kb_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _register_and_index(csrf_client, kb_dir)
    monkeypatch.setattr(aero_api, 'stream_answer', _fake_stream_answer)

    resp = csrf_client.post('/api/v1/aero-work/knowledge/answer/stream', json={'query': 'usb export'})
    assert resp.status_code == 200, resp.text
    assert resp.headers['content-type'].startswith('text/event-stream')

    frames = _sse_frames(resp.text)
    kinds = [kind for kind, _ in frames]
    assert kinds == ['hits', 'delta', 'delta', 'done']
    hits_data = frames[0][1]
    assert isinstance(hits_data, list) and hits_data and hits_data[0]['rel_path'] == 'security.md'
    assert frames[1][1] == '보안'
    assert frames[2][1] == '서약 안내입니다.'
    assert frames[3][1] == {'answer': '보안서약 안내입니다.'}


def test_answer_stream_error_frame_when_chat_stream_fails(
    csrf_client, fake_embedder, kb_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _register_and_index(csrf_client, kb_dir)

    def failing_stream_answer(settings, db, query, hits, *, force_local=False, chat_stream=None):
        yield ('error', 'LLM 다운')

    monkeypatch.setattr(aero_api, 'stream_answer', failing_stream_answer)

    resp = csrf_client.post('/api/v1/aero-work/knowledge/answer/stream', json={'query': 'usb export'})
    assert resp.status_code == 200, resp.text
    frames = _sse_frames(resp.text)
    assert frames[0][0] == 'hits'
    assert frames[-1] == ('error', 'LLM 다운')


# ---- 문서 내용 생성 스트림 ----


def test_compose_stream_frame_order_delta_then_done(csrf_client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aero_api, 'stream_compose', _fake_stream_compose)

    resp = csrf_client.post(
        '/api/v1/aero-work/document/compose/stream',
        json={'title': '절감 방안', 'instruction': '청사 에너지 절감', 'format': 'onepage'},
    )
    assert resp.status_code == 200, resp.text
    frames = _sse_frames(resp.text)
    kinds = [kind for kind, _ in frames]
    assert kinds == ['delta', 'delta', 'done']
    assert frames[-1][1] == {'paragraphs': ['목표를 설정함', '후속 조치를 수립함'], 'truncated': False}


def test_compose_stream_error_frame_when_stream_fails(csrf_client, monkeypatch: pytest.MonkeyPatch) -> None:
    def failing_stream_compose(
        settings, db, *, fmt, title, instruction, previous_paragraphs=None, force_local=False, chat_stream=None
    ):
        yield ('error', 'LLM 이 빈 내용을 반환했습니다. 지시를 더 구체적으로 적어 보세요.')

    monkeypatch.setattr(aero_api, 'stream_compose', failing_stream_compose)

    resp = csrf_client.post(
        '/api/v1/aero-work/document/compose/stream',
        json={'title': 't', 'instruction': '지시', 'format': 'onepage'},
    )
    assert resp.status_code == 200, resp.text
    frames = _sse_frames(resp.text)
    assert frames[-1][0] == 'error'


# ---- orchestrate: synthesize=false 는 서버측 합성을 생략한다 ----


def test_orchestrate_synthesize_false_skips_answer_synthesis(csrf_client, fake_embedder, kb_dir: Path) -> None:
    _register_and_index(csrf_client, kb_dir)

    resp = csrf_client.post(
        '/api/v1/aero-work/orchestrate', json={'utterance': 'usb export 근거 찾아줘', 'synthesize': False}
    )
    assert resp.status_code == 200, resp.text
    results = resp.json()['results']
    knowledge_results = [item for item in results if item['kind'] == 'knowledge']
    assert knowledge_results, '지식 인텐트가 인식되어야 한다'
    assert knowledge_results[0]['answer'] == ''
