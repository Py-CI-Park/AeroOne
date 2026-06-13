from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AiChatMessage(BaseModel):
    role: Literal['system', 'user', 'assistant']
    content: str = Field(min_length=1, max_length=12000)


class AiChatRequest(BaseModel):
    messages: list[AiChatMessage] = Field(min_length=1, max_length=20)
    use_search: bool = False
    collections: list[Literal['document', 'civil', 'nsa']] | None = None
    limit: int = Field(default=5, ge=1, le=12)


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


class AiStatusResponse(BaseModel):
    enabled: bool
    base_url: str
    model: str
    reachable: bool
    model_available: bool
    status: Literal['ok', 'disabled', 'unavailable', 'model_missing']
    detail: str | None = None
