"""오케스트레이터 — 발화를 인텐트로 분해해 각 도메인 서비스로 실행한다.

gongmuwon 의 정체성인 '대화 한 줄 → 일정/문서/지식/도움말' 흐름의 백엔드. 일정은
ScheduleService, 지식 근거는 KnowledgeService 를 그대로 호출하고, 문서작성은 인텐트(양식·
제목·본문)를 인식해 프런트가 HWPX 생성으로 잇게 한다. 모든 실행은 실행기록에 남긴다.
"""

from __future__ import annotations

import re

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.aero_work.activity_service import record_activity
from app.modules.aero_work.attachments import AeroWorkAttachment, build_attachment_block
from app.modules.aero_work.embedding_client import EmbeddingUnavailable, OllamaEmbedder
from app.modules.aero_work.intent_router import (
    Intent,
    classify,
    classify_with_llm,
    detect_document_format,
    detect_feature,
    extract_title,
)

from app.modules.aero_work.knowledge_service import KnowledgeService
from app.modules.aero_work.schedule_service import ScheduleService
from app.modules.aero_work.prefs_service import get_llm_mode
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
# M1: 규칙이 knowledge 로 폴백한 뒤 2차 LLM 분류가 개입하는 케이스 중, 발화 자체가 명시적인
# 검색 동사(찾아줘/알려줘/검색)를 담고 있으면 정상적인 지식 검색 요청일 가능성이 매우 높다.
# 이런 발화에서 LLM 2차 분류가 document/help/schedule 로 오분류하면 정상 knowledge 검색이
# 통째로 대체돼 버리는 회귀가 생긴다 — 검색 동사가 있는 발화는 LLM 결과와 무관하게 knowledge
# 라우팅을 유지한다(회귀 가드). 그 외(검색 동사 없는 애매한 발화)는 기존처럼 LLM 결과를 따른다.
_KNOWLEDGE_GUARD_PATTERN = re.compile(r'찾아줘|알려줘|검색')


def build_synthesis_messages(query: str, hits: list[dict]) -> list[AiChatMessage]:
    """근거 조각을 ``[근거 N]`` 표기로 조립해 합성용 메시지를 만든다.

    ``default_synthesize`` 와 스트리밍 경로(``streaming.stream_answer``)가 동일한 조립을
    공유한다(계약 동등성 — 스트리밍/비스트리밍이 같은 근거 표기를 낸다).
    """

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
    return [
        AiChatMessage(role='system', content=_SYNTHESIS_SYSTEM),
        AiChatMessage(role='user', content=f'질문: {query}\n\n' + '\n\n'.join(parts)),
    ]


def default_synthesize(
    settings: Settings, query: str, hits: list[dict], db: Session | None = None, force_local: bool = False
) -> str:
    """검색 근거를 LLM 으로 요약해 출처 표기가 붙은 답변을 만든다(실패 시 빈 문자열).

    AeroOne provider 시스템을 따른다: ``db`` 가 있으면 AiChatService + ProviderConfigService 로
    관리자가 선택한 provider(로컬 Ollama 또는 **OpenAI 호환 연결**)로 디스패치하고, 없을 때만
    env Ollama 로 폴백한다(AeroAI 채팅과 동일한 계약).
    """

    if not settings.ai_features_enabled or not hits:
        return ''
    messages = build_synthesis_messages(query, hits)
    try:
        if db is not None and not force_local:
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


def _llm_category_to_intent(category: str, text: str, now: datetime) -> Intent:
    """2차 LLM 분류(schedule/document/knowledge/help) 결과를 실행 가능한 Intent 로 옮긴다.

    LLM 은 범주 하나만 돌려주고 슬롯(양식·기능명)은 없다 — classify() 의 개별 감지기
    (extract_title/detect_document_format/detect_feature)를 그대로 재사용해 항상 안전한
    기본값으로 슬롯을 채운다. schedule 범주는 무조건 schedule.list 로 강등한다(B5) —
    이 함수는 규칙이 최종적으로 knowledge 로 폴백한 "생성 동사가 없는" 발화에서만 호출되므로
    (규칙이 확정한 schedule.create 는 여기를 절대 거치지 않는다 — classify() 의 is_create 가
    이미 날짜·시각과 등록/잡아/예약/추가 동사를 함께 요구한다), LLM 레인 발화는 구조적으로
    생성 동사가 없다. 날짜만 있고 생성 동사가 없는 발화에서 일정을 지어내지 않기 위해 항상
    안전하게 조회로 강등한다(일정 삭제 등 파괴적 인텐트로 확대되는 일도 없다).
    """

    if category == 'document':
        return Intent(
            'document', text, {'format': detect_document_format(text), 'title': extract_title(text) or '무제'}
        )
    if category == 'schedule':
        return Intent('schedule.list', text, {})
    if category == 'help':
        return Intent('help', text, {'feature': detect_feature(text)})
    return Intent('knowledge', text, {'query': text})


