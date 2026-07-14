from __future__ import annotations

import socket
from types import SimpleNamespace
from typing import Any

import pytest

from app.core.config import Settings
from app.modules.ai import service as service_module
from app.modules.ai.egress_transport import (
    EgressError,
    EgressErrorCode,
    EgressOutcome,
    EgressPolicy,
    PeerPolicy,
    chat_completion,
    probe_models,
)
from app.modules.ai.provider_config_service import ActiveCompatibleBinding
from app.modules.ai.schemas import AiChatMessage
from app.modules.ai.service import AiChatService, OllamaEmptyResponse, OllamaUnavailable

_SYNTHETIC_API_KEY = 'sk-test-synthetic-DO-NOT-LEAK-98765'
_RAW_URL = 'http://127.0.0.1:8080/'


def _policy() -> EgressPolicy:
    return EgressPolicy(
        connect_timeout_seconds=1.0,
        read_timeout_seconds=1.0,
        max_request_bytes=65536,
        max_response_bytes=65536,
        allow_insecure_http=True,
    )


def _peer_policy() -> PeerPolicy:
    return PeerPolicy(allowed_hostnames=None, allowed_cidrs=('127.0.0.0/8',), allowed_ports=frozenset({8080}))


# ---------------------------------------------------------------------------
# probe_models / chat_completion (egress_transport's OpenAI-compatible response
# shape parsing), exercised through the send_json_request seam that _execute calls.
# ---------------------------------------------------------------------------


def _patch_send(monkeypatch: pytest.MonkeyPatch, fn) -> None:
    monkeypatch.setattr('app.modules.ai.egress_transport.send_json_request', fn)


