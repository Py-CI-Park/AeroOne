from __future__ import annotations

import json
import uuid
import time
from collections.abc import Generator
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.ai.schemas import (
    AiChatRequest,
    AiChatResponse,
    AiCitation,
    AiChatMessage,
    AiConversationDetail,
    AiConversationListResponse,
    AiConversationSummary,
    AiConversationUpdate,
    AiMessageOut,
    AiStatusResponse,
)
from app.modules.ai.service import AiChatService, OllamaEmptyResponse, OllamaModelMissing, OllamaUnavailable
from app.modules.ai.provider_config_service import ProviderConfigService
from app.modules.ai import models as ai_models  # noqa: F401  (create_all 등록용 import 체인)
from app.modules.ai.repositories import AiConversationRepository
from app.modules.ai.models import AiConversation
from app.modules.admin.models import AiRequestLog
from app.modules.admin.permissions import has_permission
from app.modules.auth.dependencies import get_db, get_optional_user, get_settings
from app.modules.auth.models import User
from app.modules.collections.policy import can_read_collection, readable_collections
from app.modules.collections.search_service import ALL_SEARCH_COLLECTIONS, DEFAULT_SEARCH_COLLECTIONS, CollectionSearchRoot


AI_SESSION_COOKIE = 'ai_session'


router = APIRouter()


def _resolve_collection_root(collection: str, settings: Settings) -> Path:
    whitelist: dict[str, Path] = {
        'document': settings.document_root_path,
        'civil': settings.civil_aircraft_root_path,
        'nsa': settings.nsa_root_path,
    }
    root = whitelist.get(collection)
    if root is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Unknown collection')
    return root


def _requested_collections(collections: list[str] | None) -> list[str]:
    requested = list(DEFAULT_SEARCH_COLLECTIONS if collections is None else collections)
    unknown = [collection for collection in requested if collection not in ALL_SEARCH_COLLECTIONS]
    if unknown:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Unknown collection')
    return list(dict.fromkeys(requested))


def _client_ip(request: Request) -> str | None:
    # 리버스 프록시 없는 직결 전제(read_tracking 선례와 동일). owner_ip 는 감사 메타
    # 전용이며 대화 조회 스코프에는 절대 쓰지 않는다.
    if request.client is not None and request.client.host:
        return request.client.host
    return None


def _owner_session(request: Request, response: Response, settings: Settings) -> str:
    """세션 쿠키 단독 권위. 쿠키가 있으면 그 세션, 없으면 새 세션을 발급(host-only+Path=/)."""

    existing = request.cookies.get(AI_SESSION_COOKIE)
    if existing:
        return existing
    session_id = uuid.uuid4().hex
    response.set_cookie(
        key=AI_SESSION_COOKIE,
        value=session_id,
        httponly=True,
        samesite='lax',
        secure=settings.secure_cookies,
        path='/',
        max_age=60 * 60 * 24 * 365,
    )
    return session_id


@dataclass
class _ChatContext:
    """``/chat`` 과 ``/chat/stream`` 이 공유하는 전처리 결과(권한 게이트 이후 상태)."""

    provider_config_service: ProviderConfigService
    collections: list[str]
    roots: list[CollectionSearchRoot]
    selected_refs: list[tuple[str, str]]
    roots_by_collection: dict[str, Path]


