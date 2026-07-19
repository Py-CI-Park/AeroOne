"""지식 근거 합성·문서 내용 생성의 SSE 스트리밍 제너레이터.

``orchestrator_service.default_synthesize`` / ``document_composer.compose_content`` 와 동일한
프롬프트 조립(``build_synthesis_messages`` / ``build_compose_messages``)·provider 계약
(AiChatService + ProviderConfigService, 로컬 강제 시 OllamaClient)을 그대로 재사용하되,
결과를 한 번에 반환하는 대신 ``('delta', 청크)`` 를 순서대로 방출한다.

라우트(``api.py``)는 이 제너레이터를 ``event: <kind>\\ndata: <json>\\n\\n`` SSE 프레임으로
직렬화한다. LLM 예외는 여기서 ``('error', 메시지)`` 로 안전하게 흡수한다 — SSE 헤더가 이미
전송된 뒤이므로 HTTP status 를 바꿀 수 없고, 예외를 그대로 전파하면 스트림이 깨진다.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Generator

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.aero_work.document_composer import build_compose_messages, parse_lines
from app.modules.aero_work.orchestrator_service import build_synthesis_messages
from app.modules.ai.provider_config_service import ProviderConfigService
from app.modules.ai.schemas import AiChatMessage
from app.modules.ai.service import AiChatService, OllamaClient, OllamaError

logger = logging.getLogger(__name__)

# 사용자에게 노출하는 error 프레임 문구 — 원문 예외 메시지(프로바이더 상세·연결 정보 등)를
# 그대로 클라이언트에 흘려보내지 않기 위해 고정 문구로 치환한다. 원문은 로그로만 남긴다.
_SAFE_ERROR_MESSAGE = 'AI 응답 생성에 실패했습니다. 잠시 후 다시 시도하세요.'

StreamEvent = tuple[str, object]
ChatStreamFn = Callable[[Settings, Session, list[AiChatMessage]], Generator[str, None, None]]


def _default_chat_stream(settings: Settings, db: Session, messages: list[AiChatMessage]) -> Generator[str, None, None]:
    """provider 선택(로컬 Ollama/OpenAI 호환) 을 따르는 기본 청크 소스.

    ``AiChatService.chat_stream`` 은 ``('citations'|'delta'|'final', 값)`` 프레임을 내므로
    가시 텍스트인 ``'delta'`` 만 순서대로 앞으로 흘려보낸다.
    """

    service = AiChatService(settings, db, ProviderConfigService(db, settings))
    for kind, value in service.chat_stream(messages, [], False, 0):
        if kind == 'delta':
            yield value


def _local_chat_stream(settings: Settings, db: Session, messages: list[AiChatMessage]) -> Generator[str, None, None]:
    yield from OllamaClient(settings).chat_stream(messages)


def _resolve_chat_stream(force_local: bool, chat_stream: ChatStreamFn | None) -> ChatStreamFn:
    if chat_stream is not None:
        return chat_stream
    return _local_chat_stream if force_local else _default_chat_stream


def _stream_chunks(
    settings: Settings,
    db: Session,
    messages: list[AiChatMessage],
    caller: ChatStreamFn,
) -> Generator[StreamEvent, None, str | None]:
    """``caller`` 가 내는 원문 청크를 ``('delta', 청크)`` 로 순서대로 방출하고, 완료 시
    이어붙인 전체 텍스트를 반환한다(``yield from`` 소비용). 실패 시 ``('error', 사용자-안전 문구)`` 를
    방출한 뒤 ``None`` 을 반환한다 — 원문 예외 메시지는 클라이언트로 보내지 않고 로그로만 남긴다."""

    collected: list[str] = []
    try:
        for chunk in caller(settings, db, messages):
            if not chunk:
                continue
            collected.append(chunk)
            yield ('delta', chunk)
    except OllamaError as exc:
        logger.warning('AI 스트림 chat_stream 실패(OllamaError): %s', exc)
        yield ('error', _SAFE_ERROR_MESSAGE)
        return None
    except Exception as exc:  # noqa: BLE001 — 스트림 중 예외는 전파 금지, error 프레임으로 종료
        logger.exception('AI 스트림 chat_stream 중 예상치 못한 예외')
        yield ('error', _SAFE_ERROR_MESSAGE)
        return None
    return ''.join(collected)


def stream_answer(
    settings: Settings,
    db: Session,
    query: str,
    hits: list[dict],
    *,
    force_local: bool = False,
    chat_stream: ChatStreamFn | None = None,
) -> Generator[StreamEvent, None, None]:
    """근거를 요약하며 ``('delta', 청크)`` 를 순서대로 방출하고, 완료 시
    ``('done', 전체답변)`` 을 방출한다. AI 비활성/근거 없음이면 즉시 ``('done', '')``."""

    if not settings.ai_features_enabled or not hits:
        yield ('done', '')
        return
    messages = build_synthesis_messages(query, hits)
    caller = _resolve_chat_stream(force_local, chat_stream)
    answer = yield from _stream_chunks(settings, db, messages, caller)
    if answer is None:
        return
    yield ('done', answer.strip())


def stream_compose(
    settings: Settings,
    db: Session,
    *,
    fmt: str,
    title: str,
    instruction: str,
    force_local: bool = False,
    chat_stream: ChatStreamFn | None = None,
) -> Generator[StreamEvent, None, None]:
    """지시를 개조식 문장으로 확장하며 ``('delta', 청크)`` 를 순서대로 방출하고, 완료 시
    ``('done', 문장리스트)`` 를 방출한다. 실패·빈 결과는 ``('error', 메시지)``."""

    instruction = (instruction or '').strip()
    if not settings.ai_features_enabled:
        yield ('error', 'AI 기능이 비활성화되어 있습니다.')
        return
    if not instruction:
        yield ('error', '지시(개요)를 입력해야 합니다.')
        return
    messages = build_compose_messages(fmt, title, instruction)
    caller = _resolve_chat_stream(force_local, chat_stream)
    answer = yield from _stream_chunks(settings, db, messages, caller)
    if answer is None:
        return
    lines = parse_lines(answer)
    if not lines:
        yield ('error', 'LLM 이 빈 내용을 반환했습니다. 지시를 더 구체적으로 적어 보세요.')
        return
    yield ('done', lines)
