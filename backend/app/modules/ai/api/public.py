from __future__ import annotations

import uuid
import time
from hashlib import sha256
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
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
    # 명시적 provider 선택만 신뢰한다(요청 시점 폴백 금지). openai_compatible 이 선택된
    # 경우에만 활성 인증 사용자의 정확한 ai.use 권한을 사전 게이트한다 — Ollama 경로는
    # 익명 접근을 포함해 기존 동작을 그대로 보존한다.
    provider_state = ProviderConfigService(db, settings).get_state()
    if provider_state.selected_kind == 'openai_compatible':
        if current_user is None or not current_user.is_active or not has_permission(db, current_user, 'ai.use'):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='ai_use_required')
    started = time.perf_counter()
    request_id = uuid.uuid4().hex
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
    def log_failure(error_code: str) -> None:
        db.add(
            AiRequestLog(
                request_id=request_id,
                user_id=current_user.id if current_user is not None else None,
                session_hash=None,
                ip_address=_client_ip(request),
                model=settings.ollama_default_model,
                status='error',
                latency_ms=int((time.perf_counter() - started) * 1000),
                error_code=error_code,
                citation_count=0,
                collection_scope=','.join(collections),
            )
        )
        db.flush()
        db.commit()

    try:
        answer, citations = AiChatService(settings, db, ProviderConfigService(db, settings)).chat(
            payload.messages,
            roots,
            use_search=payload.use_search,
            limit=payload.limit,
            selected_refs=selected_refs,
            roots_by_collection=roots_by_collection,
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
        session_id = owner_session_id
        repo = AiConversationRepository(db)
        conversation: AiConversation | None = None
        if payload.conversation_id is not None:
            conversation = repo.get_conversation(session_id, payload.conversation_id)
            if conversation is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Conversation not found')
        if conversation is None:
            conversation = repo.create_conversation(
                session_id,
                _client_ip(request),
                _title_from_messages(payload.messages),
            )
        repo.append_turn(
            conversation,
            user_content=AiChatService._last_user_message(payload.messages),
            assistant_content=answer,
            citations=citation_dicts,
        )
        db.commit()
        conversation_id = conversation.id
        persisted = True
    session_hash = None
    if owner_session_id:
        session_hash = sha256(owner_session_id.encode('utf-8')).hexdigest()[:64]
    db.add(
        AiRequestLog(
            request_id=request_id,
            user_id=current_user.id if current_user is not None else None,
            session_hash=session_hash,
            ip_address=_client_ip(request),
            model=settings.ollama_default_model,
            status='ok',
            latency_ms=int((time.perf_counter() - started) * 1000),
            conversation_id=conversation_id,
            citation_count=len(citation_dicts),
            collection_scope=','.join(collections),
        )
    )
    db.flush()

    return AiChatResponse(
        model=settings.ollama_default_model,
        message=AiChatMessage(role='assistant', content=answer),
        citations=[AiCitation(**result) for result in citation_dicts],
        conversation_id=conversation_id,
        persisted=persisted,
    )


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