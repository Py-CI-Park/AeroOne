"""인텐트 분류 — gongmuwon 발화표 재현 단위 검증."""

from __future__ import annotations

from datetime import datetime

from app.modules.aero_work.intent_router import classify

NOW = datetime(2026, 7, 19, 15, 0)


def _kinds(utterance: str) -> list[str]:
    return [intent.kind for intent in classify(utterance, NOW)]


def test_schedule_create() -> None:
    intents = classify('내일 오전 10시 주간회의 일정 등록해줘', NOW)
    assert intents[0].kind == 'schedule.create'
    assert intents[0].slots['starts_at'] == datetime(2026, 7, 20, 10, 0)
    assert '주간회의' in intents[0].slots['title']


def test_schedule_list_and_delete() -> None:
    assert _kinds('이번 주 일정 알려줘') == ['schedule.list']
    assert _kinds('내일 주간회의 일정 삭제해줘') == ['schedule.delete']


def test_document_formats() -> None:
    assert classify('이 내용을 시행문으로 작성해줘', NOW)[0].slots['format'] == 'official'
    assert classify('회의 내용을 1페이지 보고서로 작성해줘', NOW)[0].slots['format'] == 'onepage'
    assert classify('풀버전 보고서로 만들어줘', NOW)[0].slots['format'] == 'full'
    assert classify('이메일로 작성해줘', NOW)[0].slots['format'] == 'email'


def test_help_and_knowledge() -> None:
    assert _kinds('문서작성 어떻게 하는지 알려줘') == ['help']
    assert _kinds('지식폴더에서 예산 편성 근거 찾아줘') == ['knowledge']


def test_multi_intent_create_and_document() -> None:
    intents = classify('내일 오후 2시 부서 워크숍 등록하고 그 내용으로 시행문 작성해줘', NOW)
    assert [intent.kind for intent in intents] == ['schedule.create', 'document']
    title = intents[0].slots['title']
    assert '워크숍' in title
    assert '시행문' not in title  # 문서 절이 일정 제목에 섞이면 안 됨(실사 발견 회귀)
    assert intents[1].slots['format'] == 'official'


def test_empty_utterance() -> None:
    assert classify('   ', NOW) == []
