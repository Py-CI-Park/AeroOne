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
from dataclasses import dataclass, field
from datetime import datetime

from app.modules.aero_work.korean_datetime import parse_datetime


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
    r'(오전|오후|정오|일정|등록|잡아|예약|추가|해줘|해 줘|만들어|만들|생성|작성|써줘|써|'
    r'알려|보여|조회|목록|삭제|취소|그리고|그 내용으로|그내용으로|줘|해)'
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

    intents: list[Intent] = []
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
