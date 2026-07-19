"""SSE 스트리밍 제너레이터 — 주입 chat_stream 으로 delta 순서·done 값·error 경로 검증(실 LLM 없이 결정적)."""

from __future__ import annotations

from app.core.config import Settings
from app.modules.aero_work.streaming import stream_answer, stream_compose


def _settings(**overrides) -> Settings:
    return Settings(app_env='test', jwt_secret_key='x', **overrides)


_HITS = [{'folder_id': 1, 'folder_name': '총무', 'rel_path': 'a.txt', 'content': '연차 규정입니다.'}]


def test_stream_answer_yields_delta_then_done_with_injected_chat_stream() -> None:
    captured: dict = {}

    def fake_chat_stream(settings, db, messages):
        captured['system'] = messages[0].content
        captured['user'] = messages[1].content
        yield '연차는 '
        yield '15일입니다.'

    events = list(stream_answer(_settings(), None, '연차 며칠?', _HITS, chat_stream=fake_chat_stream))
    assert events == [('delta', '연차는 '), ('delta', '15일입니다.'), ('done', '연차는 15일입니다.')]
    assert '[근거 N]' in captured['system']
    assert '연차 며칠?' in captured['user'] and '연차 규정입니다.' in captured['user']


def test_stream_answer_no_hits_short_circuits_to_empty_done() -> None:
    def boom(settings, db, messages):
        raise AssertionError('근거가 없으면 chat_stream 을 호출하면 안 된다')
        yield ''  # pragma: no cover

    events = list(stream_answer(_settings(), None, '질문', [], chat_stream=boom))
    assert events == [('done', '')]


def test_stream_answer_ai_disabled_short_circuits() -> None:
    def boom(settings, db, messages):
        raise AssertionError('AI 비활성화 시 chat_stream 을 호출하면 안 된다')
        yield ''  # pragma: no cover

    events = list(stream_answer(_settings(ai_features_enabled=False), None, '질문', _HITS, chat_stream=boom))
    assert events == [('done', '')]


def test_stream_answer_chat_stream_error_yields_error_and_stops() -> None:
    def failing(settings, db, messages):
        yield '일부 '
        raise RuntimeError('LLM 다운')

    events = list(stream_answer(_settings(), None, '질문', _HITS, chat_stream=failing))
    assert events[0] == ('delta', '일부 ')
    assert events[1][0] == 'error' and 'LLM 다운' in events[1][1]
    assert len(events) == 2  # error 이후 done 은 나오지 않는다


def test_stream_compose_yields_delta_then_done_lines() -> None:
    def fake_chat_stream(settings, db, messages):
        assert '절감 방안' in messages[1].content
        yield '- 목표를 10%로 설정함\n'
        yield '조명을 교체함'

    events = list(
        stream_compose(
            _settings(), None, fmt='onepage', title='절감 방안', instruction='청사 에너지 절감',
            chat_stream=fake_chat_stream,
        )
    )
    assert events[:2] == [('delta', '- 목표를 10%로 설정함\n'), ('delta', '조명을 교체함')]
    assert events[2] == ('done', ['목표를 10%로 설정함', '조명을 교체함'])


def test_stream_compose_empty_instruction_short_circuits_to_error() -> None:
    def boom(settings, db, messages):
        raise AssertionError('지시가 없으면 chat_stream 을 호출하면 안 된다')
        yield ''  # pragma: no cover

    events = list(stream_compose(_settings(), None, fmt='onepage', title='t', instruction='   ', chat_stream=boom))
    assert len(events) == 1 and events[0][0] == 'error'


def test_stream_compose_empty_answer_yields_error() -> None:
    def empty_stream(settings, db, messages):
        yield '   '

    events = list(
        stream_compose(_settings(), None, fmt='onepage', title='t', instruction='지시', chat_stream=empty_stream)
    )
    assert events[-1][0] == 'error'


def test_stream_compose_chat_stream_error_yields_error() -> None:
    def failing(settings, db, messages):
        raise RuntimeError('연결 실패')
        yield ''  # pragma: no cover

    events = list(
        stream_compose(_settings(), None, fmt='onepage', title='t', instruction='지시', chat_stream=failing)
    )
    assert events == [('error', '연결 실패')]