def _prepare_chat_context(
    payload: AiChatRequest,
    db: Session,
    settings: Settings,
    current_user: User | None,
) -> _ChatContext:
    """``/chat``/``/chat/stream`` 공통 전처리: provider 선택에 따른 ai.use 사전 게이트,
    readable_collections/selected_refs/roots 계산. 공유 로직은 여기 한 곳에만 존재한다
    (복제 금지)."""

    provider_config_service = ProviderConfigService(db, settings)
    provider_state = provider_config_service.get_state()
    # 명시적 provider 선택만 신뢰한다(요청 시점 폴백 금지). openai_compatible 이 선택된
    # 경우에만 활성 인증 사용자의 정확한 ai.use 권한을 사전 게이트한다 — Ollama 경로는
    # 익명 접근을 포함해 기존 동작을 그대로 보존한다.
    if provider_state.selected_kind == 'openai_compatible':
        if current_user is None or not current_user.is_active or not has_permission(db, current_user, 'ai.use'):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='ai_use_required')
    requested_collections = _requested_collections(payload.collections)
    collections = readable_collections(db, current_user, requested_collections)
    roots = [
        CollectionSearchRoot(collection=collection, root=_resolve_collection_root(collection, settings))
        for collection in collections
    ]
    selected_refs = [
        (ref.collection, ref.path)
        for ref in payload.selected_refs
        if can_read_collection(db, current_user, ref.collection)
    ]
    roots_by_collection = {
        collection: _resolve_collection_root(collection, settings)
        for collection in ALL_SEARCH_COLLECTIONS
        if can_read_collection(db, current_user, collection)
    }
    return _ChatContext(
        provider_config_service=provider_config_service,
        collections=collections,
        roots=roots,
        selected_refs=selected_refs,
        roots_by_collection=roots_by_collection,
    )


def _request_log(
    *,
    request_id: str,
    current_user: User | None,
    request: Request,
    settings: Settings,
    started: float,
    status_value: str,
    collections: list[str],
    model: str,
    session_hash: str | None = None,
    error_code: str | None = None,
    conversation_id: int | None = None,
    citation_count: int = 0,
) -> AiRequestLog:
    return AiRequestLog(
        request_id=request_id,
        user_id=current_user.id if current_user is not None else None,
        session_hash=session_hash,
        ip_address=_client_ip(request),
        model=model,
        status=status_value,
        latency_ms=int((time.perf_counter() - started) * 1000),
        error_code=error_code,
        conversation_id=conversation_id,
        citation_count=citation_count,
        collection_scope=','.join(collections),
    )


class _ConversationVanished(RuntimeError):
    """영속화 시점에 ``conversation_id`` 재조회가 None 을 반환했다(삭제 레이스).

    스트림은 이미 헤더를 커밋한 뒤이므로 새 대화를 만들지 않고 ``persisted: false`` 로
    조용히 종결한다(``/chat`` 의 사전 404 계약과 달리, 중간에 삭제됐다고 새 대화를 여는
    것은 사용자가 요청하지 않은 부작용이다).
    """


def _persist_turn(
    *,
    db: Session,
    request: Request,
    payload: AiChatRequest,
    owner_session_id: str,
    answer: str,
    citation_dicts: list[dict[str, object]],
    raise_404_on_missing_conversation: bool,
) -> tuple[int, bool]:
    """``/chat`` 과 ``/chat/stream`` 이 공유하는 영속화 헬퍼(대화 upsert + append_turn).

    ``conversation_id`` 가 지정됐는데 조회 결과가 없으면:
    - ``raise_404_on_missing_conversation=True``(``/chat``): 진짜 HTTP 404 로 응답한다
      (헤더가 아직 나가지 않았으므로 가능하다).
    - ``False``(``/chat/stream``): ``_ConversationVanished`` 를 던져 호출부가 새 대화를
      만들지 않고 ``persisted: false`` 로 종결하게 한다(헤더가 이미 나간 뒤이므로 404 불가).
    """

    repo = AiConversationRepository(db)
    conversation: AiConversation | None = None
    if payload.conversation_id is not None:
        conversation = repo.get_conversation(owner_session_id, payload.conversation_id)
        if conversation is None:
            if raise_404_on_missing_conversation:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Conversation not found')
            raise _ConversationVanished('conversation was deleted during stream')
    if conversation is None:
        conversation = repo.create_conversation(owner_session_id, _client_ip(request), _title_from_messages(payload.messages))
    repo.append_turn(
        conversation,
        user_content=AiChatService.build_persisted_user_content(payload.messages, payload.attachments),
        assistant_content=answer,
        citations=citation_dicts,
    )
    db.commit()
    return conversation.id, True


def _sse_frame(event: str, data: dict[str, object]) -> str:
    return f'event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n'



