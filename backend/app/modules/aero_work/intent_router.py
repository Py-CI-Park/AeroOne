"""발화 → 인텐트 분류 (gongmuwon 발화표 재현, 규칙 기반).

한 발화를 하나 이상의 인텐트로 나눈다. gongmuwon 사용설명서 §4.7 발화표를 수용 기준으로:

  날짜·시각 + 등록/잡아/예약/추가  → schedule.create
  일정 + 삭제/취소                 → schedule.delete
  일정 + 알려/보여/조회/목록        → schedule.list
  보고서/시행문/공문/이메일 + 작성/생성/만들 → document (양식 자동 판별)
  사용법/어떻게 + 기능명            → help
  그 외(찾아줘/무엇)               → knowledge (근거 검색)

멀티 인텐트: "등록하고 … 작성해줘" 처럼 일정 등록 + 문서작성이 함께 오면 둘 다 낸다.
LLM 없이 결정적으로 동작해 회귀 고정이 쉽다(LLM 보조 라우팅은 후속).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.aero_work.korean_datetime import parse_datetime
from app.modules.ai.provider_config_service import ProviderConfigService
from app.modules.ai.schemas import AiChatMessage
from app.modules.ai.service import AiChatService


@dataclass
class Intent:
    kind: str
    raw: str
    slots: dict = field(default_factory=dict)


_DOC_FORMATS = (
    ('시행문', 'official'),
    ('공문', 'official'),
    ('풀버전', 'full'),
    ('상세 보고', 'full'),
    ('상세보고', 'full'),
    ('1페이지', 'onepage'),
    ('한 장', 'onepage'),
    ('한장', 'onepage'),
    ('이메일', 'email'),
    ('메일', 'email'),
)

_FEATURES = (
    ('문서작성', '문서작성'),
    ('문서', '문서작성'),
    ('일정', '일정'),
    ('지식폴더', '내 지식폴더'),
    ('지식', '내 지식폴더'),
    ('업무대화', '업무대화'),
    ('실행기록', '실행기록'),
    ('환경설정', '환경설정'),
)

_STRIP_TOKENS = re.compile(
    r'(오전|오후|정오|일정|할\s*일|등록|잡아|예약|추가|해줘|해 줘|만들어|만들|생성|작성|써줘|써|'
    r'알려|보여|조회|목록|삭제|취소|완료|했어|그리고|그 내용으로|그내용으로|줘|해)'
)


def detect_document_format(text: str) -> str:
    for keyword, fmt in _DOC_FORMATS:
        if keyword in text:
            return fmt
    return 'onepage'


def detect_feature(text: str) -> str:
    for keyword, name in _FEATURES:
        if keyword in text:
            return name
    return '업무대화'


def extract_title(text: str) -> str:
    cleaned = text
    for word in ('그저께', '그제', '어제', '오늘', '금일', '내일', '명일', '모레', '글피'):
        cleaned = cleaned.replace(word, ' ')
    cleaned = re.sub(r'\d{1,2}\s*월\s*\d{1,2}\s*일', ' ', cleaned)
    cleaned = re.sub(r'\d+\s*일\s*(뒤|후)', ' ', cleaned)
    cleaned = re.sub(r'\d{1,2}\s*시(\s*\d{1,2}\s*분)?', ' ', cleaned)
    cleaned = _STRIP_TOKENS.sub(' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip(' .,·')
    return cleaned


def _has(text: str, pattern: str) -> bool:
    return re.search(pattern, text) is not None


def classify(utterance: str, now: datetime) -> list[Intent]:
    text = (utterance or '').strip()
    if not text:
        return []

    started_at, has_time = parse_datetime(text, now)
    has_datetime = started_at is not None

    is_document = _has(text, r'보고서|시행문|공문|이메일|메일') and _has(text, r'작성|생성|만들|써')
    is_create = has_datetime and _has(text, r'등록|잡아|예약|추가')
    is_delete = '일정' in text and _has(text, r'삭제|취소')
    is_list = '일정' in text and _has(text, r'알려|보여|조회|목록')
    is_help = _has(text, r'사용법|어떻게\s*(하|쓰|해|사용)|사용\s*방법')

    is_task = '할 일' in text
    is_task_create = is_task and _has(text, r'추가|등록')
    is_task_list = is_task and _has(text, r'목록|알려|보여')
    is_task_done = is_task and _has(text, r'완료|했어')
    intents: list[Intent] = []
    if is_task_create:
        return [Intent('task.create', text, {'title': extract_title(text) or '새 할 일'})]
    if is_task_list:
        return [Intent('task.list', text, {})]
    if is_task_done:
        return [Intent('task.done', text, {'title': extract_title(text)})]
    if is_create:
        # 멀티인텐트("…등록하고 …작성해줘")면 일정 제목은 연결어 앞 절에서만 뽑는다 —
        # 문서 절(시행문/보고서…)이 일정 제목에 섞이는 것을 막는다(실사 발견 결함).
        schedule_text = re.split(r'하고|그리고|그\s*내용', text)[0] if is_document else text
        intents.append(
            Intent(
                'schedule.create',
                text,
                {'starts_at': started_at, 'has_time': has_time, 'title': extract_title(schedule_text) or '새 일정'},
            )
        )
    if is_document:
        intents.append(
            Intent(
                'document',
                text,
                {'format': detect_document_format(text), 'title': extract_title(text) or '무제'},
            )
        )
    if intents:
        # schedule.create + document 가 함께면 멀티 인텐트로 둘 다 반환.
        return intents

    if is_delete:
        return [Intent('schedule.delete', text, {'title': extract_title(text)})]
    if is_list:
        return [Intent('schedule.list', text, {})]
    if is_help:
        return [Intent('help', text, {'feature': detect_feature(text)})]
    return [Intent('knowledge', text, {'query': text})]


# ---- LLM 보조 2차 분류(폴백 전용) ----
#
# classify() 는 규칙만으로 결정적으로 동작한다(회귀 고정 — 발화표 테스트 불변). 규칙이 아무
# 패턴도 못 찾아 최종적으로 knowledge 로 폴백한 "비확정" 케이스에 한해, 오케스트레이터가
# 이 함수로 2차 LLM 분류를 시도한다. 규칙이 이미 확정한 결과(schedule.create/list/delete,
# document, help)는 이 함수를 절대 거치지 않는다 — 규칙 확정 결과를 LLM 이 뒤집는 일은 없다.

_LLM_CLASSIFY_CATEGORIES: tuple[str, ...] = ('schedule', 'document', 'knowledge', 'help')

_LLM_CLASSIFY_SYSTEM = (
    '너는 업무대화 인텐트 분류기다. 사용자 발화 하나를 다음 네 범주 중 정확히 하나로 분류해 '
    '그 단어 하나만 출력하라(설명·문장부호·다른 말 금지): schedule, document, knowledge, help.\n'
    '- schedule: 일정 등록/조회/삭제 요청\n'
    '- document: 보고서·시행문·공문·이메일 등 문서 작성 요청\n'
    '- help: 기능 사용법 안내 요청\n'
    '- knowledge: 그 외 정보·근거 검색 요청'
)


def _default_llm_chat(settings: Settings, db: Session, messages: list[AiChatMessage]) -> str:
    service = AiChatService(settings, db, ProviderConfigService(db, settings))
    answer, _ = service.chat(messages, [], False, 0)
    return answer


def classify_with_llm(
    settings: Settings,
    db: Session,
    utterance: str,
    chat: Callable[[Settings, Session, list[AiChatMessage]], str] | None = None,
) -> str:
    """규칙이 knowledge 로 폴백했을 때만 호출되는 2차 LLM 분류.

    ``schedule``/``document``/``knowledge``/``help`` 중 정확히 하나를 반환한다. AI 기능
    비활성화·빈 발화·LLM 호출 실패·응답 파싱 실패(네 범주 중 어느 것도 포함하지 않음) 시에는
    안전하게 ``knowledge`` 를 유지한다(호출부는 이미 knowledge 로 확정된 폴백 상태이므로,
    이 함수가 실패해도 결과가 나빠지지 않는다 — 순수 보강).
    """

    if not settings.ai_features_enabled:
        return 'knowledge'
    text = (utterance or '').strip()
    if not text:
        return 'knowledge'
    messages = [
        AiChatMessage(role='system', content=_LLM_CLASSIFY_SYSTEM),
        AiChatMessage(role='user', content=f'발화: {text}'),
    ]
    caller = chat if chat is not None else _default_llm_chat
    try:
        answer = caller(settings, db, messages)
    except Exception:  # noqa: BLE001 — 분류 실패는 knowledge 유지(치명 아님).
        return 'knowledge'
    token = re.sub(r'[^a-z]', '', (answer or '').strip().lower())
    for category in _LLM_CLASSIFY_CATEGORIES:
        if category in token:
            return category
    return 'knowledge'
