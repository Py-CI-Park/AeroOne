from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings
from app.modules.ai.schemas import AiChatRequest, AiChatResponse, AiCitation, AiChatMessage, AiStatusResponse
from app.modules.ai.service import AiChatService, OllamaModelMissing, OllamaUnavailable
from app.modules.auth.dependencies import get_settings
from app.modules.collections.search_service import ALL_SEARCH_COLLECTIONS, DEFAULT_SEARCH_COLLECTIONS, CollectionSearchRoot


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


@router.get('/status', response_model=AiStatusResponse)
def get_ai_status(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    return AiChatService(settings).status()


@router.post('/chat', response_model=AiChatResponse)
def chat_with_ai(
    payload: AiChatRequest,
    settings: Settings = Depends(get_settings),
) -> AiChatResponse:
    collections = _requested_collections(payload.collections)
    roots = [
        CollectionSearchRoot(collection=collection, root=_resolve_collection_root(collection, settings))
        for collection in collections
    ]
    try:
        answer, citations = AiChatService(settings).chat(
            payload.messages,
            roots,
            use_search=payload.use_search,
            limit=payload.limit,
        )
    except OllamaModelMissing as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except OllamaUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return AiChatResponse(
        model=settings.ollama_default_model,
        message=AiChatMessage(role='assistant', content=answer),
        citations=[AiCitation(**result.as_dict()) for result in citations],
    )
