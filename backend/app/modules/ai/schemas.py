from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AiChatMessage(BaseModel):
    role: Literal['system', 'user', 'assistant']
    content: str = Field(min_length=1, max_length=12000)


class AiSelectedRef(BaseModel):
    collection: Literal['document', 'civil', 'nsa']
    path: str = Field(min_length=1, max_length=1000)


class AiChatRequest(BaseModel):
    messages: list[AiChatMessage] = Field(min_length=1, max_length=20)
    use_search: bool = False
    collections: list[Literal['document', 'civil', 'nsa']] | None = None
    limit: int = Field(default=5, ge=1, le=12)
    conversation_id: int | None = None
    temporary: bool = False
    selected_refs: list[AiSelectedRef] = Field(default_factory=list, max_length=12)


class AiCitation(BaseModel):
    collection: Literal['document', 'civil', 'nsa']
    path: str
    name: str
    folder: str
    snippet: str
    navigation_url: str


class AiChatResponse(BaseModel):
    model: str
    message: AiChatMessage
    citations: list[AiCitation] = []
    conversation_id: int | None = None
    persisted: bool = False


class AiStatusResponse(BaseModel):
    enabled: bool
    base_url: str
    model: str
    reachable: bool
    model_available: bool
    status: Literal['ok', 'disabled', 'unavailable', 'model_missing']
    detail: str | None = None

class AiConversationSummary(BaseModel):
    id: int
    title: str
    is_pinned: bool
    is_archived: bool
    created_at: datetime
    updated_at: datetime


class AiConversationListResponse(BaseModel):
    conversations: list[AiConversationSummary] = []


class AiMessageOut(BaseModel):
    id: int
    role: str
    content: str
    seq: int
    created_at: datetime
    citations: list[AiCitation] = []


class AiConversationDetail(AiConversationSummary):
    messages: list[AiMessageOut] = []


class AiConversationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    is_pinned: bool | None = None
    is_archived: bool | None = None
