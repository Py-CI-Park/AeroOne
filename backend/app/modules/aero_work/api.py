"""Aero Work 지식폴더 REST 라우터 — ``/api/v1/aero-work`` prefix 로 include.

로그인한 사용자만 폴더 등록/색인/검색이 가능하다(익명 차단). 전용 ``aerowork.*`` 세분 권한과
service_modules 카드 노출은 후속(P0/P5) 범위이며, 여기서는 인증 게이트만 건다.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.aero_work import models as aero_work_models  # noqa: F401  (create_all 등록용)
from app.modules.aero_work.embedding_client import EmbeddingUnavailable, OllamaEmbedder
from app.modules.aero_work.knowledge_service import KnowledgeError, KnowledgeService
from app.modules.aero_work.schedule_service import ScheduleError, ScheduleService
from app.modules.aero_work.schemas import (
    EventCreateRequest,
    EventListResponse,
    EventResponse,
    EventUpdateRequest,
    FolderListResponse,
    FolderRegisterRequest,
    FolderResponse,
    SearchHit,
    SearchRequest,
    SearchResponse,
)
from app.modules.auth.dependencies import get_db, get_optional_user, get_settings, require_csrf
from app.modules.auth.models import User

router = APIRouter()


def _service(db: Session, settings: Settings) -> KnowledgeService:
    return KnowledgeService(db, OllamaEmbedder(settings))


def _require_user(user: User | None) -> User:
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='로그인이 필요합니다.')
    return user


@router.get('/knowledge/folders', response_model=FolderListResponse)
def list_folders(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User | None = Depends(get_optional_user),
) -> FolderListResponse:
    _require_user(user)
    service = _service(db, settings)
    return FolderListResponse(folders=[FolderResponse.from_model(f) for f in service.list_folders()])


@router.post(
    '/knowledge/folders',
    response_model=FolderResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def register_folder(
    payload: FolderRegisterRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User | None = Depends(get_optional_user),
) -> FolderResponse:
    _require_user(user)
    service = _service(db, settings)
    try:
        folder = service.register_folder(payload.name, payload.path)
    except KnowledgeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    return FolderResponse.from_model(folder)


@router.post(
    '/knowledge/folders/{folder_id}/reindex',
    response_model=FolderResponse,
    dependencies=[Depends(require_csrf)],
)
def reindex_folder(
    folder_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User | None = Depends(get_optional_user),
) -> FolderResponse:
    _require_user(user)
    service = _service(db, settings)
    try:
        folder = service.reindex(folder_id)
    except EmbeddingUnavailable as exc:
        db.commit()  # status='error' 상태를 저장한 뒤 안내
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except KnowledgeError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    db.commit()
    return FolderResponse.from_model(folder)


@router.delete(
    '/knowledge/folders/{folder_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
def delete_folder(
    folder_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User | None = Depends(get_optional_user),
) -> Response:
    _require_user(user)
    service = _service(db, settings)
    if not service.delete_folder(folder_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='폴더를 찾을 수 없습니다.')
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post('/knowledge/search', response_model=SearchResponse)
def search_knowledge(
    payload: SearchRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User | None = Depends(get_optional_user),
) -> SearchResponse:
    _require_user(user)
    service = _service(db, settings)
    try:
        hits = service.search(payload.query, folder_id=payload.folder_id, top_k=payload.top_k)
    except EmbeddingUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return SearchResponse(hits=[SearchHit(**hit) for hit in hits], model=service.embedder.model)


# ---- 일정(Schedule) ----
@router.get('/schedule/events', response_model=EventListResponse)
def list_events(
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> EventListResponse:
    owner = _require_user(user)
    service = ScheduleService(db)
    events = service.list_events(owner.id, start=start, end=end)
    return EventListResponse(events=[EventResponse.from_model(event) for event in events])


@router.post(
    '/schedule/events',
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def create_event(
    payload: EventCreateRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> EventResponse:
    owner = _require_user(user)
    service = ScheduleService(db)
    try:
        event = service.create_event(
            owner.id,
            title=payload.title,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            all_day=payload.all_day,
            location=payload.location,
            notes=payload.notes,
        )
    except ScheduleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    return EventResponse.from_model(event)


@router.patch(
    '/schedule/events/{event_id}',
    response_model=EventResponse,
    dependencies=[Depends(require_csrf)],
)
def update_event(
    event_id: int,
    payload: EventUpdateRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> EventResponse:
    owner = _require_user(user)
    service = ScheduleService(db)
    try:
        event = service.update_event(owner.id, event_id, payload.model_dump(exclude_unset=True))
    except ScheduleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='일정을 찾을 수 없습니다.')
    db.commit()
    return EventResponse.from_model(event)


@router.delete(
    '/schedule/events/{event_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> Response:
    owner = _require_user(user)
    service = ScheduleService(db)
    if not service.delete_event(owner.id, event_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='일정을 찾을 수 없습니다.')
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
