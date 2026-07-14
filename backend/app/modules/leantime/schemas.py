from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


def _validate_base_url(value: str | None) -> str | None:
    """http/https 스킴만 허용한다(내부망 IP/도메인 모두 통과, 파일/기타 스킴 거부)."""

    if value is None:
        return None
    cleaned = value.strip()
    if not (cleaned.startswith('http://') or cleaned.startswith('https://')):
        raise ValueError('base_url must start with http:// or https://')
    return cleaned


class LeantimeConnectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    base_url: str = Field(min_length=1, max_length=500)
    api_key: str = Field(default='', max_length=2000)
    is_enabled: bool = True
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


class LeantimeConnectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    base_url: str | None = Field(default=None, min_length=1, max_length=500)
    api_key: str | None = Field(default=None, max_length=2000)
    is_enabled: bool | None = None
    verify_tls: bool | None = None

    @field_validator('base_url')
    @classmethod
    def _check_base_url(cls, value: str | None) -> str | None:
        return _validate_base_url(value)


class LeantimeConnectionResponse(BaseModel):
    id: int
    name: str
    base_url: str
    is_enabled: bool
    verify_tls: bool
    api_key_masked: str
    created_at: datetime
    updated_at: datetime


class LeantimeProject(BaseModel):
    """Leantime 프로젝트 목록 항목 — 원본 필드를 방어적으로 정규화한 결과만 담는다."""

    id: str
    name: str
    state: str | None = None
    client_name: str | None = None


class LeantimeTask(BaseModel):
    """Leantime 티켓/태스크 목록 항목."""

    id: str
    project_id: str | None = None
    headline: str
    status: str | None = None
    date_to_finish: str | None = None


class LeantimeCalendarEntry(BaseModel):
    """Leantime 캘린더 항목."""

    id: str
    name: str
    date_start: str | None = None
    date_end: str | None = None


class LeantimeReadResponse(BaseModel):
    """읽기 엔드포인트 공통 응답 봉투 — 실패 시에도 200 으로 degraded 상태를 알린다.

    ``items`` 는 요청한 리소스 타입에 맞는 DTO 리스트이며, 시크릿 필드는 절대 포함하지
    않는다(``LeantimeConnection.api_key_encrypted``/복호화된 키 모두 여기 들어오지 않는다).
    """

    items: list[LeantimeProject] | list[LeantimeTask] | list[LeantimeCalendarEntry]
    degraded: bool = False
    reason: str | None = None
    source: str = 'leantime'
    fetched_at: str
