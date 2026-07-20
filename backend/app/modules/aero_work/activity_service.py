"""Aero Work 실행기록 서비스 — 사용자 행위를 기록하고 최근 순으로 조회한다.

기록은 각 도메인 라우트가 성공 시 같은 트랜잭션에서 남긴다(입력·결과 요약을 쉬운 우리말로).
조회는 소유자(user_id) 스코프이며 최신순이다.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.aero_work.models import AeroWorkActivity

MAX_DETAIL_CHARS = 2000


def record_activity(
    db: Session, user_id: int, kind: str, summary: str, detail: str = ''
) -> AeroWorkActivity:
    activity = AeroWorkActivity(
        user_id=user_id,
        kind=kind,
        summary=(summary or '')[:400],
        detail=(detail or '')[:MAX_DETAIL_CHARS],
    )
    db.add(activity)
    db.flush()
    return activity


class ActivityService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_activities(self, user_id: int, *, limit: int = 50) -> list[AeroWorkActivity]:
        limit = max(1, min(limit, 200))
        stmt = (
            select(AeroWorkActivity)
            .where(AeroWorkActivity.user_id == user_id)
            .order_by(AeroWorkActivity.created_at.desc(), AeroWorkActivity.id.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())
