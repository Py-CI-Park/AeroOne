"""Aero Work 지식폴더 REST 라우터 — ``/api/v1/aero-work`` prefix 로 include.

로그인한 사용자만 폴더 등록/색인/검색이 가능하다(익명 차단). 전용 ``aerowork.*`` 세분 권한과
service_modules 카드 노출은 후속(P0/P5) 범위이며, 여기서는 인증 게이트만 건다.
"""

from __future__ import annotations

import json
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.aero_work import models as aero_work_models  # noqa: F401  (create_all 등록용)
from app.modules.aero_work.embedding_client import EmbeddingUnavailable, OllamaEmbedder
from app.modules.aero_work.activity_service import ActivityService, record_activity
from app.modules.aero_work.document_composer import ComposeUnavailable, compose_content
from app.modules.aero_work.document_formats import FORMAT_LABELS, format_document
from app.modules.aero_work.hwpx_generator import build_hwpx_document
from app.modules.aero_work.knowledge_service import KnowledgeError, KnowledgeService
from app.modules.aero_work.schedule_service import ScheduleError, ScheduleService
from app.modules.aero_work.prefs_service import get_llm_mode, set_llm_mode
from app.modules.aero_work.orchestrator_service import OrchestratorService
from app.modules.aero_work.schemas import (
    ActivityListResponse,
    ChatHistoryItem,
    ChatHistoryResponse,
    DocumentComposeRequest,
    DocumentComposeResponse,
    PrefResponse,
    PrefUpdateRequest,
    SavedDocumentListResponse,
    SavedDocumentResponse,
    ActivityResponse,
    EventCreateRequest,
    EventListResponse,
    EventResponse,
    DocumentIntent,
    DocumentRequest,
    EventUpdateRequest,
    FolderListResponse,
    FolderRegisterRequest,
    FolderResponse,
    OrchestrateRequest,
    OrchestrateResponse,
    OrchestrateResult,
    SearchHit,
    SearchRequest,
    SearchResponse,
    WikiResponse,
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
    owner = _require_user(user)
    service = _service(db, settings)
    try:
        folder = service.register_folder(payload.name, payload.path)
    except KnowledgeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    record_activity(db, owner.id, 'knowledge.register', f'지식폴더 "{folder.name}" 등록', folder.path)
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
    owner = _require_user(user)
    service = _service(db, settings)
    try:
        folder = service.reindex(folder_id)
    except EmbeddingUnavailable as exc:
        db.commit()  # status='error' 상태를 저장한 뒤 안내
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except KnowledgeError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    record_activity(db, owner.id, 'knowledge.reindex', f'"{folder.name}" 색인 완료', folder.status_detail)
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
    owner = _require_user(user)
    service = _service(db, settings)
    folder = service.get_folder(folder_id)
    if folder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='폴더를 찾을 수 없습니다.')
    folder_name = folder.name
    service.delete_folder(folder_id)
    record_activity(db, owner.id, 'knowledge.delete', f'지식폴더 "{folder_name}" 삭제')
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post('/knowledge/search', response_model=SearchResponse)
def search_knowledge(
    payload: SearchRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User | None = Depends(get_optional_user),
) -> SearchResponse:
    owner = _require_user(user)
    service = _service(db, settings)
    try:
        hits = service.search(payload.query, folder_id=payload.folder_id, top_k=payload.top_k)
    except EmbeddingUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    result = SearchResponse(hits=[SearchHit(**hit) for hit in hits], model=service.embedder.model)
    record_activity(db, owner.id, 'knowledge.search', f'지식 검색 "{payload.query}" — {len(hits)}건')
    db.commit()
    return result


@router.post('/knowledge/keyword-search', response_model=SearchResponse)
def keyword_search(
    payload: SearchRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User | None = Depends(get_optional_user),
) -> SearchResponse:
    owner = _require_user(user)
    service = _service(db, settings)
    hits = service.keyword_search(payload.query, folder_id=payload.folder_id, top_k=payload.top_k)
    record_activity(db, owner.id, 'knowledge.search', f'키워드 검색 "{payload.query}" — {len(hits)}건')
    db.commit()
    return SearchResponse(hits=[SearchHit(**hit) for hit in hits], model='keyword')


