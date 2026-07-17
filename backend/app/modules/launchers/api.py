"""외부 앱 런처(Open Notebook/OpenWebUI) 동거 상태 라우터.

라우터-레벨 의존성으로 세션 로그인을 강제한다(미로그인 401, leantime 과 동일 수준). main.py
는 이 라우터를 prefix ``/api/v1/launchers`` 로 등록한다 → 최종 경로
``/api/v1/launchers/{kind}/health``. ``kind`` 는 ``open_notebook``/``open_webui`` 만 허용하며
미등록 kind 는 404. 그 외에는 프로브 결과와 무관하게 항상 HTTP 200 을 반환한다(상태 자체가
페이로드).
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.modules.auth.dependencies import get_current_user
from app.modules.launchers import service

router = APIRouter(dependencies=[Depends(get_current_user)], tags=['launchers'])


class LauncherHealth(BaseModel):
    """외부 런처 동거 스택의 감지 결과.

    status 는 TCP 도달성 + 시간 제한 HTTP 프로브로 판정한다(신원 마커는 옵션 — 응답만
    오면 ready):
    - ``absent``: TCP connect 거부/도달 불가(미설치/미구동)
    - ``starting``: TCP 는 연결되지만 HTTP 가 타임아웃/리셋/5xx(부팅 중)
    - ``ready``: HTTP 응답을 받음
    - ``error``: 프로브/설정 처리 중 예기치 않은 오류
    """

    status: Literal['ready', 'starting', 'absent', 'error']
    port: int
    probe_target: str
    checked_at: str
    latency_ms: int | None
    detail: str


@router.get('/{kind}/health', response_model=LauncherHealth)
def health(kind: str) -> LauncherHealth:
    try:
        payload = service.launcher_status(kind)
    except service.UnknownLauncherKindError as exc:
        raise HTTPException(status_code=404, detail='알 수 없는 런처 종류입니다.') from exc
    return LauncherHealth(**payload)  # type: ignore[arg-type]
