"""charts 서브라우터 — 차트 스튜디오(svc02).

``POST /inspect`` 은 데이터 파일(.csv/.xlsx/.json) 을 받아 pandas 프로필(행/열/샘플)만
돌려준다(job 미생성). ``POST /generate`` 는 데이터 + 목적 문장 + 옵션을 받아 pandas 로
집계하고 **브라우저 ECharts option(JSON)만** 산출한다(서버 SVG/PNG 없음). 산출물은
JobStore 에 ``chart_data.csv`` / ``chart_spec.json`` / ``echarts_option.json`` / ``manifest.json``
으로 등록한다.

AI 보조(``ai_assist``)는 ``core.llm_bridge`` 의 활성 연결을 우선 쓰고, 없거나 실패하면
규칙 기반 폴백으로 내려간다(경고 첨부). 상위 라우터가 세션 로그인과 ``office.use`` 를
강제하므로 미로그인은 401, 권한 없이는 403 이다. 업로드를 처리하는 ``POST /inspect`` 와
JobStore 를 변경하는 ``POST /generate`` 는 ``require_csrf`` 도 요구하며 유효하지 않은 CSRF 는
403 이다. 업로드 크기 초과는 413, 미지원 확장자/행수 초과/잘못된 수동 스펙은 422 로 거부한다.
"""

from __future__ import annotations

from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.auth.dependencies import get_current_user, get_db, get_settings, require_csrf
from app.modules.auth.models import User
from app.modules.office_tools.api.jobs import get_office_job_store
from app.modules.office_tools.core import llm_bridge
from app.modules.office_tools.core.job_store import OfficeJobStore
from app.modules.office_tools.schemas import (
    CHART_DATA_SUFFIXES,
    MAX_CHART_DATA_ROWS,
    MAX_CHART_UPLOAD_BYTES,
    ChartGenerateResponse,
    ChartInspectResponse,
    ChartType,
)
from app.modules.office_tools.services.chart import generate_chart, inspect_data
from app.modules.office_tools.services.report.assets import UploadSizeLimitExceeded, read_bounded_bytes

router = APIRouter(tags=['office-tools'])


def _require_data_suffix(filename: str | None) -> None:
    """확장자 화이트리스트를 라우트에서 먼저 강제한다(422)."""

    suffix = PurePosixPath(filename or '').suffix.lower()
    if suffix not in CHART_DATA_SUFFIXES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f'지원하지 않는 데이터 확장자입니다: {suffix or "(없음)"}',
        )


@router.post('/inspect', response_model=ChartInspectResponse, dependencies=[Depends(require_csrf)])
def inspect(
    data_file: UploadFile = File(...),
) -> ChartInspectResponse:
    """데이터 파일의 프로필(행/열/샘플)을 반환한다. 업로드 크기 초과는 413이다."""

    _require_data_suffix(data_file.filename)
    try:
        data = read_bounded_bytes(data_file.file, max_bytes=MAX_CHART_UPLOAD_BYTES)
        profile = inspect_data(
            filename=data_file.filename or 'data.csv',
            data=data,
            max_upload_bytes=MAX_CHART_UPLOAD_BYTES,
            max_data_rows=MAX_CHART_DATA_ROWS,
        )
    except UploadSizeLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return ChartInspectResponse(**profile)


@router.post('/generate', response_model=ChartGenerateResponse, dependencies=[Depends(require_csrf)])
def generate(
    data_file: UploadFile = File(...),
    prompt: str = Form(default=''),
    ai_assist: bool = Form(default=True),
    chart_type: ChartType | None = Form(default=None),
    manual_spec_json: str = Form(default=''),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    store: OfficeJobStore = Depends(get_office_job_store),
    user: User = Depends(get_current_user),
) -> ChartGenerateResponse:
    """데이터를 ECharts option 으로 집계한다. 업로드 크기 초과는 413이다."""

    _require_data_suffix(data_file.filename)
    try:
        data = read_bounded_bytes(data_file.file, max_bytes=MAX_CHART_UPLOAD_BYTES)
        record = generate_chart(
            store=store,
            owner_id=user.id,
            filename=data_file.filename or 'data.csv',
            data=data,
            prompt=prompt,
            ai_assist=ai_assist,
            requested_type=chart_type,
            manual_spec_json=manual_spec_json,
            client=llm_bridge.resolve_active_client(db, settings),
            app_version=settings.app_version,
            max_upload_bytes=MAX_CHART_UPLOAD_BYTES,
            max_data_rows=MAX_CHART_DATA_ROWS,
        )
    except UploadSizeLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return ChartGenerateResponse(
        job_id=record['job_id'],
        status=record['status'],
        title=record['title'],
        llm_used=record['llm_used'],
        chart_spec=record['chart_spec'],
        echarts_option=record['echarts_option'],
        warnings=record.get('warnings', []),
        artifacts=record.get('artifacts', []),
        preview_url=record['preview_url'],
        bundle_url=record['bundle_url'],
    )
