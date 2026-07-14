"""LLM 연결 브리지 — 산출물 A(LLM 연결 레지스트리)의 활성 연결을 office-tools 로 연결한다.

각 도구의 AI 보조(``ai_mode``/``ai_assist``)는 이 브리지로 활성 연결을 얻어
``OpenAiCompatibleClient`` 로 호출한다. 활성 연결이 없으면 ``None`` 을 돌려주고,
호출부(각 도구 서비스)는 규칙 기반 폴백으로 내려간다(“LLM 미설정/실패로 규칙 기반 사용”).

이 브리지는 base_url/api_key 를 절대 외부로 노출하지 않는다. ``describe_capabilities``
는 활성 여부와 모델명(비밀 아님)만 반환한다.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.ai.llm_connection_service import LlmConnectionService
from app.modules.ai.openai_client import OpenAiCompatibleClient


def resolve_active_client(db: Session, settings: Settings) -> OpenAiCompatibleClient | None:
    """활성 LLM 연결이 있으면 OpenAI 호환 클라이언트를, 없으면 None 을 반환한다."""

    service = LlmConnectionService(db, settings)
    connection = service.get_active()
    if connection is None:
        return None
    return service.client_for(connection)


def describe_capabilities(db: Session, settings: Settings) -> dict[str, object]:
    """LLM 능력 요약(base_url 미노출). 활성 여부 + 모델명 + 폴백 전략만 노출한다."""

    connection = LlmConnectionService(db, settings).get_active()
    return {
        'active': connection is not None,
        'default_model': connection.default_model if connection is not None else None,
        'fallback': 'rule-based',
    }
