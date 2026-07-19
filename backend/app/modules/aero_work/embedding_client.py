"""Ollama 임베딩 클라이언트 — AeroAI 와 동일한 표준 라이브러리(urllib) 경로.

폐쇄망 순도를 위해 외부 SaaS 없이 loopback Ollama ``/api/embeddings`` 만 호출한다. 모델은
``settings.ollama_embed_model``(기본 ``nomic-embed-text``, Open Notebook 용으로 이미 운영 중).
httpx/requests 의존을 새로 들이지 않고 AiChatService 와 같은 ``urllib.request`` 를 쓴다.
"""

from __future__ import annotations

import json
from urllib import error, request

from app.core.config import Settings


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
