"""지식 문서 요약 — 색인된 파일의 청크를 LLM 으로 2~3문장 요약해 문서 카드에 싣는다.

gongmuwon 위키 '문서 카드'(§6.5 요약·키워드)의 요약 부분. provider 시스템(AiChatService)과
사용자 LLM 프로필(local 강제)을 따르며, ``chat`` 주입으로 테스트는 실 LLM 없이 결정적으로 돈다.
요약은 KnowledgeFile.summary 에 저장해 재계산을 피한다.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.aero_work.models import KnowledgeChunk, KnowledgeFile, KnowledgeFolder
from app.modules.ai.provider_config_service import ProviderConfigService
from app.modules.ai.schemas import AiChatMessage
from app.modules.ai.service import AiChatService, OllamaClient, OllamaError

_SYSTEM = (
    '너는 문서 사서다. 아래 발췌만 근거로 이 문서가 무엇인지 한국어 2~3문장으로 요약하라. '
    '개조식(-함/-임 종결)으로, 발췌에 없는 내용은 지어내지 마라.'
)
_CONTEXT_CHARS = 6000


class SummaryUnavailable(RuntimeError):
    """LLM 미가용/빈 응답 등으로 요약 실패."""


def _provider_chat(settings: Settings, db: Session, messages: list[AiChatMessage]) -> str:
    service = AiChatService(settings, db, ProviderConfigService(db, settings))
    answer, _ = service.chat(messages, [], False, 0)
    return answer


def _local_chat(settings: Settings, db: Session, messages: list[AiChatMessage]) -> str:
    return OllamaClient(settings).chat(messages)


def summarize_file(
    settings: Settings,
    db: Session,
    file_id: int,
    *,
    owner_id: int | None = None,
    force_local: bool = False,
    chat: Callable[[Settings, Session, list[AiChatMessage]], str] | None = None,
) -> str:
    """파일 청크 앞부분을 요약해 저장·반환한다. 실패 시 SummaryUnavailable."""
    if not settings.ai_features_enabled:
        raise SummaryUnavailable('AI 기능이 비활성화되어 있습니다.')
    file_row = db.execute(
        select(KnowledgeFile)
        .join(KnowledgeFolder, KnowledgeFile.folder_id == KnowledgeFolder.id)
        .where(KnowledgeFile.id == file_id, KnowledgeFolder.owner_id == owner_id)
    ).scalar_one_or_none()
    if file_row is None:
        raise SummaryUnavailable('파일을 찾을 수 없습니다.')
    chunks = (
        db.execute(
            select(KnowledgeChunk.content)
            .where(KnowledgeChunk.file_id == file_id)
            .order_by(KnowledgeChunk.chunk_index)
            .limit(3)
        )
        .scalars()
        .all()
    )
    excerpt = '\n'.join(chunks)[:_CONTEXT_CHARS]
    if not excerpt.strip():
        raise SummaryUnavailable('요약할 본문이 없습니다(색인을 확인하세요).')
    messages = [
        AiChatMessage(role='system', content=_SYSTEM),
        AiChatMessage(role='user', content=f'파일명: {file_row.rel_path}\n\n발췌:\n{excerpt}'),
    ]
    caller = chat if chat is not None else (_local_chat if force_local else _provider_chat)
    try:
        answer = (caller(settings, db, messages) or '').strip()
    except OllamaError as exc:
        raise SummaryUnavailable(f'LLM 호출 실패: {exc}') from exc
    except Exception as exc:  # noqa: BLE001
        raise SummaryUnavailable(f'요약 실패: {exc}') from exc
    if not answer:
        raise SummaryUnavailable('LLM 이 빈 요약을 반환했습니다.')
    file_row.summary = answer[:1000]
    db.flush()
    return file_row.summary
