"""diagrams 서브라우터 — 다이어그램 스튜디오(svc03).

``POST /generate`` 는 설명 + 유형(flowchart/sequence/state/gantt)을 받아
``services/diagram_service.py`` 로 **Mermaid 소스(.mmd)만** 산출한다(브라우저 렌더).
서버는 ``security.validate_mermaid`` 로 실행 지시어(click/javascript:/<script> 등)를
차단하고 소스만 JobStore 에 등록한다. cairosvg PNG export 는 없다.

AI 보조(``ai_assist``)는 ``core.llm_bridge`` 의 활성 연결을 우선 사용하고, 없거나
실패하면 규칙 기반 폴백으로 내려간다(경고 첨부). 상위 라우터가 세션 로그인을
강제하므로 미로그인은 401 이다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.auth.dependencies import get_current_user, get_db, get_settings
from app.modules.auth.models import User
from app.modules.office_tools.api.jobs import get_office_job_store
from app.modules.office_tools.core import llm_bridge
from app.modules.office_tools.core.job_store import OfficeJobStore
from app.modules.office_tools.schemas import DiagramGenerateRequest, DiagramGenerateResponse
from app.modules.office_tools.services.diagram_service import generate_diagram

router = APIRouter(tags=['office-tools'])


@router.post('/generate', response_model=DiagramGenerateResponse)
def generate(
    request: DiagramGenerateRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    store: OfficeJobStore = Depends(get_office_job_store),
    user: User = Depends(get_current_user),
) -> DiagramGenerateResponse:
    """설명을 Mermaid 소스로 생성한다. 잘못된/금지된 소스는 422."""

    client = llm_bridge.resolve_active_client(db, settings)
    try:
        record = generate_diagram(
            store=store,
            owner_id=user.id,
            request=request,
            client=client,
            app_version=settings.app_version,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return DiagramGenerateResponse(
        job_id=record['job_id'],
        status=record['status'],
        title=record['title'],
        diagram_type=record['diagram_type'],
        mermaid=record['mermaid'],
        warnings=record.get('warnings', []),
        artifacts=record.get('artifacts', []),
        preview_url=record['preview_url'],
        bundle_url=record['bundle_url'],
    )
