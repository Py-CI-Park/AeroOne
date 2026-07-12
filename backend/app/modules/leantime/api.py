"""Leantime 동거 상태 라우터 — 로그인한 사용자에게 기동 여부를 돌려준다.

라우터-레벨 의존성으로 세션 로그인을 강제한다(미로그인 401). main.py 는 이 라우터를
prefix ``/api/v1/leantime`` 로 등록한다 → 최종 경로 ``/api/v1/leantime/health``.

상태만 노출하고 Leantime DB/데이터에는 접근하지 않는다(동거 경계 유지).
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.modules.auth.dependencies import get_current_user
from app.modules.leantime import service

router = APIRouter(dependencies=[Depends(get_current_user)], tags=['leantime'])


class LeantimeHealth(BaseModel):
    """Leantime 동거 스택의 감지 결과. status 는 TCP 프로브로 판정한다."""

    status: Literal['up', 'down']
    probe_host: str
    port: int
    probe_target: str


@router.get('/health', response_model=LeantimeHealth)
def health() -> LeantimeHealth:
    return LeantimeHealth(**service.leantime_status())  # type: ignore[arg-type]