def test_probe_models_ok_when_exact_model_id_present(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_send(monkeypatch, lambda *a, **k: (200, {'data': [{'id': 'llama-3'}, {'id': 'other-model'}]}))
    outcome = probe_models(
        _RAW_URL, model='llama-3', app_env='development', api_key=_SYNTHETIC_API_KEY, policy=_policy(), peer_policy=_peer_policy()
    )
    assert outcome.ok is True
    assert outcome.error_code is None
    assert outcome.status_code == 200


def test_probe_models_fails_when_model_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_send(monkeypatch, lambda *a, **k: (200, {'data': [{'id': 'other-model'}]}))
    outcome = probe_models(
        _RAW_URL, model='llama-3', app_env='development', api_key=_SYNTHETIC_API_KEY, policy=_policy(), peer_policy=_peer_policy()
    )
    assert outcome.ok is False
    assert outcome.error_code == EgressErrorCode.UPSTREAM_SHAPE_INVALID


def test_probe_models_fails_on_malformed_data_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_send(monkeypatch, lambda *a, **k: (200, {'data': 'not-a-list'}))
    outcome = probe_models(
        _RAW_URL, model='llama-3', app_env='development', api_key=_SYNTHETIC_API_KEY, policy=_policy(), peer_policy=_peer_policy()
    )
    assert outcome.ok is False
    assert outcome.error_code == EgressErrorCode.UPSTREAM_SHAPE_INVALID


def test_chat_completion_ok_parses_choices_message_content(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_send(monkeypatch, lambda *a, **k: (200, {'choices': [{'message': {'content': 'hello there'}}]}))
    outcome = chat_completion(
        _RAW_URL,
        model='llama-3',
        messages=[{'role': 'user', 'content': 'hi'}],
        app_env='development',
        api_key=_SYNTHETIC_API_KEY,
        policy=_policy(),
        peer_policy=_peer_policy(),
    )
    assert outcome.ok is True
    assert outcome.payload is not None
    assert outcome.payload['choices'][0]['message']['content'] == 'hello there'


def test_chat_completion_fails_on_missing_choices(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_send(monkeypatch, lambda *a, **k: (200, {'choices': []}))
    outcome = chat_completion(
        _RAW_URL,
        model='llama-3',
        messages=[{'role': 'user', 'content': 'hi'}],
        app_env='development',
        api_key=_SYNTHETIC_API_KEY,
        policy=_policy(),
        peer_policy=_peer_policy(),
    )
    assert outcome.ok is False
    assert outcome.error_code == EgressErrorCode.UPSTREAM_SHAPE_INVALID


def test_chat_completion_fails_when_message_content_is_not_a_string(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_send(monkeypatch, lambda *a, **k: (200, {'choices': [{'message': {'content': None}}]}))
    outcome = chat_completion(
        _RAW_URL,
        model='llama-3',
        messages=[{'role': 'user', 'content': 'hi'}],
        app_env='development',
        api_key=_SYNTHETIC_API_KEY,
        policy=_policy(),
        peer_policy=_peer_policy(),
    )
    assert outcome.ok is False
    assert outcome.error_code == EgressErrorCode.UPSTREAM_SHAPE_INVALID


@pytest.mark.parametrize(
    ('raised_code',),
    [
        (EgressErrorCode.HTTP_ERROR,),  # upstream 401/403/other 4xx -> uniform http-error taxonomy
        (EgressErrorCode.REDIRECT_REJECTED,),  # 3xx / policy-blocked upstream response
        (EgressErrorCode.CONNECT_FAILED,),  # connect timeout / unreachable
        (EgressErrorCode.TLS_VERIFICATION_FAILED,),  # TLS failure
        (EgressErrorCode.INVALID_JSON,),  # non-JSON body
        (EgressErrorCode.RESPONSE_TOO_LARGE,),  # oversize body
    ],
)
def test_chat_completion_propagates_send_seam_error_taxonomy(monkeypatch: pytest.MonkeyPatch, raised_code: EgressErrorCode) -> None:
    def fake_send(*a: Any, **k: Any):
        raise EgressError(raised_code)

    _patch_send(monkeypatch, fake_send)
    outcome = chat_completion(
        _RAW_URL,
        model='llama-3',
        messages=[{'role': 'user', 'content': 'hi'}],
        app_env='development',
        api_key=_SYNTHETIC_API_KEY,
        policy=_policy(),
        peer_policy=_peer_policy(),
    )
    assert outcome.ok is False
    assert outcome.error_code == raised_code
    assert outcome.status_code is None
    assert outcome.payload is None


def test_chat_completion_dns_failure_surfaces_as_dns_resolution_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    # End-to-end through resolve_pinned_peer (no send_json_request mocking) to prove
    # the adapter surfaces DNS-unreachable failures without ever touching the network.
    def fake_getaddrinfo(host: str, port: int, *, proto: int = 0) -> list[tuple]:
        raise OSError('simulated DNS failure')

    monkeypatch.setattr('app.modules.ai.egress_transport.socket.getaddrinfo', fake_getaddrinfo)
    outcome = chat_completion(
        'http://api.internal.example:8080/',
        model='llama-3',
        messages=[{'role': 'user', 'content': 'hi'}],
        app_env='development',
        api_key=_SYNTHETIC_API_KEY,
        policy=_policy(),
        peer_policy=_peer_policy(),
    )
    assert outcome.ok is False
    assert outcome.error_code == EgressErrorCode.DNS_RESOLUTION_FAILED


def test_no_api_key_leaks_into_outcomes_or_exception_strings(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_send(*a: Any, **k: Any):
        raise EgressError(EgressErrorCode.HTTP_ERROR)

    _patch_send(monkeypatch, fake_send)
    outcome = chat_completion(
        _RAW_URL,
        model='llama-3',
        messages=[{'role': 'user', 'content': 'hi'}],
        app_env='development',
        api_key=_SYNTHETIC_API_KEY,
        policy=_policy(),
        peer_policy=_peer_policy(),
    )
    assert _SYNTHETIC_API_KEY not in repr(outcome)
    assert _SYNTHETIC_API_KEY not in str(outcome)

    _patch_send(monkeypatch, lambda *a, **k: (200, {'data': [{'id': 'llama-3'}]}))
    ok_outcome = probe_models(
        _RAW_URL, model='llama-3', app_env='development', api_key=_SYNTHETIC_API_KEY, policy=_policy(), peer_policy=_peer_policy()
    )
    assert _SYNTHETIC_API_KEY not in repr(ok_outcome)
    assert _SYNTHETIC_API_KEY not in str(ok_outcome)


# ---------------------------------------------------------------------------
# AiChatService._compatible_chat / chat (the actual OpenAI-compatible adapter that
# service.py drives) — verifies the mapped OllamaUnavailable/OllamaEmptyResponse
# behavior and that failures never silently fall back to the Ollama provider.
# ---------------------------------------------------------------------------


class _FakeProviderConfigService:
    def __init__(self, binding: ActiveCompatibleBinding) -> None:
        self._binding = binding

    def get_state(self) -> SimpleNamespace:
        return SimpleNamespace(selected_kind='openai_compatible')

    def load_active_compatible_binding(self) -> ActiveCompatibleBinding:
        return self._binding


def _make_service(monkeypatch: pytest.MonkeyPatch, binding: ActiveCompatibleBinding) -> AiChatService:
    settings = Settings(app_env='development')
    service = AiChatService(settings=settings, provider_config_service=_FakeProviderConfigService(binding))

    def ollama_chat_should_not_be_called(*a: Any, **k: Any) -> str:
        raise AssertionError('OllamaClient.chat must not be invoked once openai_compatible is selected')

    monkeypatch.setattr(service.ollama, 'chat', ollama_chat_should_not_be_called)
    # NOTE: AiChatService._compatible_chat calls `self._messages_with_context(...)`, but
    # that method is only ever defined on OllamaClient (service.py:141), not on
    # AiChatService itself — this is a genuine pre-existing bug that makes the
    # openai_compatible chat path raise AttributeError unconditionally in the shipped
    # code (reproduced without this stub: AttributeError: 'AiChatService' object has no
    # attribute '_messages_with_context'). Fixing service.py is out of this test file's
    # scope, so this stub isolates the egress-outcome -> answer mapping behavior under
    # test from that unrelated, already-broken collaborator. Flagged as a blocker for
    # the parent/maintainers below.
    monkeypatch.setattr(
        AiChatService,
        '_messages_with_context',
        lambda self, messages, citations: messages,
        raising=False,
    )
    return service


def test_compatible_chat_returns_stripped_answer_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    binding = ActiveCompatibleBinding(canonical_url=_RAW_URL, model='llama-3', api_key=_SYNTHETIC_API_KEY.encode('utf-8'))
    service = _make_service(monkeypatch, binding)

    def fake_chat_completion(*a: Any, **k: Any) -> EgressOutcome:
        assert k['model'] == 'llama-3'
        return EgressOutcome(
            ok=True,
            error_code=None,
            status_code=200,
            latency_ms=5,
            payload={'choices': [{'message': {'content': '<think>reasoning</think>Final answer.'}}]},
        )

    monkeypatch.setattr(service_module, 'chat_completion', fake_chat_completion)
    answer = service.chat([AiChatMessage(role='user', content='hi')], roots=[], use_search=False, limit=5)[0]
    assert answer == 'Final answer.'


def test_compatible_chat_raises_empty_response_when_only_reasoning_returned(monkeypatch: pytest.MonkeyPatch) -> None:
    binding = ActiveCompatibleBinding(canonical_url=_RAW_URL, model='llama-3', api_key=_SYNTHETIC_API_KEY.encode('utf-8'))
    service = _make_service(monkeypatch, binding)

    def fake_chat_completion(*a: Any, **k: Any) -> EgressOutcome:
        return EgressOutcome(
            ok=True,
            error_code=None,
            status_code=200,
            latency_ms=5,
            payload={'choices': [{'message': {'content': '<think>only reasoning, no final answer</think>'}}]},
        )

    monkeypatch.setattr(service_module, 'chat_completion', fake_chat_completion)
    with pytest.raises(OllamaEmptyResponse):
        service.chat([AiChatMessage(role='user', content='hi')], roots=[], use_search=False, limit=5)


def test_compatible_chat_raises_unavailable_and_never_falls_back_to_ollama_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    binding = ActiveCompatibleBinding(canonical_url=_RAW_URL, model='llama-3', api_key=_SYNTHETIC_API_KEY.encode('utf-8'))
    service = _make_service(monkeypatch, binding)
    captured_models: list[str] = []

    def fake_chat_completion(*a: Any, **k: Any) -> EgressOutcome:
        captured_models.append(k['model'])
        return EgressOutcome(ok=False, error_code=EgressErrorCode.HTTP_ERROR, status_code=None, latency_ms=3, payload=None)

    monkeypatch.setattr(service_module, 'chat_completion', fake_chat_completion)
    with pytest.raises(OllamaUnavailable) as exc:
        service.chat([AiChatMessage(role='user', content='hi')], roots=[], use_search=False, limit=5)

    # Provider is never silently switched: the same bound model is always sent, the
    # error is surfaced to the caller (not swallowed), and ollama.chat (patched to
    # raise if invoked, see _make_service) was confirmed never called.
    assert captured_models == ['llama-3']
    assert _SYNTHETIC_API_KEY not in str(exc.value)
    assert 'http-error' in str(exc.value)

# ---------------------------------------------------------------------------
# Regression: the real compatible chat path must assemble messages via the
# provider-neutral OllamaClient helper. A prior bug called a non-existent
# AiChatService._messages_with_context and raised AttributeError for every
# compatible request. This test does NOT patch _messages_with_context.
# ---------------------------------------------------------------------------


class _BindingProvider:
    def load_active_compatible_binding(self) -> ActiveCompatibleBinding:
        return ActiveCompatibleBinding(
            canonical_url='http://127.0.0.1:8080/v1',
            model='gpt-test',
            api_key=_SYNTHETIC_API_KEY.encode('utf-8'),
        )


def test_compatible_chat_uses_real_ollama_message_context_and_returns_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(app_env='test')
    service = AiChatService(settings, db=None, provider_config_service=_BindingProvider())

    captured: dict[str, Any] = {}

    def fake_chat_completion(url: str, **kwargs: Any) -> EgressOutcome:
        captured['url'] = url
        captured['messages'] = kwargs.get('messages')
        captured['api_key'] = kwargs.get('api_key')
        return EgressOutcome(
            ok=True,
            error_code=None,
            status_code=200,
            latency_ms=1,
            payload={'choices': [{'message': {'content': '실제 경로 답변입니다.'}}]},
        )

    monkeypatch.setattr(service_module, 'chat_completion', fake_chat_completion)

    answer = service._compatible_chat([AiChatMessage(role='user', content='질문')], [])

    assert answer == '실제 경로 답변입니다.'
    # The provider-neutral system prompt from OllamaClient._messages_with_context must be present.
    assert captured['messages'][0]['role'] == 'system'
    assert 'AeroOne AI' in captured['messages'][0]['content']
    # The synthetic key is forwarded to the transport but never surfaced in the answer.
    assert _SYNTHETIC_API_KEY not in answer
