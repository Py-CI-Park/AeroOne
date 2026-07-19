"""문서 내용 생성 — 파싱·주입 chat·실패 경로 단위 검증(실 LLM 없이 결정적)."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.aero_work.document_composer import ComposeUnavailable, compose_content, parse_lines


def _settings(**overrides) -> Settings:
    return Settings(app_env='test', jwt_secret_key='x', **overrides)


def test_parse_lines_strips_bullets_and_numbers() -> None:
    answer = '- 추진 배경을 정리함\n1. 세부 계획을 수립함\n□ 기대 효과가 큼\n\nⅠ. 일정을 확정함'
    assert parse_lines(answer) == ['추진 배경을 정리함', '세부 계획을 수립함', '기대 효과가 큼', '일정을 확정함']


def test_compose_uses_injected_chat_and_returns_lines() -> None:
    captured: dict = {}

    def fake_chat(settings, db, messages):
        captured['system'] = messages[0].content
        captured['user'] = messages[1].content
        return '에너지 절감 목표를 10%로 설정함\n조명 교체를 우선 추진함'

    lines = compose_content(
        _settings(), None, fmt='onepage', title='절감 방안', instruction='청사 에너지 절감', chat=fake_chat
    )
    assert lines == ['에너지 절감 목표를 10%로 설정함', '조명 교체를 우선 추진함']
    assert '개조식' in captured['system']
    assert '절감 방안' in captured['user'] and '청사 에너지 절감' in captured['user']


def test_compose_rejects_empty_instruction_and_empty_answer() -> None:
    with pytest.raises(ComposeUnavailable):
        compose_content(_settings(), None, fmt='onepage', title='t', instruction='   ', chat=lambda *a: 'x')
    with pytest.raises(ComposeUnavailable):
        compose_content(_settings(), None, fmt='onepage', title='t', instruction='지시', chat=lambda *a: '')


def test_compose_disabled_ai_raises() -> None:
    with pytest.raises(ComposeUnavailable):
        compose_content(
            _settings(ai_features_enabled=False), None, fmt='onepage', title='t', instruction='지시',
            chat=lambda *a: 'x',
        )


def test_compose_wraps_chat_failure() -> None:
    def boom(settings, db, messages):
        raise RuntimeError('down')

    with pytest.raises(ComposeUnavailable):
        compose_content(_settings(), None, fmt='onepage', title='t', instruction='지시', chat=boom)
