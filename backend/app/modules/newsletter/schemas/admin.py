from __future__ import annotations

from pydantic import BaseModel


class ThumbnailUploadResponse(BaseModel):
    thumbnail_path: str
