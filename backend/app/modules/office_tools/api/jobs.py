"""jobs 서브라우터 — 산출물 조회/다운로드/번들. 세션 사용자 소유권으로 스코프한다.

MVP ``routes/jobs.py`` 를 포팅하되 인증/소유권을 더한다. ``job.json`` 의 ``owner_id`` 가
세션 사용자와 다르면 403. 잘못된 job_id(정규식 밖)나 경로 탈출은 404 로 차단한다.

JobStore 는 의존성(``get_office_job_store``)으로 주입해 테스트에서 tmp 루트로 교체할 수 있다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from app.core.config import Settings
from app.modules.auth.dependencies import get_current_user, get_settings
from app.modules.auth.models import User
from app.modules.office_tools.core.job_store import OfficeJobStore

router = APIRouter(tags=['office-tools'])


def get_office_job_store(settings: Settings = Depends(get_settings)) -> OfficeJobStore:
    return OfficeJobStore.from_settings(settings)


def _load_owned_job(store: OfficeJobStore, job_id: str, user: User) -> dict[str, object]:
    """job.json 을 읽고 소유권을 검증한다. 없으면 404, 타인 소유면 403."""

    try:
        record = store.get(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='job not found') from exc
    if record.get('owner_id') != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='job belongs to another user')
    return record


@router.get('/{job_id}')
def get_job(
    job_id: str,
    store: OfficeJobStore = Depends(get_office_job_store),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    return _load_owned_job(store, job_id, user)


@router.get('/{job_id}/artifacts/{filename}')
def get_artifact(
    job_id: str,
    filename: str,
    store: OfficeJobStore = Depends(get_office_job_store),
    user: User = Depends(get_current_user),
) -> FileResponse:
    _load_owned_job(store, job_id, user)
    try:
        path = store.artifact_path(job_id, filename)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='artifact not found') from exc
    return FileResponse(path, filename=path.name)


@router.get('/{job_id}/bundle')
def get_bundle(
    job_id: str,
    store: OfficeJobStore = Depends(get_office_job_store),
    user: User = Depends(get_current_user),
) -> FileResponse:
    _load_owned_job(store, job_id, user)
    try:
        path = store.create_bundle(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='job not found') from exc
    return FileResponse(path, filename=path.name, media_type='application/zip')
