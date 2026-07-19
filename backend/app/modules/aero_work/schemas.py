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
    query: str = Field(min_length=1, max_length=2000)
    folder_id: int | None = None
    top_k: int = Field(default=8, ge=1, le=30)


class SearchHit(BaseModel):
    folder_id: int
    folder_name: str
    rel_path: str
    chunk_index: int
    content: str
    score: float
    is_latest: bool = False


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
    remind_before_minutes: int | None = None


class EventUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    all_day: bool | None = None
    location: str | None = Field(default=None, max_length=300)
    notes: str | None = None
    remind_before_minutes: int | None = None


class EventResponse(BaseModel):
    id: int
    title: str
    starts_at: datetime
    ends_at: datetime | None
    all_day: bool
    location: str
    notes: str
    remind_before_minutes: int | None

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
            remind_before_minutes=event.remind_before_minutes,
        )


class EventListResponse(BaseModel):
    events: list[EventResponse]


class ActivityResponse(BaseModel):
    id: int
    kind: str
    summary: str
    detail: str
    created_at: datetime

    @classmethod
    def from_model(cls, activity) -> 'ActivityResponse':
        return cls(
            id=activity.id,
            kind=activity.kind,
            summary=activity.summary,
            detail=activity.detail,
            created_at=activity.created_at,
        )


class ActivityListResponse(BaseModel):
    activities: list[ActivityResponse]


class DocumentRequest(BaseModel):
    title: str = Field(default='', max_length=300)
    body: str = Field(default='', max_length=100000)
    format: str = Field(default='onepage', max_length=20)


class OrchestrateRequest(BaseModel):
    utterance: str = Field(min_length=1, max_length=2000)
    session_id: int | None = None
    synthesize: bool = True


class DocumentIntent(BaseModel):
    format: str
    title: str
    content: str


class OrchestrateResult(BaseModel):
    kind: str
    summary: str
    events: list[EventResponse] = Field(default_factory=list)
    hits: list[SearchHit] = Field(default_factory=list)
    document: DocumentIntent | None = None
    feature: str | None = None
    answer: str = ''


class OrchestrateResponse(BaseModel):
    utterance: str
    session_id: int | None = None
    results: list[OrchestrateResult]


class WikiFile(BaseModel):
    id: int = 0
    summary: str = ''
    folder_id: int
    folder_name: str
    rel_path: str
    chunk_count: int
    is_latest: bool = False


class WikiFamily(BaseModel):
    base: str
    representative: WikiFile
    items: list[WikiFile]
    has_versions: bool


class WikiResponse(BaseModel):
    families: list[WikiFamily]


class ChatHistoryItem(BaseModel):
    id: int
    utterance: str
    results: list[OrchestrateResult]
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    items: list[ChatHistoryItem]


class DocumentComposeRequest(BaseModel):
    title: str = Field(default='', max_length=300)
    instruction: str = Field(min_length=1, max_length=10000)
    format: str = Field(default='onepage', max_length=20)


class DocumentComposeResponse(BaseModel):
    paragraphs: list[str]


class PrefResponse(BaseModel):
    llm_mode: str


class PrefUpdateRequest(BaseModel):
    llm_mode: str = Field(pattern='^(default|local)$')


class SavedDocumentResponse(BaseModel):
    id: int
    title: str
    format: str
    status: str
    created_at: datetime

    @classmethod
    def from_model(cls, doc) -> 'SavedDocumentResponse':
        return cls(id=doc.id, title=doc.title, format=doc.format, status=doc.status, created_at=doc.created_at)


class SavedDocumentListResponse(BaseModel):
    documents: list[SavedDocumentResponse]


class ChatSessionResponse(BaseModel):
    id: int
    title: str
    updated_at: datetime


class ChatSessionListResponse(BaseModel):
    sessions: list[ChatSessionResponse]


class FileSummaryResponse(BaseModel):
    summary: str


class TaxonomyProposeRequest(BaseModel):
    organization: str = Field(min_length=1, max_length=200)
    department: str = Field(min_length=1, max_length=200)
    duties: str = Field(min_length=1, max_length=2000)


class TaxonomyCategoryInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default='', max_length=2000)
    file_ids: list[int] = Field(default_factory=list, max_length=500)


class TaxonomyProposeResponse(BaseModel):
    candidates: list[TaxonomyCategoryInput]
    model: str


class TaxonomyApplyRequest(BaseModel):
    categories: list[TaxonomyCategoryInput] = Field(default_factory=list, max_length=100)


class TaxonomyApplyResponse(BaseModel):
    applied: int


class TaxonomyCategoryFile(BaseModel):
    id: int
    rel_path: str
    folder_name: str
    summary: str


class TaxonomyCategoryResponse(BaseModel):
    id: int
    name: str
    description: str
    sort_order: int
    files: list[TaxonomyCategoryFile]


class TaxonomyResponse(BaseModel):
    categories: list[TaxonomyCategoryResponse]
