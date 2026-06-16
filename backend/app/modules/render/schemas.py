from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RenderRequest(BaseModel):
    # 폐쇄망 stateless 렌더 입력. 파일/경로 파라미터를 일절 받지 않으며,
    # 몰래 끼워넣은 file/path 필드는 extra='forbid' 로 422 거부한다.
    model_config = ConfigDict(extra='forbid')

    type: Literal['markdown', 'html']
    # 렌더 DoS 를 막기 위해 입력 길이를 1MB 로 제한한다.
    text: str = Field(max_length=1_000_000)
