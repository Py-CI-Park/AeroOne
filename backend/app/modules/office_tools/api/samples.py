"""samples 서브라우터 — 각 스튜디오의 즉시 체험용 샘플 예제.

``GET /samples`` 는 지원 도구 목록을, ``GET /samples/{tool}`` 은 해당 도구의 샘플
내용 + 폼 프리필 힌트를 돌려준다. 프런트 '예제 불러오기' 버튼이 이를 받아 폼을
채우고 바로 실행할 수 있게 한다. 상위 라우터가 세션 로그인을 강제하므로 미로그인은 401.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.modules.office_tools import samples_service
from app.modules.office_tools.schemas import OfficeSampleResponse

router = APIRouter(tags=['office-tools'])


@router.get('', response_model=list[OfficeSampleResponse])
def list_samples() -> list[OfficeSampleResponse]:
    """지원하는 모든 도구의 샘플을 돌려준다."""

    return [OfficeSampleResponse(**samples_service.get_sample(tool)) for tool in samples_service.available_tools()]


@router.get('/{tool}', response_model=OfficeSampleResponse)
def get_sample(tool: str) -> OfficeSampleResponse:
    """도구 하나의 샘플 내용 + 힌트를 돌려준다. 미지원 도구는 404."""

    try:
        return OfficeSampleResponse(**samples_service.get_sample(tool))
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'unknown sample tool: {tool}') from exc