class OrchestratorService:
    def __init__(
        self,
        db: Session,
        settings: Settings,
        user_id: int,
        *,
        embedder: OllamaEmbedder | None = None,
        synthesizer=None,
        llm_classify=None,
    ) -> None:
        self.db = db
        self.settings = settings
        self.user_id = user_id
        self.embedder = embedder if embedder is not None else OllamaEmbedder(settings)
        self.synthesizer = (
            synthesizer
            if synthesizer is not None
            else (lambda s, q, h: default_synthesize(s, q, h, db=db, force_local=get_llm_mode(db, user_id) == 'local'))
        )
        # G006: 규칙이 knowledge 로 폴백했을 때만 쓰는 2차 LLM 분류(주입 가능 — 테스트는 실
        # LLM 없이 결정적으로 돈다). 첨부 블록은 run() 호출마다 새로 조립해 인스턴스에 담는다.
        self.llm_classify = llm_classify if llm_classify is not None else (lambda u: classify_with_llm(settings, db, u))
        self.attachment_block = ''
        # B4: 첨부 블록이 안전 상한(ATTACHMENT_BLOCK_MAX_CHARS)에서 잘렸는지 — 답변 말미 안내용.
        self.attachment_truncated = False

    def run(
        self, utterance: str, *, now: datetime | None = None, attachments: list[AeroWorkAttachment] | None = None
    ) -> list[dict]:
        now = now or datetime.now()
        self.attachment_block, self.attachment_truncated = build_attachment_block(attachments or [])
        intents = classify(utterance, now)
        routed_by = 'rule'
        # 규칙이 knowledge 로 폴백한 "비확정" 케이스(단일 knowledge 인텐트)에 한해서만 2차 LLM
        # 분류를 시도한다 — 규칙이 확정한 결과(schedule.create/list/delete·document·help, 혹은
        # 멀티 인텐트)는 여기서 절대 LLM 을 호출하지 않는다(회귀 고정 발화표 불변 보장).
        if len(intents) == 1 and intents[0].kind == 'knowledge':
            category = self.llm_classify(utterance)
            # M1: 검색 동사가 명시된 발화는 LLM 오분류로부터 knowledge 라우팅을 지킨다.
            if category != 'knowledge' and _KNOWLEDGE_GUARD_PATTERN.search(utterance or ''):
                category = 'knowledge'
            # L1: LLM 이 실제로 결과를 바꿨을 때만(호출 실패/비활성·파싱 실패로 knowledge 를
            # 그대로 유지한 경우 포함) routed_by 를 'llm' 로 표시한다 — 개입이 없었다면 'rule'.
            if category != 'knowledge':
                routed_by = 'llm'
                intents = [_llm_category_to_intent(category, (utterance or '').strip(), now)]
        results = []
        for intent in intents:
            result = self._execute(intent, now)
            result['routed_by'] = routed_by
            results.append(result)
        return results

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
        matches = [e for e in events if title in e.title] if title else []
        if not matches:
            return {'kind': 'schedule.delete', 'summary': f'"{title}" 일정을 찾지 못했습니다.', 'events': []}
        if len(matches) > 1:
            # AW-R03: 제목 부분일치가 여러 건이면 즉시 삭제하지 않고 후보를 돌려 선택을 요청한다.
            # (같은 제목 반복 회의·넓은 검색어에서 다른 일정이 지워지는 오삭제를 막는다.)
            record_activity(self.db, self.user_id, 'schedule.delete', f'삭제 후보 {len(matches)}건 — 확인 요청 "{title}"')
            return {
                'kind': 'schedule.delete',
                'summary': f'"{title}"에 해당하는 일정이 {len(matches)}건입니다. 삭제할 일정을 날짜·시각까지 넣어 더 구체적으로 말해 주세요.',
                'events': [EventResponse.from_model(e) for e in matches],
            }
        target = matches[0]
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
        service = KnowledgeService(self.db, self.embedder, self.user_id)
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
            # G006: 첨부 텍스트가 있으면 합성 질의에 방어 블록으로 덧붙인다 — synthesizer 시그니처
            # (settings, query, hits)는 그대로 두어 기존 주입 테스트와 호환한다.
            synthesis_query = query
            if self.attachment_block:
                synthesis_query = f'{query}\n\n{self.attachment_block}'
            try:
                answer = self.synthesizer(self.settings, synthesis_query, hits)
            except Exception:  # noqa: BLE001 — 합성 실패는 근거만 제공
                answer = ''
            # B4: 첨부가 안전 상한에서 잘렸으면 무증상 소실 대신 답변 말미에 안내를 남긴다.
            if answer and self.attachment_truncated:
                answer = f'{answer}\n\n(안내: 첨부 문서가 길어 일부 내용만 반영되었습니다.)'
        summary = (
            f'지식폴더에서 근거 {len(hits)}건을 찾았습니다.'
            if hits
            else '지식폴더에서 근거를 찾지 못했습니다. 폴더 등록·색인을 확인하세요.'
        )
        return {'kind': 'knowledge', 'summary': summary, 'hits': hits, 'answer': answer}
