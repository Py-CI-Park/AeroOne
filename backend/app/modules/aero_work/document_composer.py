"""문서 내용 생성 — 지시(instruction)를 LLM 으로 개조식 내용 문장으로 확장한다.

gongmuwon 문서작성의 "지시 → 구조 생성 → 검토"(사용설명서 §5.1) 중 구조·내용 생성 단계.
AeroOne provider 시스템(AiChatService + ProviderConfigService — 관리자 선택 Ollama/OpenAI 호환)
경유로 호출하며, ``chat`` 콜러블 주입으로 테스트는 실 LLM 없이 결정적으로 돈다.

생성 결과는 **내용 문장 리스트**(한 문장 = 한 줄)다. 양식 위계(□/◦, 1.·가. 등)는 다운로드
시점에 ``document_formats.format_document`` 가 입히므로 여기서는 입히지 않는다(이중 포맷 방지).
"""

from __future__ import annotations

import re
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.ai.provider_config_service import ProviderConfigService
from app.modules.ai.schemas import AiChatMessage
from app.modules.ai.service import AiChatService, OllamaClient, OllamaError

_FORMAT_GUIDE = {
    'onepage': '1페이지 보고서: 첫 줄은 두괄식 핵심 요약 1문장, 이어서 세부 항목 4~7문장.',
    'official': '시행문(공문): 본문 항목 3~6문장. 관련 근거·요청 사항·협조 기한 순.',
    'full': '풀버전 보고서: 장 제목이 될 문장 4~8개(추진 배경, 현황, 세부 계획, 기대 효과, 추진 일정 순).',
    'email': '업무 이메일 본문 3~6문장. 용건, 세부 내용, 요청/기한 순.',
    'freeform': '개조식 문장 4~8개.',
}

_SYSTEM = (
    '너는 공공기관 문서 작성 비서다. 사용자의 지시를 공공기관 개조식 문체(한 문장 한 줄, '
    '명사형 종결 "-함/-임/-됨")로 확장하라. 각 줄은 완결된 한 문장이며, 번호·기호·머리표 없이 '
    '순수 문장만 출력하라. 지시에 없는 사실을 지어내지 마라.'
)

_STRIP_PREFIX = re.compile(r'^\s*(?:[-*•◦□■]|\d+[.)]|[가-힣][.)]|[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ][.)]?)\s*')


class ComposeUnavailable(RuntimeError):
    """LLM 미가용 등으로 내용 생성 실패."""


def _default_chat(settings: Settings, db: Session, messages: list[AiChatMessage]) -> str:
    service = AiChatService(settings, db, ProviderConfigService(db, settings))
    answer, _ = service.chat(messages, [], False, 0)
    return answer


def _local_chat(settings: Settings, db: Session, messages: list[AiChatMessage]) -> str:
    return OllamaClient(settings).chat(messages)


def parse_lines(answer: str) -> list[str]:
    """LLM 응답을 문장 리스트로 정리한다(머리표·번호 제거, 빈 줄 삭제, 최대 12줄)."""

    lines = []
    for raw in (answer or '').splitlines():
        line = _STRIP_PREFIX.sub('', raw).strip()
        if line:
            lines.append(line)
    return lines[:12]


def build_compose_messages(
    fmt: str, title: str, instruction: str, previous_paragraphs: list[str] | None = None
) -> list[AiChatMessage]:
    """양식 지침을 포함한 내용 생성용 메시지를 조립한다.

    ``previous_paragraphs`` 가 주어지면(미리보기 '수정 지시' 재생성 루프) 이전 본문을 함께
    프롬프트에 넣고 ``instruction`` 을 최초 지시가 아닌 "수정 지시"로 취급한다 — 요청 계약은
    그대로(``instruction``/``previous_paragraphs`` 둘 다 optional), 프롬프트 조립만 갈린다.

    ``compose_content`` 와 스트리밍 경로(``streaming.stream_compose``)가 동일한 조립을
    공유한다(계약 동등성).
    """

    guide = _FORMAT_GUIDE.get(fmt, _FORMAT_GUIDE['freeform'])
    previous = [line.strip() for line in (previous_paragraphs or []) if (line or '').strip()]
    if previous:
        previous_block = '\n'.join(f'- {line}' for line in previous)
        user_content = (
            f'문서 제목: {title or "무제"}\n양식 지침: {guide}\n\n'
            f'이전 본문:\n{previous_block[:6000]}\n\n'
            f'수정 지시:\n{instruction[:2000]}\n\n'
            '위 수정 지시를 반영해 이전 본문 전체를 다시 써라(반영되지 않은 문장은 그대로 유지).'
        )
    else:
        user_content = f'문서 제목: {title or "무제"}\n양식 지침: {guide}\n\n지시:\n{instruction[:6000]}'
    return [
        AiChatMessage(role='system', content=_SYSTEM),
        AiChatMessage(role='user', content=user_content),
    ]


def compose_content(
    settings: Settings,
    db: Session,
    *,
    fmt: str,
    title: str,
    instruction: str,
    previous_paragraphs: list[str] | None = None,
    chat: Callable[[Settings, Session, list[AiChatMessage]], str] | None = None,
    force_local: bool = False,
) -> list[str]:
    """지시를 양식에 맞는 개조식 내용 문장으로 확장한다. 실패 시 ComposeUnavailable."""

    if not settings.ai_features_enabled:
        raise ComposeUnavailable('AI 기능이 비활성화되어 있습니다.')
    instruction = (instruction or '').strip()
    if not instruction:
        raise ComposeUnavailable('지시(개요)를 입력해야 합니다.')
    messages = build_compose_messages(fmt, title, instruction, previous_paragraphs)
    caller = chat if chat is not None else (_local_chat if force_local else _default_chat)
    try:
        answer = caller(settings, db, messages)
    except OllamaError as exc:
        raise ComposeUnavailable(f'LLM 호출 실패: {exc}') from exc
    except Exception as exc:  # noqa: BLE001 — provider 계열 오류 전부 사용자 안내로 변환
        raise ComposeUnavailable(f'내용 생성 실패: {exc}') from exc
    lines = parse_lines(answer)
    if not lines:
        raise ComposeUnavailable('LLM 이 빈 내용을 반환했습니다. 지시를 더 구체적으로 적어 보세요.')
    return lines
