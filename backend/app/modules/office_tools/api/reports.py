"""reports 서브라우터 — 보고서 스튜디오(svc01).

``POST /generate`` 는 multipart 업로드(Markdown 파일 + 선택 이미지/ZIP + 메타 +
``ai_mode``)를 받아 ``services/report`` 로 sanitize HTML 보고서를 만들고 JobStore 에
``source_original.md`` / ``aeroone_report.md`` / ``aeroone_report.html`` / ``manifest.json``
artifact 를 등록한다. 렌더는 브라우저 CDN 없이 서버에서 인라인 CSS 자립형 HTML 로 만든다.

AI 보조(``ai_mode=polish/executive``)는 ``core.llm_bridge`` 의 활성 연결을 우선 쓰고,
없거나 실패하면 원문을 유지한다(경고 첨부). 상위 라우터가 세션 로그인을 강제하므로
미로그인은 401 이다. 잘못된 확장자/크기 초과/문자수 초과는 422 로 거부한다.
"""

from __future__ import annotations

from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.auth.dependencies import get_current_user, get_db, get_settings
from app.modules.auth.models import User
from app.modules.office_tools.api.jobs import get_office_job_store
from app.modules.office_tools.core import llm_bridge
from app.modules.office_tools.core.job_store import OfficeJobStore
from app.modules.office_tools.schemas import (
    MAX_REPORT_MARKDOWN_CHARS,
    MAX_REPORT_UPLOAD_BYTES,
    REPORT_MARKDOWN_SUFFIXES,
    ReportAiMode,
    ReportGenerateResponse,
)
from app.modules.office_tools.services.report import generate_report, unpack_asset_zip
from app.modules.office_tools.services.report.assets import IMAGE_SUFFIXES

router = APIRouter(tags=['office-tools'])


def _collect_assets(uploads: list[UploadFile]) -> dict[str, bytes]:
    """업로드 자산을 {키: 바이트} 로 모은다. ZIP 은 이미지만 풀고, 이미지 파일은 그대로."""

    assets: dict[str, bytes] = {}
    for upload in uploads:
        name = upload.filename or ''
        suffix = PurePosixPath(name).suffix.lower()
        data = upload.file.read()
        if suffix == '.zip':
            assets.update(unpack_asset_zip(data))
        elif suffix in IMAGE_SUFFIXES:
            assets[PurePosixPath(name).name] = data
        else:
            raise ValueError(f'지원하지 않는 자산 확장자입니다: {suffix or "(없음)"}')
    return assets


@router.post('/generate', response_model=ReportGenerateResponse)
def generate(
    markdown_file: UploadFile = File(...),
    assets: list[UploadFile] = File(default=[]),
    title: str = Form(default=''),
    subtitle: str = Form(default=''),
    document_version: str = Form(default=''),
    tags: str = Form(default=''),
    ai_mode: ReportAiMode = Form(default='none'),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    store: OfficeJobStore = Depends(get_office_job_store),
    user: User = Depends(get_current_user),
) -> ReportGenerateResponse:
    """Markdown 을 sanitize HTML 보고서로 변환한다. 잘못된 입력은 422."""

    suffix = PurePosixPath(markdown_file.filename or '').suffix.lower()
    if suffix not in REPORT_MARKDOWN_SUFFIXES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f'지원하지 않는 Markdown 확장자입니다: {suffix or "(없음)"}',
        )

    try:
        collected = _collect_assets(assets)
        record = generate_report(
            store=store,
            owner_id=user.id,
            markdown_filename=markdown_file.filename or 'report.md',
            markdown_bytes=markdown_file.file.read(),
            assets=collected,
            title=title,
            subtitle=subtitle,
            document_version=document_version,
            tags=tags,
            ai_mode=ai_mode,
            client=llm_bridge.resolve_active_client(db, settings),
            app_version=settings.app_version,
            max_upload_bytes=MAX_REPORT_UPLOAD_BYTES,
            max_markdown_chars=MAX_REPORT_MARKDOWN_CHARS,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return ReportGenerateResponse(
        job_id=record['job_id'],
        status=record['status'],
        title=record['title'],
        ai_mode=record['ai_mode'],
        llm_used=record['llm_used'],
        html=record['html'],
        warnings=record.get('warnings', []),
        artifacts=record.get('artifacts', []),
        preview_url=record['preview_url'],
        bundle_url=record['bundle_url'],
    )
