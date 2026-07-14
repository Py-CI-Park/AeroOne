"""samples 서브라우터 — 각 스튜디오의 즉시 체험용 샘플 예제(도구별 여러 종).

``GET /samples`` 는 모든 도구의 모든 샘플(내용 + 폼 프리필 힌트)을, ``GET /samples/{key}``
는 key 로 지정한 샘플 하나를 돌려준다. 프런트는 목록을 받아 도구별 '예제' 칩으로 보여 주고,
사용자가 고르면 그 내용으로 폼을 채운다. 상위 라우터가 세션 로그인을 강제하므로 미로그인은 401.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.modules.office_tools import samples_service
from app.modules.office_tools.schemas import OfficeSampleResponse

router = APIRouter(tags=['office-tools'])


@router.get('', response_model=list[OfficeSampleResponse])
def list_samples() -> list[OfficeSampleResponse]:
    """모든 도구의 모든 샘플을 돌려준다."""

    return [OfficeSampleResponse(**sample) for sample in samples_service.all_samples()]


@router.get('/{key}', response_model=OfficeSampleResponse)
def get_sample(key: str) -> OfficeSampleResponse:
    """key 로 샘플 하나를 돌려준다. 미지원 key 는 404."""

    try:
        return OfficeSampleResponse(**samples_service.get_sample(key))
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'unknown sample: {key}') from exc
