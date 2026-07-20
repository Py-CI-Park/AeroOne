"""Aero Work 문서작성(HWPX) REST — 실 앱 HTTP 스택 + 다운로드 + 기록 통합 검증."""

from __future__ import annotations

import io
import zipfile


def test_document_anonymous_rejected(client) -> None:
    resp = client.post('/api/v1/aero-work/document/hwpx', json={'title': 'x', 'body': 'y'})
    assert resp.status_code == 401


def test_document_requires_csrf(client) -> None:
    assert client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'}).status_code == 200
    resp = client.post('/api/v1/aero-work/document/hwpx', json={'title': 'x', 'body': 'y'})
    assert resp.status_code == 403


def test_document_generates_valid_hwpx_and_records(csrf_client) -> None:
    resp = csrf_client.post(
        '/api/v1/aero-work/document/hwpx',
        json={'title': '출장 결과 보고', 'body': '대전 방문함.\n특이사항 없음.'},
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers['content-type'] == 'application/hwp+zip'
    assert 'attachment' in resp.headers['content-disposition']

    archive = zipfile.ZipFile(io.BytesIO(resp.content))
    assert archive.infolist()[0].filename == 'mimetype'
    assert archive.read('mimetype').decode('utf-8') == 'application/hwp+zip'
    assert '출장 결과 보고' in archive.read('Contents/section0.xml').decode('utf-8')

    activities = csrf_client.get('/api/v1/aero-work/activity').json()['activities']
    assert activities[0]['kind'] == 'document.generate'
    assert '출장 결과 보고' in activities[0]['summary']


def test_official_format_applies_hierarchy(csrf_client) -> None:
    resp = csrf_client.post(
        '/api/v1/aero-work/document/hwpx',
        json={'title': '협조 요청', 'body': '자료 제출 협조\n기한 엄수', 'format': 'official'},
    )
    assert resp.status_code == 200, resp.text
    section = zipfile.ZipFile(io.BytesIO(resp.content)).read('Contents/section0.xml').decode('utf-8')
    assert '수신' in section
    assert '제목' in section
    assert '1. 자료 제출 협조' in section
    assert '끝.' in section


# ---- 종이 미리보기(G005) ----


def test_preview_anonymous_rejected(client) -> None:
    resp = client.post(
        '/api/v1/aero-work/document/preview',
        json={'format_id': 'onepage', 'title': 't', 'paragraphs': ['x']},
    )
    assert resp.status_code == 401


def test_preview_requires_csrf(client) -> None:
    assert client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'}).status_code == 200
    resp = client.post(
        '/api/v1/aero-work/document/preview',
        json={'format_id': 'onepage', 'title': 't', 'paragraphs': ['x']},
    )
    assert resp.status_code == 403


def test_preview_official_renders_hierarchy_and_does_not_record_activity(csrf_client) -> None:
    """L3: preview 는 디바운스 재요청이 빈번해 실행기록을 남기지 않는다."""

    resp = csrf_client.post(
        '/api/v1/aero-work/document/preview',
        json={'format_id': 'official', 'title': '협조 요청', 'paragraphs': ['자료 제출 협조', '기한 엄수']},
    )
    assert resp.status_code == 200, resp.text
    html = resp.json()['html']
    assert '수신' in html
    assert '1. 자료 제출 협조' in html
    assert '끝.' in html

    activities = csrf_client.get('/api/v1/aero-work/activity').json()['activities']
    assert activities == []


def test_preview_escapes_script_injection(csrf_client) -> None:
    resp = csrf_client.post(
        '/api/v1/aero-work/document/preview',
        json={'format_id': 'onepage', 'title': '<script>alert(1)</script>', 'paragraphs': ['<b>x</b>']},
    )
    assert resp.status_code == 200, resp.text
    html = resp.json()['html']
    assert '<script>' not in html
    assert '&lt;script&gt;' in html
    assert '<b>x</b>' not in html
    assert '&lt;b&gt;x&lt;/b&gt;' in html


def test_preview_unsupported_format_rejected_with_422(csrf_client) -> None:
    resp = csrf_client.post(
        '/api/v1/aero-work/document/preview',
        json={'format_id': 'pdf', 'title': 't', 'paragraphs': ['x']},
    )
    assert resp.status_code == 422


def test_compose_with_previous_paragraphs_regenerates_via_revision_instruction(
    csrf_client, monkeypatch
) -> None:
    """수정 지시 → previous_paragraphs 를 함께 보내면 재생성 프롬프트에 이전 본문과 지시가
    모두 반영되어야 한다(``document_composer.compose_content`` 실호출, chat 만 주입 스텁)."""

    captured: dict = {}

    def fake_default_chat(settings, db, messages):
        captured['user'] = messages[1].content
        return '목표를 15%로 상향함'

    monkeypatch.setattr('app.modules.aero_work.document_composer._default_chat', fake_default_chat)

    resp = csrf_client.post(
        '/api/v1/aero-work/document/compose',
        json={
            'title': '절감 방안',
            'instruction': '목표를 15%로 올려줘',
            'format': 'onepage',
            'previous_paragraphs': ['목표를 10%로 설정함', '조명 교체를 추진함'],
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {'paragraphs': ['목표를 15%로 상향함'], 'truncated': False}
    assert '이전 본문' in captured['user']
    assert '목표를 10%로 설정함' in captured['user'] and '조명 교체를 추진함' in captured['user']
    assert '수정 지시' in captured['user']
    assert '목표를 15%로 올려줘' in captured['user']


def test_compose_stream_with_previous_paragraphs_passes_through_to_prompt_builder(
    csrf_client, monkeypatch
) -> None:
    """L5: 스트리밍 경로(``/document/compose/stream``)도 비스트리밍과 동일하게
    ``previous_paragraphs`` 를 프롬프트 조립(``build_compose_messages``)까지 관통시킨다."""

    from app.modules.ai.schemas import AiChatMessage

    captured: dict = {}

    def fake_build_compose_messages(fmt, title, instruction, previous_paragraphs=None):
        captured['previous_paragraphs'] = previous_paragraphs
        return [AiChatMessage(role='system', content='sys'), AiChatMessage(role='user', content='user')]

    def fake_default_chat_stream(settings, db, messages):
        yield '재생성 결과'

    monkeypatch.setattr('app.modules.aero_work.streaming.build_compose_messages', fake_build_compose_messages)
    monkeypatch.setattr('app.modules.aero_work.streaming._default_chat_stream', fake_default_chat_stream)

    resp = csrf_client.post(
        '/api/v1/aero-work/document/compose/stream',
        json={
            'title': '절감 방안',
            'instruction': '목표를 15%로 올려줘',
            'format': 'onepage',
            'previous_paragraphs': ['목표를 10%로 설정함'],
        },
    )
    assert resp.status_code == 200, resp.text
    assert captured['previous_paragraphs'] == ['목표를 10%로 설정함']