@router.get('/knowledge/wiki', response_model=WikiResponse)
def knowledge_wiki(
    folder_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User | None = Depends(get_optional_user),
) -> WikiResponse:
    _require_user(user)
    service = _service(db, settings)
    return WikiResponse(families=service.wiki(folder_id=folder_id))


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
            remind_before_minutes=payload.remind_before_minutes,
        )
    except ScheduleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    record_activity(db, owner.id, 'schedule.create', f'일정 추가 "{event.title}"')
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
    record_activity(db, owner.id, 'schedule.update', f'일정 수정 "{event.title}"')
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
    event = service.get_event(owner.id, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='일정을 찾을 수 없습니다.')
    event_title = event.title
    service.delete_event(owner.id, event_id)
    record_activity(db, owner.id, 'schedule.delete', f'일정 삭제 "{event_title}"')
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- 실행기록(Activity) ----
@router.get('/activity', response_model=ActivityListResponse)
def list_activity(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> ActivityListResponse:
    owner = _require_user(user)
    service = ActivityService(db)
    activities = service.list_activities(owner.id, limit=limit)
    return ActivityListResponse(activities=[ActivityResponse.from_model(item) for item in activities])


# ---- 문서작성(HWPX) ----
@router.post('/document/hwpx', dependencies=[Depends(require_csrf)])
def generate_hwpx(
    payload: DocumentRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> Response:
    owner = _require_user(user)
    title = (payload.title or '').strip() or '무제'
    paragraphs = format_document(payload.format, title, payload.body)
    data = build_hwpx_document(title, paragraphs)
    label = FORMAT_LABELS.get(payload.format, '문서')
    record_activity(db, owner.id, 'document.generate', f'HWPX {label} 생성 "{title}"')
    db.commit()
    disposition = f"attachment; filename=\"document.hwpx\"; filename*=UTF-8''{quote(title)}.hwpx"
    return Response(
        content=data,
        media_type='application/hwp+zip',
        headers={'Content-Disposition': disposition},
    )


# ---- 업무대화 오케스트레이션 (F1) ----
@router.post('/orchestrate', response_model=OrchestrateResponse, dependencies=[Depends(require_csrf)])
def orchestrate(
    payload: OrchestrateRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User | None = Depends(get_optional_user),
) -> OrchestrateResponse:
    owner = _require_user(user)
    service = OrchestratorService(db, settings, owner.id)
    raw_results = service.run(payload.utterance)
    results = [
        OrchestrateResult(
            kind=item['kind'],
            summary=item['summary'],
            events=item.get('events', []),
            hits=[SearchHit(**hit) for hit in item.get('hits', [])],
            document=DocumentIntent(**item['document']) if item.get('document') else None,
            feature=item.get('feature'),
            answer=item.get('answer', ''),
        )
        for item in raw_results
    ]
    # 업무대화 영속화 — 새로고침해도 세션 흐름이 남는다(소유자 스코프).
    db.add(
        aero_work_models.AeroWorkChatMessage(
            user_id=owner.id,
            utterance=payload.utterance,
            results_json=json.dumps([r.model_dump(mode='json') for r in results], ensure_ascii=False),
        )
    )
    db.commit()
    return OrchestrateResponse(utterance=payload.utterance, results=results)


@router.get('/chat/history', response_model=ChatHistoryResponse)
def chat_history(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> ChatHistoryResponse:
    owner = _require_user(user)
    rows = (
        db.query(aero_work_models.AeroWorkChatMessage)
        .filter(aero_work_models.AeroWorkChatMessage.user_id == owner.id)
        .order_by(aero_work_models.AeroWorkChatMessage.created_at.desc(), aero_work_models.AeroWorkChatMessage.id.desc())
        .limit(limit)
        .all()
    )
    items = []
    for row in rows:
        try:
            results = [OrchestrateResult(**item) for item in json.loads(row.results_json)]
        except (ValueError, TypeError):
            results = []
        items.append(ChatHistoryItem(id=row.id, utterance=row.utterance, results=results, created_at=row.created_at))
    return ChatHistoryResponse(items=items)


@router.post('/document/compose', response_model=DocumentComposeResponse, dependencies=[Depends(require_csrf)])
def compose_document(
    payload: DocumentComposeRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User | None = Depends(get_optional_user),
) -> DocumentComposeResponse:
    """지시 → LLM 개조식 내용 생성(gongmuwon '구조 생성 → 검토'). provider 시스템 경유."""

    owner = _require_user(user)
    title = (payload.title or '').strip() or '무제'
    try:
        paragraphs = compose_content(
            settings, db, fmt=payload.format, title=title, instruction=payload.instruction,
            force_local=get_llm_mode(db, owner.id) == 'local',
        )
    except ComposeUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    record_activity(db, owner.id, 'document.compose', f'문서 내용 생성 "{title}" — {len(paragraphs)}문장')
    db.commit()
    return DocumentComposeResponse(paragraphs=paragraphs)


# ---- 환경설정(사용자 LLM 프로필) ----
@router.get('/prefs', response_model=PrefResponse)
def get_prefs(
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> PrefResponse:
    owner = _require_user(user)
    return PrefResponse(llm_mode=get_llm_mode(db, owner.id))


@router.put('/prefs', response_model=PrefResponse, dependencies=[Depends(require_csrf)])
def update_prefs(
    payload: PrefUpdateRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> PrefResponse:
    owner = _require_user(user)
    mode = set_llm_mode(db, owner.id, payload.llm_mode)
    record_activity(db, owner.id, 'settings.llm_mode', f'LLM 프로필 전환 — {"로컬 강제" if mode == "local" else "관리자 선택 따름"}')
    db.commit()
    return PrefResponse(llm_mode=mode)


# ---- 문서 최종 저장(승인형 정책) ----
@router.post('/document/save-request', response_model=SavedDocumentResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_csrf)])
def request_document_save(
    payload: DocumentRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> SavedDocumentResponse:
    owner = _require_user(user)
    title = (payload.title or '').strip() or '무제'
    doc = aero_work_models.AeroWorkDocument(
        user_id=owner.id, title=title, format=payload.format, body=payload.body, status='pending'
    )
    db.add(doc)
    db.flush()
    record_activity(db, owner.id, 'document.save_request', f'최종 저장 요청 "{title}" — 승인 대기')
    db.commit()
    return SavedDocumentResponse.from_model(doc)


@router.get('/document/saved', response_model=SavedDocumentListResponse)
def list_saved_documents(
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> SavedDocumentListResponse:
    owner = _require_user(user)
    rows = (
        db.query(aero_work_models.AeroWorkDocument)
        .filter(aero_work_models.AeroWorkDocument.user_id == owner.id)
        .order_by(aero_work_models.AeroWorkDocument.created_at.desc(), aero_work_models.AeroWorkDocument.id.desc())
        .limit(50)
        .all()
    )
    return SavedDocumentListResponse(documents=[SavedDocumentResponse.from_model(row) for row in rows])


def _owned_document(db: Session, owner: User, document_id: int) -> 'aero_work_models.AeroWorkDocument':
    doc = db.get(aero_work_models.AeroWorkDocument, document_id)
    if doc is None or doc.user_id != owner.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='문서를 찾을 수 없습니다.')
    return doc


@router.post('/document/saved/{document_id}/approve', response_model=SavedDocumentResponse, dependencies=[Depends(require_csrf)])
def approve_document(
    document_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> SavedDocumentResponse:
    owner = _require_user(user)
    doc = _owned_document(db, owner, document_id)
    doc.status = 'approved'
    record_activity(db, owner.id, 'document.approve', f'최종 저장 승인 "{doc.title}"')
    db.commit()
    return SavedDocumentResponse.from_model(doc)


@router.get('/document/saved/{document_id}/download')
def download_saved_document(
    document_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> Response:
    owner = _require_user(user)
    doc = _owned_document(db, owner, document_id)
    if doc.status != 'approved':
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='승인 대기 중입니다. 승인 후 내려받을 수 있습니다.')
    paragraphs = format_document(doc.format, doc.title, doc.body)
    data = build_hwpx_document(doc.title, paragraphs)
    record_activity(db, owner.id, 'document.generate', f'HWPX {FORMAT_LABELS.get(doc.format, "문서")} 생성 "{doc.title}" (승인본)')
    db.commit()
    disposition = f"attachment; filename=\"document.hwpx\"; filename*=UTF-8''{quote(doc.title)}.hwpx"
    return Response(content=data, media_type='application/hwp+zip', headers={'Content-Disposition': disposition})


@router.delete('/document/saved/{document_id}', status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf)])
def delete_saved_document(
    document_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> Response:
    owner = _require_user(user)
    doc = _owned_document(db, owner, document_id)
    title = doc.title
    db.delete(doc)
    record_activity(db, owner.id, 'document.discard', f'최종 저장 요청 폐기 "{title}"')
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
