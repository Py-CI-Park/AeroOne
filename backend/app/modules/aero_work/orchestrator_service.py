"""오케스트레이터 — 발화를 인텐트로 분해해 각 도메인 서비스로 실행한다.

gongmuwon 의 정체성인 '대화 한 줄 → 일정/문서/지식/도움말' 흐름의 백엔드. 일정은
ScheduleService, 지식 근거는 KnowledgeService 를 그대로 호출하고, 문서작성은 인텐트(양식·
제목·본문)를 인식해 프런트가 HWPX 생성으로 잇게 한다. 모든 실행은 실행기록에 남긴다.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.aero_work.activity_service import record_activity
from app.modules.aero_work.embedding_client import EmbeddingUnavailable, OllamaEmbedder
from app.modules.aero_work.intent_router import Intent, classify
from app.modules.aero_work.knowledge_service import KnowledgeService
from app.modules.aero_work.schedule_service import ScheduleService
from app.modules.aero_work.schemas import EventResponse
from app.modules.aero_work.version_ranker import mark_latest
from app.modules.ai.schemas import AiChatMessage
from app.modules.ai.provider_config_service import ProviderConfigService
from app.modules.ai.service import AiChatService, OllamaClient, OllamaError

_SYNTHESIS_CONTEXT_BUDGET = 8000
_SYNTHESIS_SYSTEM = (
    '너는 폐쇄망 업무 비서다. 아래 [근거]만 사용해 한국어로 간결히 답하고, 관련 문장 끝에 '
    '[근거 N] 으로 출처를 표기하라. 근거에 없는 내용은 지어내지 말고 "근거를 찾지 못했습니다"라고 답하라.'
)


def default_synthesize(settings: Settings, query: str, hits: list[dict], db: Session | None = None) -> str:
    """검색 근거를 LLM 으로 요약해 출처 표기가 붙은 답변을 만든다(실패 시 빈 문자열).

    AeroOne provider 시스템을 따른다: ``db`` 가 있으면 AiChatService + ProviderConfigService 로
    관리자가 선택한 provider(로컬 Ollama 또는 **OpenAI 호환 연결**)로 디스패치하고, 없을 때만
    env Ollama 로 폴백한다(AeroAI 채팅과 동일한 계약).
    """

    if not settings.ai_features_enabled or not hits:
        return ''
    parts: list[str] = []
    budget = _SYNTHESIS_CONTEXT_BUDGET
    for index, hit in enumerate(hits[:5], 1):
        piece = f'[근거 {index}] {hit.get("folder_name")}/{hit.get("rel_path")}\n{hit.get("content", "")}'
        if len(piece) > budget:
            piece = piece[:budget]
        parts.append(piece)
        budget -= len(piece)
        if budget <= 0:
            break
    messages = [
        AiChatMessage(role='system', content=_SYNTHESIS_SYSTEM),
        AiChatMessage(role='user', content=f'질문: {query}\n\n' + '\n\n'.join(parts)),
    ]
    try:
        if db is not None:
            service = AiChatService(settings, db, ProviderConfigService(db, settings))
            answer, _ = service.chat(messages, [], False, 0)
            return answer.strip()
        return OllamaClient(settings).chat(messages).strip()
    except OllamaError:
        return ''
    except Exception:  # noqa: BLE001 — 합성 실패는 답변 없이 근거만 제공(치명 아님)
        return ''


HELP_TEXTS = {
    '문서작성': '문서작성 탭에서 제목·본문을 적어 HWPX 로 내려받거나, 대화에서 "…보고서로 작성해줘"라고 말하면 됩니다.',
    '일정': '일정 탭에서 추가·수정·삭제하거나, 대화에서 "내일 오전 10시 회의 등록해줘"처럼 말하면 등록됩니다.',
    '내 지식폴더': '지식폴더 탭에서 폴더를 등록·색인하면, 대화에서 근거와 함께 검색할 수 있습니다.',
    '업무대화': '대화 한 줄로 일정 등록·문서작성·지식 검색을 이어서 할 수 있습니다.',
    '실행기록': '실행기록 탭에서 그동안 실행한 작업을 최신순으로 확인합니다.',
    '환경설정': '환경설정 탭에서 업무대화·지식폴더가 쓰는 로컬 AI 연결 상태를 확인합니다.',
}


def _format_when(value: datetime, has_time: bool) -> str:
    return value.strftime('%m월 %d일 %H:%M') if has_time else value.strftime('%m월 %d일')


class OrchestratorService:
    def __init__(
        self,
        db: Session,
        settings: Settings,
        user_id: int,
        *,
        embedder: OllamaEmbedder | None = None,
        synthesizer=None,
    ) -> None:
        self.db = db
        self.settings = settings
        self.user_id = user_id
        self.embedder = embedder if embedder is not None else OllamaEmbedder(settings)
        self.synthesizer = (
            synthesizer
            if synthesizer is not None
            else (lambda s, q, h: default_synthesize(s, q, h, db=db))
        )

    def run(self, utterance: str, *, now: datetime | None = None) -> list[dict]:
        now = now or datetime.now()
        return [self._execute(intent, now) for intent in classify(utterance, now)]

    def _execute(self, intent: Intent, now: datetime) -> dict:
        handler = {
            'schedule.create': self._schedule_create,
            'schedule.list': self._schedule_list,
            'schedule.delete': self._schedule_delete,
            'document': self._document,
            'help': self._help,
            'knowledge': self._knowledge,
        }.get(intent.kind, self._knowledge)
        return handler(intent, now)

    def _schedule_create(self, intent: Intent, now: datetime) -> dict:
        service = ScheduleService(self.db)
        event = service.create_event(
            self.user_id,
            title=intent.slots['title'],
            starts_at=intent.slots['starts_at'],
            ends_at=None,
            all_day=not intent.slots['has_time'],
            location='',
            notes='',
        )
        record_activity(self.db, self.user_id, 'schedule.create', f'일정 추가 "{event.title}"')
        when = _format_when(intent.slots['starts_at'], intent.slots['has_time'])
        return {
            'kind': 'schedule.create',
            'summary': f'일정을 등록했습니다: {event.title} ({when})',
            'events': [EventResponse.from_model(event)],
        }

    def _schedule_list(self, intent: Intent, now: datetime) -> dict:
        service = ScheduleService(self.db)
        events = service.list_events(self.user_id, start=now, end=now + timedelta(days=30))
        record_activity(self.db, self.user_id, 'schedule.list', f'일정 조회 — {len(events)}건')
        summary = f'다가오는 30일 일정 {len(events)}건입니다.' if events else '예정된 일정이 없습니다.'
        return {'kind': 'schedule.list', 'summary': summary, 'events': [EventResponse.from_model(e) for e in events]}

    def _schedule_delete(self, intent: Intent, now: datetime) -> dict:
        service = ScheduleService(self.db)
        title = (intent.slots.get('title') or '').strip()
        events = service.list_events(self.user_id)
        target = next((e for e in events if title and title in e.title), None)
        if target is None:
            return {'kind': 'schedule.delete', 'summary': f'"{title}" 일정을 찾지 못했습니다.', 'events': []}
        removed_title = target.title
        service.delete_event(self.user_id, target.id)
        record_activity(self.db, self.user_id, 'schedule.delete', f'일정 삭제 "{removed_title}"')
        return {'kind': 'schedule.delete', 'summary': f'일정을 삭제했습니다: {removed_title}', 'events': []}

    def _document(self, intent: Intent, now: datetime) -> dict:
        fmt = intent.slots['format']
        label = {'official': '시행문', 'full': '풀버전 보고서', 'onepage': '1페이지 보고서', 'email': '이메일'}.get(fmt, '문서')
        return {
            'kind': 'document',
            'summary': f'문서작성 의도로 인식했습니다({label}). 아래 [HWPX 생성]으로 내려받으세요.',
            'document': {'format': fmt, 'title': intent.slots['title'], 'content': intent.raw},
        }

    def _help(self, intent: Intent, now: datetime) -> dict:
        feature = intent.slots.get('feature', '업무대화')
        return {'kind': 'help', 'summary': HELP_TEXTS.get(feature, HELP_TEXTS['업무대화']), 'feature': feature}

    def _knowledge(self, intent: Intent, now: datetime) -> dict:
        query = intent.slots.get('query', intent.raw)
        service = KnowledgeService(self.db, self.embedder)
        try:
            hits = service.search(query, top_k=5)
        except EmbeddingUnavailable:
            return {
                'kind': 'knowledge',
                'summary': '지식 검색을 쓰려면 로컬 Ollama 임베딩 서버가 필요합니다.',
                'hits': [],
                'answer': '',
            }
        mark_latest(hits)
        record_activity(self.db, self.user_id, 'knowledge.search', f'지식 검색 "{query}" — {len(hits)}건')
        answer = ''
        if hits:
            try:
                answer = self.synthesizer(self.settings, query, hits)
            except Exception:  # noqa: BLE001 — 합성 실패는 근거만 제공
                answer = ''
        summary = (
            f'지식폴더에서 근거 {len(hits)}건을 찾았습니다.'
            if hits
            else '지식폴더에서 근거를 찾지 못했습니다. 폴더 등록·색인을 확인하세요.'
        )
        return {'kind': 'knowledge', 'summary': summary, 'hits': hits, 'answer': answer}
