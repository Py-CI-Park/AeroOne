"""OpenAI 호환 엔드포인트 클라이언트 — MVP ``llm_client.py`` 로직을 stdlib ``urllib`` 로 포팅.

기존 ``OllamaClient`` 와 동일한 transport(``urllib.request`` + ``json``)를 써서 신규
의존성(httpx)을 도입하지 않는다. reasoning/chain-of-thought 필드는 절대 노출하지 않고
``choices[0].message.content`` 만 반환한다. ``verify_tls=False`` 인 경우에만 미검증 SSL
컨텍스트를 사용한다(폐쇄망 사설 인증서 대응).
"""

from __future__ import annotations

import json
import ssl
from typing import Any
from urllib import error, request

from app.core.config import Settings


class LlmConnectionError(RuntimeError):
    """연결 다운/HTTP 오류/빈 응답 등 호출 실패."""


class LlmConfigError(RuntimeError):
    """연결이 설정되지 않음(모델 미지정 등)."""


class OpenAiCompatibleClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str | None,
        verify_tls: bool,
        settings: Settings,
    ) -> None:
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key or ''
        self.model = model
        self.verify_tls = verify_tls
        self.settings = settings

    def _endpoint(self, path: str) -> str:
        # base 가 /v1 로 끝나고 path 가 /v1/ 로 시작하면 중복 세그먼트를 제거한다
        # (MVP llm_client._endpoint 와 동일 규칙).
        base = self.base_url
        if not path.startswith('/'):
            path = '/' + path
        if base.endswith('/v1') and path.startswith('/v1/'):
            path = path[3:]
        return base + path

    def _ssl_context(self) -> ssl.SSLContext | None:
        if self.verify_tls:
            return None
        return ssl._create_unverified_context()

    def _headers(self) -> dict[str, str]:
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        return headers

    def _request(self, method: str, path: str, body: dict[str, Any] | None, timeout: float) -> Any:
        data = json.dumps(body).encode('utf-8') if body is not None else None
        req = request.Request(self._endpoint(path), data=data, method=method, headers=self._headers())
        try:
            with request.urlopen(req, timeout=timeout, context=self._ssl_context()) as response:
                return json.loads(response.read().decode('utf-8'))
        except error.HTTPError as exc:
            raise LlmConnectionError(f'LLM HTTP error {exc.code} (base_url={self.base_url})') from exc
        except Exception as exc:
            raise LlmConnectionError(f'{exc} (reason=request_failed, base_url={self.base_url})') from exc

    def list_models(self) -> list[str]:
        """``GET {base}/models`` 응답의 ``data[].id`` 를 파싱해 모델명 목록을 반환한다."""

        payload = self._request('GET', '/models', None, timeout=self.settings.ollama_connect_timeout_seconds)
        data = payload.get('data') if isinstance(payload, dict) else None
        models: list[str] = []
        for item in data or []:
            model_id = item.get('id') if isinstance(item, dict) else None
            if isinstance(model_id, str) and model_id:
                models.append(model_id)
        return models

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.2, max_tokens: int = 1200) -> str:
        """``POST {base}/chat/completions`` 호출. 최종 content 문자열만 반환(추론 필드 비노출)."""

        if not self.model:
            raise LlmConfigError('model is not configured for this connection')
        payload: dict[str, Any] = {
            'model': self.model,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens,
            'stream': False,
        }
        body = self._request('POST', '/chat/completions', payload, timeout=self.settings.ollama_read_timeout_seconds)
        choices = body.get('choices') if isinstance(body, dict) else None
        if not choices:
            raise LlmConnectionError('LLM response has no choices')
        message = choices[0].get('message') if isinstance(choices[0], dict) else None
        content = message.get('content') if isinstance(message, dict) else None
        if isinstance(content, list):
            content = ''.join(
                str(part.get('text', '')) if isinstance(part, dict) else str(part)
                for part in content
            )
        if not isinstance(content, str) or not content.strip():
            raise LlmConnectionError('LLM response content is empty')
        return content.strip()
