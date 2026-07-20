"""Ollama 임베딩 클라이언트 — AeroAI 와 동일한 표준 라이브러리(urllib) 경로.

폐쇄망 순도를 위해 외부 SaaS 없이 loopback Ollama ``/api/embeddings`` 만 호출한다. 모델은
``settings.ollama_embed_model``(기본 ``nomic-embed-text``, Open Notebook 용으로 이미 운영 중).
httpx/requests 의존을 새로 들이지 않고 AiChatService 와 같은 ``urllib.request`` 를 쓴다.
"""

from __future__ import annotations

import json
from urllib import error, request

from app.core.config import Settings
from sqlalchemy.orm import Session

from app.modules.ai import egress_transport
from app.modules.ai.provider_config_service import (
    ProviderConfigError,
    ProviderConfigService,
)


class EmbeddingUnavailable(RuntimeError):
    """Ollama 임베딩 엔드포인트 연결/응답 실패(폐쇄망에서 Ollama 미기동 등)."""


class OllamaEmbedder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base_url = settings.ollama_base_url.rstrip('/')
        self._model = settings.ollama_embed_model

    @property
    def model(self) -> str:
        return self._model

    @property
    def base_url(self) -> str:
        return self._base_url

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def embed_one(self, text: str) -> list[float]:
        return self._embed_one(text)

    def _embed_one(self, text: str) -> list[float]:
        body = json.dumps({'model': self._model, 'prompt': text}).encode('utf-8')
        req = request.Request(
            f'{self._base_url}/api/embeddings',
            data=body,
            method='POST',
            headers={'Content-Type': 'application/json'},
        )
        try:
            with request.urlopen(req, timeout=self._settings.ollama_read_timeout_seconds) as response:
                payload = json.loads(response.read().decode('utf-8'))
        except error.HTTPError as exc:
            raise EmbeddingUnavailable(
                f'Ollama 임베딩 HTTP {exc.code} (base_url={self._base_url}, model={self._model})'
            ) from exc
        except Exception as exc:  # noqa: BLE001 — 연결/타임아웃 등 전부 사용자용 메시지로 변환
            raise EmbeddingUnavailable(
                f'Ollama 임베딩 호출 실패: {exc} (base_url={self._base_url}, model={self._model})'
            ) from exc
        vector = payload.get('embedding') if isinstance(payload, dict) else None
        if not isinstance(vector, list) or not vector:
            raise EmbeddingUnavailable(
                f'Ollama 임베딩 응답에 embedding 벡터가 없습니다(model={self._model}).'
            )
        return [float(value) for value in vector]
class CompatibleEmbedder:
    """선택된 OpenAI 호환 제공자의 SSRF 핀닝 임베딩 어댑터."""

    def __init__(self, settings: Settings, db: Session) -> None:
        self._settings = settings
        self._provider_config_service = ProviderConfigService(db, settings)
        self._model = settings.ai_compatible_embed_model
        self._base_url = self._binding_base_url()

    @property
    def model(self) -> str:
        return self._model

    @property
    def base_url(self) -> str:
        return self._base_url

    def _binding_base_url(self) -> str:
        try:
            binding = self._provider_config_service.load_active_compatible_binding()
        except ProviderConfigError as exc:
            raise EmbeddingUnavailable(f'OpenAI 호환 임베딩 바인딩을 사용할 수 없습니다: {exc}') from exc
        finally:
            if 'binding' in locals():
                wiped = bytearray(binding.api_key)
                wiped[:] = b'\0' * len(wiped)
        return binding.canonical_url

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            binding = self._provider_config_service.load_active_compatible_binding()
        except ProviderConfigError as exc:
            raise EmbeddingUnavailable(f'OpenAI 호환 임베딩 바인딩을 사용할 수 없습니다: {exc}') from exc
        try:
            outcome = egress_transport.embeddings(
                binding.canonical_url,
                model=self._model,
                inputs=texts,
                app_env=self._settings.app_env,
                api_key=binding.api_key.decode('utf-8'),
                policy=self._settings.ai_compatible_egress_policy,
                peer_policy=self._settings.ai_compatible_peer_policy,
            )
        finally:
            wiped = bytearray(binding.api_key)
            wiped[:] = b'\0' * len(wiped)
        if not outcome.ok or outcome.payload is None:
            reason = outcome.error_code.value if outcome.error_code else 'unknown'
            raise EmbeddingUnavailable(
                f'OpenAI 호환 임베딩 호출 실패: {reason} (base_url={self._base_url}, model={self._model})'
            )
        data = outcome.payload['data']
        return [[float(value) for value in item['embedding']] for item in data]

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]


def build_embedder(settings: Settings, db: Session | None) -> OllamaEmbedder | CompatibleEmbedder:
    """관리자 선택이 OpenAI 호환일 때만 해당 임베더를 사용하고 기본 경로는 Ollama로 유지한다."""
    if db is None:
        return OllamaEmbedder(settings)
    provider_config_service = ProviderConfigService(db, settings)
    if provider_config_service.get_state().selected_kind == 'openai_compatible':
        return CompatibleEmbedder(settings, db)
    return OllamaEmbedder(settings)
