"""한국어 자연어 날짜·시각 파서 단위 검증."""

from __future__ import annotations

from datetime import datetime

from app.modules.aero_work.korean_datetime import parse_datetime

NOW = datetime(2026, 7, 19, 15, 0)  # 2026-07-19(일) 15:00 기준


def test_tomorrow_morning() -> None:
    dt, has_time = parse_datetime('내일 오전 10시 회의', NOW)
    assert dt == datetime(2026, 7, 20, 10, 0)
    assert has_time is True


def test_afternoon_with_minutes() -> None:
    dt, has_time = parse_datetime('오늘 오후 2시 30분', NOW)
    assert dt == datetime(2026, 7, 19, 14, 30)
    assert has_time is True


def test_explicit_month_day_rolls_to_next_year_if_past() -> None:
    dt, _ = parse_datetime('3월 5일 오전 9시', NOW)  # 3/5 는 지났으니 내년
    assert dt == datetime(2027, 3, 5, 9, 0)


def test_noon() -> None:
    dt, has_time = parse_datetime('내일 정오', NOW)
    assert dt == datetime(2026, 7, 20, 12, 0)
    assert has_time is True


def test_date_without_time_defaults_and_flags_no_time() -> None:
    dt, has_time = parse_datetime('모레 워크숍', NOW)
    assert dt == datetime(2026, 7, 21, 9, 0)
    assert has_time is False


def test_no_date_returns_none() -> None:
    dt, has_time = parse_datetime('보고서 작성해줘', NOW)
    assert dt is None
    assert has_time is False


def test_days_after() -> None:
    dt, _ = parse_datetime('3일 후 오전 11시 점검', NOW)
    assert dt == datetime(2026, 7, 22, 11, 0)
