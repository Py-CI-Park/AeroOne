from __future__ import annotations

from urllib import error as urllib_error

import pytest

from app.modules.ai import service as service_module
from app.modules.ai.schemas import AiChatMessage
from app.modules.ai.service import OllamaClient, OllamaModelMissing, OllamaUnavailable


class _FakeHttpResponse:
    def __init__(self, lines: list[bytes]) -> None:
        self._lines = lines

    def __enter__(self) -> '_FakeHttpResponse':
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def __iter__(self):
        return iter(self._lines)


def _ndjson_lines(*frames: dict) -> list[bytes]:
    import json

    return [(json.dumps(frame) + '\n').encode('utf-8') for frame in frames]


def test_stream_chat_answer_parses_ndjson_content_chunks_in_order(settings, monkeypatch) -> None:
    ollama = OllamaClient(settings)
    lines = _ndjson_lines(
        {'message': {'content': '안'}, 'done': False},
        {'message': {'content': '녕'}, 'done': False},
        {'message': {'content': '하세요'}, 'done': True},
    )
    monkeypatch.setattr(service_module.request, 'urlopen', lambda req, timeout=None: _FakeHttpResponse(lines))

    chunks = list(ollama._stream_chat_answer([{'role': 'user', 'content': '안녕'}]))
    assert chunks == ['안', '녕', '하세요']


def test_stream_chat_answer_stops_iterating_once_done_true_frame_seen(settings, monkeypatch) -> None:
    ollama = OllamaClient(settings)
    lines = _ndjson_lines(
        {'message': {'content': 'first'}, 'done': True},
        {'message': {'content': 'should-not-appear'}, 'done': False},
    )
    monkeypatch.setattr(service_module.request, 'urlopen', lambda req, timeout=None: _FakeHttpResponse(lines))

    chunks = list(ollama._stream_chat_answer([{'role': 'user', 'content': 'hi'}]))
    assert chunks == ['first']


def test_stream_chat_answer_skips_blank_and_malformed_json_lines(settings, monkeypatch) -> None:
    ollama = OllamaClient(settings)
    lines = [
        b'\n',
        b'not-json{{{',
        *_ndjson_lines({'message': {'content': 'ok'}, 'done': True}),
    ]
    monkeypatch.setattr(service_module.request, 'urlopen', lambda req, timeout=None: _FakeHttpResponse(lines))

    chunks = list(ollama._stream_chat_answer([{'role': 'user', 'content': 'hi'}]))
    assert chunks == ['ok']


def test_stream_chat_answer_ignores_frames_without_string_content(settings, monkeypatch) -> None:
    ollama = OllamaClient(settings)
    lines = _ndjson_lines(
        {'message': {'content': None}, 'done': False},
        {'message': {}, 'done': False},
        {'done': False},
        {'message': {'content': 'final'}, 'done': True},
    )
    monkeypatch.setattr(service_module.request, 'urlopen', lambda req, timeout=None: _FakeHttpResponse(lines))

    chunks = list(ollama._stream_chat_answer([{'role': 'user', 'content': 'hi'}]))
    assert chunks == ['final']


def test_stream_chat_answer_raises_model_missing_on_http_404(settings, monkeypatch) -> None:
    ollama = OllamaClient(settings)

    def fake_urlopen(req, timeout=None):
        raise urllib_error.HTTPError(req.full_url, 404, 'not found', hdrs=None, fp=None)

    monkeypatch.setattr(service_module.request, 'urlopen', fake_urlopen)

    with pytest.raises(OllamaModelMissing):
        list(ollama._stream_chat_answer([{'role': 'user', 'content': 'hi'}]))


def test_stream_chat_answer_raises_unavailable_on_other_http_errors(settings, monkeypatch) -> None:
    ollama = OllamaClient(settings)

    def fake_urlopen(req, timeout=None):
        raise urllib_error.HTTPError(req.full_url, 500, 'server error', hdrs=None, fp=None)

    monkeypatch.setattr(service_module.request, 'urlopen', fake_urlopen)

    with pytest.raises(OllamaUnavailable):
        list(ollama._stream_chat_answer([{'role': 'user', 'content': 'hi'}]))


def test_chat_stream_dispatches_through_stream_chat_answer(settings, monkeypatch) -> None:
    ollama = OllamaClient(settings)
    lines = _ndjson_lines({'message': {'content': 'hello'}, 'done': True})
    monkeypatch.setattr(service_module.request, 'urlopen', lambda req, timeout=None: _FakeHttpResponse(lines))

    chunks = list(ollama.chat_stream([AiChatMessage(role='user', content='질문')]))
    assert chunks == ['hello']
