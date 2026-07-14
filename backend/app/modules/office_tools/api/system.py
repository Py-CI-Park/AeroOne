"""system 서브라우터 — 상태(health)와 능력(capabilities).

두 엔드포인트 모두 상위 라우터의 로그인 의존성 아래에 있다(미로그인 401).
capabilities 는 활성 LLM 여부만 노출하고 base_url/api_key 는 절대 노출하지 않는다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.auth.dependencies import get_db, get_settings
from app.modules.office_tools.core import llm_bridge
from app.modules.office_tools.schemas import (
    OfficeCapabilities,
    OfficeHealth,
    OfficeLlmCapability,
    OfficeServiceFlags,
)

router = APIRouter(tags=['office-tools'])

# 도구별 서버 검증 상한(각 도구 구현 단계에서 실제 강제). capabilities 로 프런트에 노출한다.
_DEFAULT_LIMITS: dict[str, int] = {
    'max_upload_mb': 20,
    'max_markdown_chars': 200_000,
    'max_data_rows': 100_000,
}


@router.get('/health', response_model=OfficeHealth)
def health(settings: Settings = Depends(get_settings)) -> OfficeHealth:
    return OfficeHealth(status='ok', service=settings.app_name)


@router.get('/capabilities', response_model=OfficeCapabilities)
def capabilities(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> OfficeCapabilities:
    llm = llm_bridge.describe_capabilities(db, settings)
    return OfficeCapabilities(
        services=OfficeServiceFlags(report=True, chart=True, diagram=True),
        llm=OfficeLlmCapability(
            active=bool(llm['active']),
            default_model=llm['default_model'],  # type: ignore[arg-type]
            fallback=str(llm['fallback']),
        ),
        limits=dict(_DEFAULT_LIMITS),
    )
