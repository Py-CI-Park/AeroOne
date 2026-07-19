"""한국어 자연어 날짜·시각 파싱 — '내일 오전 10시', '3월 5일 오후 2시 30분' 등.

규칙 기반(외부 의존 0, 폐쇄망 적합). 상대일(오늘/내일/모레/글피/N일 후) + 명시일(N월 N일) +
시각(오전/오후 N시 M분, 정오)을 인식한다. 날짜/시각 근거가 없으면 (None, False) 를 돌려준다.
오케스트레이터의 일정 등록 인텐트가 이 파서로 슬롯을 채운다.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

_RELATIVE_DAYS = {
    '그저께': -2,
    '그제': -2,
    '어제': -1,
    '오늘': 0,
    '금일': 0,
    '내일': 1,
    '명일': 1,
    '모레': 2,
    '글피': 3,
}

_DEFAULT_HOUR = 9


def parse_datetime(text: str, now: datetime) -> tuple[datetime | None, bool]:
    """``text`` 에서 시작 시각을 추출한다.

    반환: ``(datetime | None, has_time)``. 날짜 근거(상대일·명시일)나 시각(N시)이 하나도
    없으면 ``(None, False)``. 시각이 없고 날짜만 있으면 기본 09:00 + ``has_time=False``.
    """

    base_date = None

    for word, offset in _RELATIVE_DAYS.items():
        if word in text:
            base_date = (now + timedelta(days=offset)).date()
            break

    days_after = re.search(r'(\d+)\s*일\s*(뒤|후)', text)
    if days_after:
        base_date = (now + timedelta(days=int(days_after.group(1)))).date()

    explicit = re.search(r'(\d{1,2})\s*월\s*(\d{1,2})\s*일', text)
    if explicit:
        month, day = int(explicit.group(1)), int(explicit.group(2))
        try:
            candidate = datetime(now.year, month, day).date()
            if candidate < now.date():
                candidate = datetime(now.year + 1, month, day).date()
            base_date = candidate
        except ValueError:
            pass

    time_match = re.search(r'(\d{1,2})\s*시\s*(?:(\d{1,2})\s*분)?', text)
    has_noon = '정오' in text

    if base_date is None:
        # 날짜 표현이 없어도 시각이 있으면 오늘 기준으로 본다.
        if time_match or has_noon:
            base_date = now.date()
        else:
            return None, False

    hour: int | None = None
    minute = 0
    if time_match:
        hour = int(time_match.group(1))
        if time_match.group(2):
            minute = int(time_match.group(2))
        if '오후' in text and hour < 12:
            hour += 12
        if '오전' in text and hour == 12:
            hour = 0
    elif has_noon:
        hour = 12

    has_time = hour is not None
    if hour is None:
        hour = _DEFAULT_HOUR
    hour = max(0, min(hour, 23))
    minute = max(0, min(minute, 59))

    result = datetime(base_date.year, base_date.month, base_date.day, hour, minute)
    return result, has_time
