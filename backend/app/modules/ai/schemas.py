from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


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


def _validate_base_url(value: str | None) -> str | None:
    """http/https 스킴만 허용한다(내부망 IP/도메인 모두 통과, 파일/기타 스킴 거부)."""

    if value is None:
        return None
    cleaned = value.strip()
    if not (cleaned.startswith('http://') or cleaned.startswith('https://')):
        raise ValueError('base_url must start with http:// or https://')
    return cleaned


class LlmConnectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    base_url: str = Field(min_length=1, max_length=500)
    api_key: str = Field(default='', max_length=2000)
    default_model: str | None = Field(default=None, max_length=160)
    is_enabled: bool = True
    is_default: bool = False
    verify_tls: bool = True

    @field_validator('name')
    @classmethod
    def _strip_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError('name is required')
        return cleaned

    @field_validator('base_url')
    @classmethod
    def _check_base_url(cls, value: str) -> str:
        checked = _validate_base_url(value)
        assert checked is not None  # min_length=1 이라 None 이 될 수 없다.
        return checked


class LlmConnectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    base_url: str | None = Field(default=None, min_length=1, max_length=500)
    api_key: str | None = Field(default=None, max_length=2000)
    default_model: str | None = Field(default=None, max_length=160)
    is_enabled: bool | None = None
    is_default: bool | None = None
    verify_tls: bool | None = None

    @field_validator('base_url')
    @classmethod
    def _check_base_url(cls, value: str | None) -> str | None:
        return _validate_base_url(value)


class LlmConnectionResponse(BaseModel):
    id: int
    name: str
    base_url: str
    default_model: str | None
    is_enabled: bool
    is_default: bool
    verify_tls: bool
    api_key_masked: str
    created_at: datetime
    updated_at: datetime


class LlmVerifyResponse(BaseModel):
    ok: bool
    models: list[str] = []
    detail: str | None = None
