"""Aero Work 지식폴더 API 스키마."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.aero_work.models import KnowledgeFolder


class FolderRegisterRequest(BaseModel):
    name: str = Field(default='', max_length=200)
    path: str = Field(min_length=1)


class FolderResponse(BaseModel):
    id: int
    name: str
    path: str
    status: str
    status_detail: str
    file_count: int
    chunk_count: int
    last_indexed_at: datetime | None

    @classmethod
    def from_model(cls, folder: KnowledgeFolder) -> 'FolderResponse':
        return cls(
            id=folder.id,
            name=folder.name,
            path=folder.path,
            status=folder.status,
            status_detail=folder.status_detail,
            file_count=folder.file_count,
            chunk_count=folder.chunk_count,
            last_indexed_at=folder.last_indexed_at,
        )


class FolderListResponse(BaseModel):
    folders: list[FolderResponse]


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    folder_id: int | None = None
    top_k: int = Field(default=8, ge=1, le=30)


class SearchHit(BaseModel):
    folder_id: int
    folder_name: str
    rel_path: str
    chunk_index: int
    content: str
    score: float


class SearchResponse(BaseModel):
    hits: list[SearchHit]
    model: str


class EventCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    starts_at: datetime
    ends_at: datetime | None = None
    all_day: bool = False
    location: str = Field(default='', max_length=300)
    notes: str = ''


class EventUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    all_day: bool | None = None
    location: str | None = Field(default=None, max_length=300)
    notes: str | None = None


class EventResponse(BaseModel):
    id: int
    title: str
    starts_at: datetime
    ends_at: datetime | None
    all_day: bool
    location: str
    notes: str

    @classmethod
    def from_model(cls, event) -> 'EventResponse':
        return cls(
            id=event.id,
            title=event.title,
            starts_at=event.starts_at,
            ends_at=event.ends_at,
            all_day=event.all_day,
            location=event.location,
            notes=event.notes,
        )


class EventListResponse(BaseModel):
    events: list[EventResponse]
