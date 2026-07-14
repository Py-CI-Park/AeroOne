"""Leantime 동거 상태 라우터 — 로그인한 사용자에게 기동 여부를 돌려준다.

라우터-레벨 의존성으로 세션 로그인을 강제한다(미로그인 401). main.py 는 이 라우터를
prefix ``/api/v1/leantime`` 로 등록한다 → 최종 경로 ``/api/v1/leantime/health``.

상태만 노출하고 Leantime DB/데이터에는 접근하지 않는다(동거 경계 유지). 엔드포인트는
프로브 결과와 무관하게 항상 HTTP 200 을 반환한다 — 상태 자체가 페이로드다.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.modules.auth.dependencies import get_current_user
from app.modules.leantime import service

router = APIRouter(dependencies=[Depends(get_current_user)], tags=['leantime'])


class LeantimeHealth(BaseModel):
    """Leantime 동거 스택의 감지 결과.

    status 는 TCP 도달성 + 시간 제한 HTTP 프로브 + 앱 신원 식별로 판정한다:
    - ``absent``: TCP connect 거부/도달 불가(미설치/미구동)
    - ``starting``: TCP 는 연결되지만 HTTP 가 타임아웃/리셋/5xx(부팅 중)
    - ``unhealthy``: HTTP 는 응답하지만 Leantime 으로 식별되지 않음(또는 비인증 4xx)
    - ``ready``: HTTP 응답 성공 AND Leantime 으로 식별됨
    - ``error``: 프로브/설정 처리 중 예기치 않은 오류
    """

    status: Literal['ready', 'unhealthy', 'starting', 'absent', 'error']
    probe_host: str
    port: int
    probe_target: str
    launch_url: str
    checked_at: str
    latency_ms: int | None
    detail: str
    app_identified: bool


@router.get('/health', response_model=LeantimeHealth)
def health() -> LeantimeHealth:
    return LeantimeHealth(**service.leantime_status())  # type: ignore[arg-type]
