"""Aero Work 개인 할 일 CRUD — 모든 조회와 변경은 사용자 소유권으로 제한한다."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.aero_work.activity_service import record_activity
from app.modules.aero_work.models import AeroWorkTask

_VALID_STATUSES = {'todo', 'doing', 'done'}


class TaskError(RuntimeError):
    """할 일 입력값이 도메인 규칙을 만족하지 않을 때 발생한다."""


def _title(value: str) -> str:
    value = (value or '').strip()
    if not value:
        raise TaskError('제목은 비울 수 없습니다.')
    if len(value) > 300:
        raise TaskError('제목은 최대 300자입니다.')
    return value


def create_task(db: Session, user_id: int, title: str, due_date: date | None = None, tags: str = '') -> AeroWorkTask:
    task = AeroWorkTask(user_id=user_id, title=_title(title), due_date=due_date, tags=(tags or '').strip())
    db.add(task)
    db.flush()
    record_activity(db, user_id, 'task.create', f'할 일 추가 "{task.title}"')
    return task


def list_tasks(
    db: Session, user_id: int, *, status: str | None = None, overdue: bool | None = None, now: date | None = None
) -> list[AeroWorkTask]:
    if status is not None and status not in _VALID_STATUSES:
        raise TaskError('지원하지 않는 할 일 상태입니다.')
    stmt = select(AeroWorkTask).where(AeroWorkTask.user_id == user_id)
    if status is not None:
        stmt = stmt.where(AeroWorkTask.status == status)
    if overdue:
        today = now or date.today()
        stmt = stmt.where(AeroWorkTask.due_date.is_not(None), AeroWorkTask.due_date < today, AeroWorkTask.status != 'done')
    return list(db.execute(stmt.order_by(AeroWorkTask.due_date.is_(None), AeroWorkTask.due_date, AeroWorkTask.id)).scalars().all())


def update_task(db: Session, user_id: int, task_id: int, **fields) -> AeroWorkTask | None:
    task = db.execute(select(AeroWorkTask).where(AeroWorkTask.id == task_id, AeroWorkTask.user_id == user_id)).scalar_one_or_none()
    if task is None:
        return None
    if 'title' in fields:
        task.title = _title(fields['title'])
    if 'due_date' in fields:
        task.due_date = fields['due_date']
    if 'tags' in fields:
        task.tags = (fields['tags'] or '').strip()
    if 'status' in fields:
        task_status = fields['status']
        if task_status not in _VALID_STATUSES:
            raise TaskError('지원하지 않는 할 일 상태입니다.')
        task.status = task_status
        task.done_at = datetime.now() if task_status == 'done' else None
    db.flush()
    record_activity(db, user_id, 'task.update', f'할 일 수정 "{task.title}"')
    return task


def delete_task(db: Session, user_id: int, task_id: int) -> bool:
    task = db.execute(select(AeroWorkTask).where(AeroWorkTask.id == task_id, AeroWorkTask.user_id == user_id)).scalar_one_or_none()
    if task is None:
        return False
    title = task.title
    db.delete(task)
    db.flush()
    record_activity(db, user_id, 'task.delete', f'할 일 삭제 "{title}"')
    return True