def _title_from_messages(messages: list[AiChatMessage]) -> str:
    for message in messages:
        if message.role == 'user':
            text = message.content.strip().replace('\n', ' ')
            return (text[:60] + '…') if len(text) > 60 else text or '새 대화'
    return '새 대화'


def _conversation_summary(conversation: AiConversation) -> AiConversationSummary:
    return AiConversationSummary(
        id=conversation.id,
        title=conversation.title,
        is_pinned=conversation.is_pinned,
        is_archived=conversation.is_archived,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


def _conversation_detail(conversation: AiConversation) -> AiConversationDetail:
    return AiConversationDetail(
        id=conversation.id,
        title=conversation.title,
        is_pinned=conversation.is_pinned,
        is_archived=conversation.is_archived,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=[
            AiMessageOut(
                id=message.id,
                role=message.role,
                content=message.content,
                seq=message.seq,
                created_at=message.created_at,
                citations=[
                    AiCitation(
                        collection=citation.collection,
                        path=citation.path,
                        name=citation.name,
                        folder=citation.folder,
                        snippet=citation.snippet,
                        navigation_url=citation.navigation_url,
                    )
                    for citation in message.citations
                ],
            )
            for message in conversation.messages
        ],
    )


@router.get('/status', response_model=AiStatusResponse)
def get_ai_status(settings: Settings = Depends(get_settings), db: Session = Depends(get_db)) -> dict[str, object]:
    return AiChatService(settings, db, ProviderConfigService(db, settings)).status()


@router.post('/chat', response_model=AiChatResponse)
def chat_with_ai(
    payload: AiChatRequest,
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> AiChatResponse:
    ctx = _prepare_chat_context(payload, db, settings, current_user)
    started = time.perf_counter()
    request_id = uuid.uuid4().hex
    service = AiChatService(settings, db, ctx.provider_config_service)

    def log_failure(error_code: str) -> None:
        db.add(
            _request_log(
                request_id=request_id,
                current_user=current_user,
                request=request,
                settings=settings,
                started=started,
                status_value='error',
                collections=ctx.collections,
                model=service.effective_model(),
                error_code=error_code,
            )
        )
        db.flush()
        db.commit()

    try:
        answer, citations = service.chat(
            payload.messages,
            ctx.roots,
            use_search=payload.use_search,
            limit=payload.limit,
            selected_refs=ctx.selected_refs,
            roots_by_collection=ctx.roots_by_collection,
            attachments=payload.attachments,
        )
    except OllamaModelMissing as exc:
        log_failure(exc.__class__.__name__)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except OllamaUnavailable as exc:
        log_failure(exc.__class__.__name__)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except OllamaEmptyResponse as exc:
        # 연결 다운(503)이 아니라 모델이 빈 응답을 준 경우 — 502 Bad Gateway 로 구분.
        log_failure(exc.__class__.__name__)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    citation_dicts = [result.as_dict() for result in citations]
    conversation_id: int | None = None
    persisted = False
    owner_session_id: str | None = None
    # 임시 대화 또는 영속화 비활성 시 DB 저장 없음(임시성 원칙).
    if settings.ai_persistence_enabled and not payload.temporary:
        owner_session_id = _owner_session(request, response, settings)
        conversation_id, persisted = _persist_turn(
            db=db,
            request=request,
            payload=payload,
            owner_session_id=owner_session_id,
            answer=answer,
            citation_dicts=citation_dicts,
            raise_404_on_missing_conversation=True,
        )
    session_hash = None
    if owner_session_id:
        session_hash = sha256(owner_session_id.encode('utf-8')).hexdigest()[:64]
    effective_model = service.effective_model()
    db.add(
        _request_log(
            request_id=request_id,
            current_user=current_user,
            request=request,
            settings=settings,
            started=started,
            status_value='ok',
            collections=ctx.collections,
            model=effective_model,
            session_hash=session_hash,
            conversation_id=conversation_id,
            citation_count=len(citation_dicts),
        )
    )
    db.flush()

    return AiChatResponse(
        model=effective_model,
        message=AiChatMessage(role='assistant', content=answer),
        citations=[AiCitation(**result) for result in citation_dicts],
        conversation_id=conversation_id,
        persisted=persisted,
    )


_STREAM_ERROR_STATUS: dict[type[Exception], int] = {
    OllamaModelMissing: status.HTTP_503_SERVICE_UNAVAILABLE,
    OllamaUnavailable: status.HTTP_503_SERVICE_UNAVAILABLE,
    OllamaEmptyResponse: status.HTTP_502_BAD_GATEWAY,
}


@router.post('/chat/stream')
def chat_stream_with_ai(
    payload: AiChatRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> StreamingResponse:
    # 사전 게이트(ai.use 403)는 스트리밍 시작 전, 즉 여기서(동기) 발생한다 — 헤더가 아직
    # 전송되지 않았으므로 진짜 HTTP 403 으로 응답한다.
    ctx = _prepare_chat_context(payload, db, settings, current_user)
    started = time.perf_counter()
    request_id = uuid.uuid4().hex
    persistence_enabled = settings.ai_persistence_enabled and not payload.temporary
    # FastAPI 는 직접 반환한 Response(StreamingResponse) 에는 주입된 ``response: Response``
    # 의존성 헤더를 병합하지 않는다 — 쿠키는 실제로 반환하는 StreamingResponse 인스턴스에
    # 직접 설정해야 한다. ``owner_session_id`` 는 제너레이터가 실행되기 전(=응답 생성 직후)
    # nonlocal 로 채워 넣는다 — 제너레이터 자체는 지연 평가되므로 안전하다.
    owner_session_id: str | None = None

    def event_stream() -> Generator[str, None, None]:
        nonlocal owner_session_id
        service = AiChatService(settings, db, ctx.provider_config_service)
        citations: list = []
        collection_scope = ctx.collections


        def log(status_value: str, *, error_code: str | None = None, conversation_id: int | None = None, session_hash: str | None = None) -> None:
            db.add(
                _request_log(
                    request_id=request_id,
                    current_user=current_user,
                    request=request,
                    settings=settings,
                    started=started,
                    status_value=status_value,
                    collections=collection_scope,
                    model=service.effective_model(),
                    error_code=error_code,
                    conversation_id=conversation_id,
                    citation_count=len(citations),
                    session_hash=session_hash,
                )
            )
            db.flush()
            db.commit()

        try:
            generator = service.chat_stream(
                payload.messages,
                ctx.roots,
                use_search=payload.use_search,
                limit=payload.limit,
                selected_refs=ctx.selected_refs,
                roots_by_collection=ctx.roots_by_collection,
                attachments=payload.attachments,
            )
            final_answer: str | None = None
            for kind, value in generator:
                if kind == 'citations':
                    citations = value
                    if citations:
                        yield _sse_frame('citations', {'citations': [result.as_dict() for result in citations]})
                elif kind == 'delta':
                    yield _sse_frame('delta', {'content': value})
                elif kind == 'final':
                    final_answer = value
        except GeneratorExit:
            # 클라이언트가 연결을 끊어 이 제너레이터가 닫혔다 — yield 는 절대 금지(RuntimeError
            # 유발)이므로 감사 로그만 남기고 그대로 재전파한다.
            log('aborted', error_code='ClientAborted')
            raise
        except (OllamaModelMissing, OllamaUnavailable, OllamaEmptyResponse) as exc:
            http_status = _STREAM_ERROR_STATUS[type(exc)]
            log('error', error_code=exc.__class__.__name__)
            yield _sse_frame('error', {'detail': str(exc), 'status': http_status})
            return
        except Exception as exc:  # noqa: BLE001 - 스트림 바디는 이미 커밋됐으므로 안전망으로 error 프레임만 낸다.
            log('error', error_code=exc.__class__.__name__)
            yield _sse_frame('error', {'detail': 'internal error', 'status': status.HTTP_502_BAD_GATEWAY})
            return

        if final_answer is None:
            log('error', error_code='StreamIncomplete')
            yield _sse_frame('error', {'detail': 'stream ended without a final answer', 'status': status.HTTP_502_BAD_GATEWAY})
            return

        citation_dicts = [result.as_dict() for result in citations]
        conversation_id: int | None = None
        persisted = False
        persist_error: str | None = None
        # 스트림 완결 후에만 append_turn 한다(기존 규칙 동일: ai_persistence_enabled && !temporary).
        if persistence_enabled and owner_session_id is not None:
            try:
                conversation_id, persisted = _persist_turn(
                    db=db,
                    request=request,
                    payload=payload,
                    owner_session_id=owner_session_id,
                    answer=final_answer,
                    citation_dicts=citation_dicts,
                    raise_404_on_missing_conversation=False,
                )
            except Exception as exc:  # noqa: BLE001 - 헤더가 이미 나간 뒤이므로 done 계약을 지킨다(예외를 밖으로 던지지 않는다).
                db.rollback()
                conversation_id = None
                persisted = False
                persist_error = str(exc) or exc.__class__.__name__

        session_hash = sha256(owner_session_id.encode('utf-8')).hexdigest()[:64] if owner_session_id else None
        effective_model = service.effective_model()
        if persist_error is not None:
            log('error', error_code='PersistFailed', session_hash=session_hash)
        else:
            log('ok', conversation_id=conversation_id, session_hash=session_hash)

        done_payload: dict[str, object] = {
            'model': effective_model,
            'conversation_id': conversation_id,
            'persisted': persisted,
        }
        if persist_error is not None:
            done_payload['persist_error'] = persist_error
        yield _sse_frame('done', done_payload)

    stream_response = StreamingResponse(
        event_stream(),
        media_type='text/event-stream',
        headers={'Cache-Control': 'no-store'},
    )
    if persistence_enabled:
        owner_session_id = _owner_session(request, stream_response, settings)
        # /chat 과 동일 계약: 미존재 conversation_id 는 스트림 시작 전 진짜 HTTP 404.
        # (스트림 도중에는 헤더가 이미 나가 404 를 줄 수 없어, 여기서 사전 검증한다.)
        if payload.conversation_id is not None:
            existing = AiConversationRepository(db).get_conversation(owner_session_id, payload.conversation_id)
            if existing is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Conversation not found')
    return stream_response

@router.get('/conversations', response_model=AiConversationListResponse)
def list_conversations(
    request: Request,
    response: Response,
    include_archived: bool = False,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> AiConversationListResponse:
    # 쿠키가 없으면 빈 이력. 새 세션을 발급해 이후 대화가 묶이도록 한다.
    session_id = _owner_session(request, response, settings)
    repo = AiConversationRepository(db)
    conversations = repo.list_conversations(session_id, include_archived=include_archived)
    return AiConversationListResponse(
        conversations=[_conversation_summary(item) for item in conversations]
    )


@router.get('/conversations/{conversation_id}', response_model=AiConversationDetail)
def get_conversation(
    conversation_id: int,
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> AiConversationDetail:
    session_id = _owner_session(request, response, settings)
    conversation = AiConversationRepository(db).get_conversation(session_id, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Conversation not found')
    return _conversation_detail(conversation)


@router.patch('/conversations/{conversation_id}', response_model=AiConversationSummary)
def update_conversation(
    conversation_id: int,
    payload: AiConversationUpdate,
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> AiConversationSummary:
    session_id = _owner_session(request, response, settings)
    repo = AiConversationRepository(db)
    conversation = repo.update_conversation(
        session_id,
        conversation_id,
        title=payload.title,
        is_pinned=payload.is_pinned,
        is_archived=payload.is_archived,
    )
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Conversation not found')
    db.commit()
    return _conversation_summary(conversation)


@router.delete('/conversations/{conversation_id}')
def delete_conversation(
    conversation_id: int,
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    session_id = _owner_session(request, response, settings)
    deleted = AiConversationRepository(db).delete_conversation(session_id, conversation_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Conversation not found')
    db.commit()
    return {'deleted': True}