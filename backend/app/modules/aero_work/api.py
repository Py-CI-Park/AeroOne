"""Aero Work 지식폴더 REST 라우터 — ``/api/v1/aero-work`` prefix 로 include.

로그인한 사용자만 폴더 등록/색인/검색이 가능하다(익명 차단). 전용 ``aerowork.*`` 세분 권한과
service_modules 카드 노출은 후속(P0/P5) 범위이며, 여기서는 인증 게이트만 건다.
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Generator
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.aero_work import models as aero_work_models  # noqa: F401  (create_all 등록용)
from app.modules.aero_work.embedding_client import EmbeddingUnavailable, build_embedder
from app.modules.aero_work.activity_service import ActivityService, record_activity
from app.modules.aero_work.document_composer import ComposeUnavailable, compose_content, compose_truncated
from app.modules.aero_work.document_preview import render_preview_html
from app.modules.aero_work.document_formats import FORMAT_LABELS, format_document
from app.modules.aero_work.hwpx_generator import build_hwpx_document
from app.modules.aero_work.knowledge_service import KnowledgeError, KnowledgeService
from app.modules.aero_work.schedule_service import ScheduleError, ScheduleService
from app.modules.aero_work.prefs_service import get_llm_mode, set_llm_mode
from app.modules.aero_work.knowledge_summary import SummaryUnavailable, summarize_file
from app.modules.aero_work.orchestrator_service import OrchestratorService
from app.modules.aero_work.streaming import stream_answer, stream_compose
from app.modules.aero_work.taxonomy_service import apply_categories, delete_category, list_categories, propose_categories
from app.modules.aero_work.version_ranker import mark_latest
from app.modules.aero_work.schemas import (
    ActivityListResponse,
    ChatHistoryItem,
    ChatSessionListResponse,
    ChatSessionResponse,
    ChatHistoryResponse,
    DocumentComposeRequest,
    PreviewRequest,
    PreviewResponse,
    DocumentComposeResponse,
    PrefResponse,
    PrefUpdateRequest,
    SavedDocumentListResponse,
    SavedDocumentResponse,
    ActivityResponse,
    FileSummaryResponse,
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
    TaxonomyApplyRequest,
    TaxonomyApplyResponse,
    TaxonomyCategoryFile,
    TaxonomyCategoryInput,
    TaxonomyCategoryResponse,
    TaxonomyProposeRequest,
    TaxonomyProposeResponse,
    TaxonomyResponse,
)
from app.db.session import get_session_factory
from app.modules.auth.dependencies import get_db, get_optional_user, get_settings, require_csrf
from app.modules.auth.models import User

logger = logging.getLogger(__name__)
router = APIRouter()


def _service(db: Session, settings: Settings) -> KnowledgeService:
    return KnowledgeService(db, build_embedder(settings, db))


# ---- 비동기 재색인(G004) ----
# 폴더별 진행 중 가드 — 인메모리 set+lock. 프로세스 단일 인스턴스(uvicorn worker 1개)라는
# 전제 위에서만 안전하다 — 멀티 워커/프로세스로 확장하면 이 in-process set 은 워커마다
# 따로 생겨 서로를 보지 못해 가드가 무력화된다(같은 폴더를 워커 A/B 가 동시에 재색인).
# 후속으로 다중 워커를 지원하려면 이 가드를 DB CAS(예: folder.status 컬럼에 대해
# ``UPDATE ... SET status='indexing' WHERE id=:id AND status != 'indexing'`` 후
# rowcount 확인)로 승격해야 한다 — 지금은 배포가 단일 워커 고정이라 범위 밖(L6).
# 이미 진행 중인 폴더에 재색인을 걸면 409 로 즉시 거절한다.
_REINDEXING_FOLDER_IDS: set[int] = set()
_REINDEXING_LOCK = threading.Lock()


def _try_claim_reindex(folder_id: int) -> bool:
    with _REINDEXING_LOCK:
        if folder_id in _REINDEXING_FOLDER_IDS:
            return False
        _REINDEXING_FOLDER_IDS.add(folder_id)
        return True


def _release_reindex(folder_id: int) -> None:
    with _REINDEXING_LOCK:
        _REINDEXING_FOLDER_IDS.discard(folder_id)


def _is_reindexing(folder_id: int) -> bool:
    with _REINDEXING_LOCK:
        return folder_id in _REINDEXING_FOLDER_IDS


def reset_stale_indexing_folders(db: Session) -> int:
    """기동 스윅(H2) — 이전 프로세스가 'indexing' 도중 죽어서 남긴 폴더를 error 로 되돌린다.

    인메모리 가드(``_REINDEXING_FOLDER_IDS``)는 프로세스 재시작으로 항상 비어 시작하므로,
    DB 에만 'indexing' 으로 남은 폴더는 실제로는 아무도 진행하지 않는 좀비 상태다 — 그대로
    두면 UI 가 영원히 '색인 중'으로 멈춘다. 예외가 나도 앱 기동 자체를 막지 않도록 안전하게
    흡수한다.
    """

    from app.modules.aero_work.models import KnowledgeFolder as _KnowledgeFolder

    try:
        stale = db.query(_KnowledgeFolder).filter(_KnowledgeFolder.status == 'indexing').all()
        for folder in stale:
            folder.status = 'error'
            folder.status_detail = '서버 재시작으로 중단됨'
        if stale:
            db.commit()
        return len(stale)
    except Exception:  # noqa: BLE001 — 기동 스윅 실패는 로그만 남기고 서버 부팅을 막지 않는다
        logger.exception('기동 시 잔존 indexing 폴더 리셋 실패')
        db.rollback()
        return 0


def _run_background_reindex(folder_id: int, settings: Settings, owner_id: int) -> None:
    """백그라운드 스레드에서 새 세션으로 재색인한다 — 진행률을 status_detail 에 주기 반영."""

    db = get_session_factory()()
    try:
        service = KnowledgeService(db, build_embedder(settings, db))

        def _on_progress(done: int, total: int) -> None:
            folder = service.get_folder(folder_id)
            if folder is None:
                return
            folder.status_detail = f'{done}/{total} 파일'
            db.commit()

        try:
            folder = service.reindex(folder_id, progress_cb=_on_progress)
        except (EmbeddingUnavailable, KnowledgeError):
            db.commit()  # 서비스가 이미 status='error' + 사유를 status_detail 에 남겼다
            return
        except Exception:
            # H2: 예상 못한 예외(예: FK 위반 — 재색인 도중 폴더가 삭제된 경우)로 재색인이
            # 죽어도 폴더가 'indexing' 에 영원히 멈추지 않도록 error 상태로 남긴다. 세션이
            # 실패한 flush 로 오염됐을 수 있어 먼저 rollback 한 뒤 별도 커밋으로 상태만 남긴다.
            logger.exception('지식폴더 %s 백그라운드 재색인 중 처리되지 않은 예외', folder_id)
            db.rollback()
            folder = service.get_folder(folder_id)
            if folder is not None:
                folder.status = 'error'
                folder.status_detail = '재색인 중 예기치 않은 오류가 발생했습니다.'
                db.commit()
            return
        record_activity(db, owner_id, 'knowledge.reindex', f'"{folder.name}" 색인 완료', folder.status_detail)
        db.commit()
    finally:
        db.close()
        _release_reindex(folder_id)


def _require_user(user: User | None) -> User:
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='로그인이 필요합니다.')
    return user


def _sse_frame(event: str, data: object) -> str:
    return f'event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n'


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
        allowed_roots = [r for r in settings.aero_work_knowledge_roots.split(',') if r.strip()]
        folder = service.register_folder(payload.name, payload.path, allowed_roots=allowed_roots)
    except KnowledgeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    record_activity(db, owner.id, 'knowledge.register', f'지식폴더 "{folder.name}" 등록', folder.path)
    db.commit()
    return FolderResponse.from_model(folder)


@router.post(
    '/knowledge/folders/{folder_id}/reindex',
    dependencies=[Depends(require_csrf)],
)
def reindex_folder(
    folder_id: int,
    inline: bool = Query(
        default=False,
        description='테스트/결정성 전용 — True 면 예전처럼 동기 실행 후 완료된 FolderResponse 를 200 으로 돌려준다.',
    ),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User | None = Depends(get_optional_user),
) -> Response:
    """재색인을 건다 — 기본은 202 즉시 반환 + 백그라운드 스레드, ``inline=true`` 는 동기 실행(테스트용).

    같은 폴더에 이미 진행 중인 재색인이 있으면 409 를 돌려준다(인메모리 set+lock 가드).
    """

    owner = _require_user(user)
    service = _service(db, settings)
    folder = service.get_folder(folder_id)
    if folder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='폴더를 찾을 수 없습니다.')

    if inline:
        if not _try_claim_reindex(folder_id):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='이미 색인이 진행 중입니다.')
        try:
            folder = service.reindex(folder_id)
        except EmbeddingUnavailable as exc:
            db.commit()  # status='error' 상태를 저장한 뒤 안내
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
        except KnowledgeError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        finally:
            _release_reindex(folder_id)
        record_activity(db, owner.id, 'knowledge.reindex', f'"{folder.name}" 색인 완료', folder.status_detail)
        db.commit()
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=FolderResponse.from_model(folder).model_dump(mode='json'),
        )

    if not _try_claim_reindex(folder_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='이미 색인이 진행 중입니다.')

    try:
        folder.status = 'indexing'
        folder.status_detail = '색인을 준비하는 중'
        db.commit()

        thread = threading.Thread(
            target=_run_background_reindex, args=(folder_id, settings, owner.id), daemon=True
        )
        thread.start()
    except Exception:
        # M2: claim 이후 commit/thread 기동 중 실패하면 가드를 점유한 채로 남기지 않는다 —
        # 그러지 않으면 클라이언트가 영구히 409 만 받고 재시도할 방법이 없어진다.
        _release_reindex(folder_id)
        raise
    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={'status': 'indexing'})


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
    if _is_reindexing(folder_id):
        # M1: 재색인 스레드가 같은 세션의 폴더/파일/청크 행을 flush 하는 도중 삭제하면
        # FK 위반으로 백그라운드 스레드가 조용히 죽는다(레드팀 관측) — 가드가 점유 중이면
        # 삭제 자체를 409 로 거절해 그 경쟁을 원천 차단한다.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='재색인이 진행 중이라 삭제할 수 없습니다.')
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


@router.post('/knowledge/answer/stream', dependencies=[Depends(require_csrf)])
def answer_stream(
    payload: SearchRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User | None = Depends(get_optional_user),
) -> StreamingResponse:
    """지식 근거 검색 + LLM 합성을 SSE 로 스트리밍한다(hits → delta* → done|error).

    비스트리밍 ``/knowledge/search`` + ``OrchestratorService`` 합성 경로와 동일한 근거 조립을
    쓰되, 답변을 한 번에 반환하지 않고 청크 단위로 내보낸다(기존 엔드포인트는 불변 폴백).
    """

    owner = _require_user(user)
    service = _service(db, settings)
    try:
        hits = service.search(payload.query, folder_id=payload.folder_id, top_k=payload.top_k)
    except EmbeddingUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    mark_latest(hits)
    # 이 스트림은 orchestrate 경유 시 OrchestratorService 가 이미 'knowledge.search' 실행기록을
    # 남기므로(Q1/M2 리뷰), 여기서 다시 record_activity 를 호출하면 동일 검색에 대해 활동
    # 로그가 중복 기록된다 — 이 엔드포인트에서는 기록을 생략한다(orchestrate 가 유일한 기록 경로).
    force_local = get_llm_mode(db, owner.id) == 'local'

    def event_stream() -> Generator[str, None, None]:
        yield _sse_frame('hits', [SearchHit(**hit).model_dump() for hit in hits])
        for kind, value in stream_answer(settings, db, payload.query, hits, force_local=force_local):
            if kind == 'delta':
                yield _sse_frame('delta', value)
            elif kind == 'done':
                yield _sse_frame('done', {'answer': value})
            elif kind == 'error':
                yield _sse_frame('error', value)

    return StreamingResponse(event_stream(), media_type='text/event-stream')


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
    service = (
        OrchestratorService(db, settings, owner.id, synthesizer=lambda s, q, h: '')
        if not payload.synthesize
        else OrchestratorService(db, settings, owner.id)
    )
    raw_results = service.run(payload.utterance, attachments=payload.attachments)
    results = [
        OrchestrateResult(
            kind=item['kind'],
            summary=item['summary'],
            events=item.get('events', []),
            hits=[SearchHit(**hit) for hit in item.get('hits', [])],
            document=DocumentIntent(**item['document']) if item.get('document') else None,
            feature=item.get('feature'),
            answer=item.get('answer', ''),
            routed_by=item.get('routed_by'),
        )
        for item in raw_results
    ]
    # 세션 해석 — 지정 없으면 새 세션 생성(제목=첫 발화 40자, gongmuwon 세션 중심 IA).
    session_row = None
    if payload.session_id is not None:
        session_row = db.get(aero_work_models.AeroWorkChatSession, payload.session_id)
        if session_row is None or session_row.user_id != owner.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='세션을 찾을 수 없습니다.')
        session_row.updated_at = datetime.now()
    else:
        session_row = aero_work_models.AeroWorkChatSession(user_id=owner.id, title=payload.utterance[:40])
        db.add(session_row)
        db.flush()
    # 업무대화 영속화 — 새로고침해도 세션 흐름이 남는다(소유자 스코프).
    db.add(
        aero_work_models.AeroWorkChatMessage(
            user_id=owner.id,
            session_id=session_row.id,
            utterance=payload.utterance,
            results_json=json.dumps([r.model_dump(mode='json') for r in results], ensure_ascii=False),
        )
    )
    db.commit()
    return OrchestrateResponse(utterance=payload.utterance, session_id=session_row.id, results=results)


@router.get('/chat/history', response_model=ChatHistoryResponse)
def chat_history(
    limit: int = Query(default=20, ge=1, le=100),
    session_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> ChatHistoryResponse:
    owner = _require_user(user)
    query = (
        db.query(aero_work_models.AeroWorkChatMessage)
        .filter(aero_work_models.AeroWorkChatMessage.user_id == owner.id)
    )
    if session_id is not None:
        query = query.filter(aero_work_models.AeroWorkChatMessage.session_id == session_id)
    rows = (
        query.order_by(aero_work_models.AeroWorkChatMessage.created_at.desc(), aero_work_models.AeroWorkChatMessage.id.desc())
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


@router.get('/chat/sessions', response_model=ChatSessionListResponse)
def list_chat_sessions(
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> ChatSessionListResponse:
    owner = _require_user(user)
    rows = (
        db.query(aero_work_models.AeroWorkChatSession)
        .filter(aero_work_models.AeroWorkChatSession.user_id == owner.id)
        .order_by(aero_work_models.AeroWorkChatSession.updated_at.desc(), aero_work_models.AeroWorkChatSession.id.desc())
        .limit(50)
        .all()
    )
    return ChatSessionListResponse(
        sessions=[ChatSessionResponse(id=row.id, title=row.title, updated_at=row.updated_at) for row in rows]
    )


@router.delete('/chat/sessions/{session_id}', status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf)])
def delete_chat_session(
    session_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> Response:
    owner = _require_user(user)
    row = db.get(aero_work_models.AeroWorkChatSession, session_id)
    if row is None or row.user_id != owner.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='세션을 찾을 수 없습니다.')
    db.query(aero_work_models.AeroWorkChatMessage).filter(
        aero_work_models.AeroWorkChatMessage.user_id == owner.id,
        aero_work_models.AeroWorkChatMessage.session_id == session_id,
    ).delete()
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
            previous_paragraphs=payload.previous_paragraphs,
            force_local=get_llm_mode(db, owner.id) == 'local',
        )
    except ComposeUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    record_activity(db, owner.id, 'document.compose', f'문서 내용 생성 "{title}" — {len(paragraphs)}문장')
    db.commit()
    truncated = compose_truncated(payload.instruction, payload.previous_paragraphs)
    return DocumentComposeResponse(paragraphs=paragraphs, truncated=truncated)


@router.post('/document/compose/stream', dependencies=[Depends(require_csrf)])
def compose_document_stream(
    payload: DocumentComposeRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User | None = Depends(get_optional_user),
) -> StreamingResponse:
    """지시 → LLM 개조식 내용 생성을 SSE 로 스트리밍한다(delta* → done|error).

    비스트리밍 ``/document/compose`` 와 동일한 프롬프트 조립을 쓰되, 결과를 청크 단위로
    내보낸다(기존 엔드포인트는 불변 폴백). 실행기록은 스트림 시작 전에 커밋한다 — 완성
    문장 수는 스트리밍 특성상 시작 시점에 알 수 없다.
    """

    owner = _require_user(user)
    title = (payload.title or '').strip() or '무제'
    record_activity(db, owner.id, 'document.compose', f'문서 내용 생성 "{title}"')
    db.commit()
    force_local = get_llm_mode(db, owner.id) == 'local'

    def event_stream() -> Generator[str, None, None]:
        for kind, value in stream_compose(
            settings, db, fmt=payload.format, title=title, instruction=payload.instruction,
            previous_paragraphs=payload.previous_paragraphs, force_local=force_local
        ):
            if kind == 'delta':
                yield _sse_frame('delta', value)
            elif kind == 'done':
                # P3 잔여 해소 — 스트리밍 주경로에서도 절단 신호를 내려 '일부만 반영됨' 안내가
                # 비스트리밍 폴백에서만 뜨는 비대칭을 없앤다(프레임에 truncated 추가, 후방호환).
                yield _sse_frame('done', {
                    'paragraphs': value,
                    'truncated': compose_truncated(payload.instruction, payload.previous_paragraphs),
                })
            elif kind == 'error':
                yield _sse_frame('error', value)

    return StreamingResponse(event_stream(), media_type='text/event-stream')

@router.post('/document/preview', response_model=PreviewResponse, dependencies=[Depends(require_csrf)])
def preview_document(
    payload: PreviewRequest,
    user: User | None = Depends(get_optional_user),
) -> PreviewResponse:
    """양식(종이) 미리보기 — gongmuwon §5.3. 사용자 텍스트는 전부 이스케이프해 텍스트로만 삽입.

    디바운스 재요청이 빈번한 엔드포인트라 실행기록(record_activity)은 남기지 않는다(L3) —
    활동 로그 범람 방지. 문서 생성/저장 등 실제 산출물이 남는 동작만 기록한다.
    """

    _require_user(user)
    title = (payload.title or '').strip() or '무제'
    html = render_preview_html(payload.format_id, title, payload.paragraphs)
    return PreviewResponse(html=html)


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


@router.post('/knowledge/files/{file_id}/summarize', response_model=FileSummaryResponse, dependencies=[Depends(require_csrf)])
def summarize_knowledge_file(
    file_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User | None = Depends(get_optional_user),
) -> FileSummaryResponse:
    """지식 파일 LLM 요약(문서 카드) — provider·사용자 프로필 경유, 결과는 저장."""

    owner = _require_user(user)
    try:
        summary = summarize_file(
            settings, db, file_id, force_local=get_llm_mode(db, owner.id) == 'local'
        )
    except SummaryUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    record_activity(db, owner.id, 'knowledge.summarize', f'문서 요약 생성 (file #{file_id})')
    db.commit()
    return FileSummaryResponse(summary=summary)


# ---- 업무 분류체계 마법사(§6.6) ----
@router.post('/taxonomy/propose', response_model=TaxonomyProposeResponse, dependencies=[Depends(require_csrf)])
def propose_taxonomy(
    payload: TaxonomyProposeRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User | None = Depends(get_optional_user),
) -> TaxonomyProposeResponse:
    """① 니즈 파악 입력 → ② 색인 파일 근거로 LLM 업무 분류 후보 생성(사용자 검토용)."""

    owner = _require_user(user)
    candidates, model, reason, truncated = propose_categories(
        db,
        settings,
        owner.id,
        organization=payload.organization,
        department=payload.department,
        duties=payload.duties,
    )
    record_activity(db, owner.id, 'taxonomy.propose', f'업무 분류 후보 생성 — {len(candidates)}건')
    db.commit()
    return TaxonomyProposeResponse(
        candidates=[TaxonomyCategoryInput(**candidate) for candidate in candidates],
        model=model,
        reason=reason,
        truncated=truncated,
    )


@router.post('/taxonomy/apply', response_model=TaxonomyApplyResponse, dependencies=[Depends(require_csrf)])
def apply_taxonomy(
    payload: TaxonomyApplyRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> TaxonomyApplyResponse:
    """③ 적용 — 사용자가 확정한 분류로 기존 분류를 전량 교체한다(멱등)."""

    owner = _require_user(user)
    applied = apply_categories(db, owner.id, [category.model_dump() for category in payload.categories])
    db.commit()
    return TaxonomyApplyResponse(applied=applied)


@router.get('/taxonomy', response_model=TaxonomyResponse)
def get_taxonomy(
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> TaxonomyResponse:
    """지식위키의 업무 분류 트리 — 분류별 소속 파일(경로/폴더명/요약)과 함께 반환."""

    owner = _require_user(user)
    categories = list_categories(db, owner.id)
    return TaxonomyResponse(
        categories=[
            TaxonomyCategoryResponse(
                id=item['id'],
                name=item['name'],
                description=item['description'],
                sort_order=item['sort_order'],
                files=[TaxonomyCategoryFile(**file_row) for file_row in item['files']],
            )
            for item in categories
        ]
    )


@router.delete('/taxonomy/{category_id}', status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf)])
def delete_taxonomy_category(
    category_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> Response:
    owner = _require_user(user)
    deleted = delete_category(db, owner.id, category_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='업무 분류를 찾을 수 없습니다.')
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
