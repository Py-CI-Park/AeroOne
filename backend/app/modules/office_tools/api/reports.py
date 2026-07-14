"""reports 서브라우터 — 보고서 스튜디오(svc01).

``POST /generate`` 는 multipart 업로드(Markdown 파일 + 선택 이미지/ZIP + 메타 +
``ai_mode``)를 받아 ``services/report`` 로 sanitize HTML 보고서를 만들고 JobStore 에
``source_original.md`` / ``aeroone_report.md`` / ``aeroone_report.html`` / ``manifest.json``
artifact 를 등록한다. 렌더는 브라우저 CDN 없이 서버에서 인라인 CSS 자립형 HTML 로 만든다.

AI 보조(``ai_mode=polish/executive``)는 ``core.llm_bridge`` 의 활성 연결을 우선 쓰고,
없거나 실패하면 원문을 유지한다(경고 첨부). 상위 라우터가 세션 로그인과 ``office.use`` 를
강제하므로 미로그인은 401, 권한 없이는 403 이다. JobStore 를 변경하는 ``POST /generate`` 는
``require_csrf`` 도 요구하며 유효하지 않은 CSRF 는 403 이다. 업로드 크기 초과는 413,
잘못된 확장자/문자수 초과는 422 로 거부한다.
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
    MAX_REPORT_MARKDOWN_CHARS,
    MAX_REPORT_UPLOAD_BYTES,
    REPORT_MARKDOWN_SUFFIXES,
    ReportAiMode,
    ReportGenerateResponse,
)
from app.modules.office_tools.services.report import generate_report, unpack_asset_zip
from app.modules.office_tools.services.report.assets import (
    IMAGE_SUFFIXES,
    MAX_ZIP_CENTRAL_DIRECTORY_BYTES,
    AssetNameRegistry,
    UploadSizeLimitExceeded,
    canonical_asset_name,
    read_bounded_bytes,
    staged_bounded_stream,
)

router = APIRouter(tags=['office-tools'])
MAX_REPORT_ASSET_TOTAL_BYTES = 50 * 1024 * 1024
MAX_REPORT_ASSET_COMPRESSED_BYTES = 50 * 1024 * 1024
MAX_REPORT_ASSET_UPLOADS = 50
MAX_REPORT_ASSET_MEMBERS = 200
MAX_REPORT_ASSET_FILENAME_BYTES = 1024


def _collect_assets(
    uploads: list[UploadFile],
    *,
    max_upload_bytes: int = MAX_REPORT_UPLOAD_BYTES,
    max_total_bytes: int = MAX_REPORT_ASSET_TOTAL_BYTES,
    max_compressed_bytes: int = MAX_REPORT_ASSET_COMPRESSED_BYTES,
    max_uploads: int = MAX_REPORT_ASSET_UPLOADS,
    max_members: int = MAX_REPORT_ASSET_MEMBERS,
    max_filename_bytes: int = MAX_REPORT_ASSET_FILENAME_BYTES,
    max_central_directory_bytes: int = MAX_ZIP_CENTRAL_DIRECTORY_BYTES,
) -> dict[str, bytes]:
    """모든 multipart/ZIP에 공유되는 압축·해제·이름·멤버 예산 내에서 자산을 모은다."""
    if (
        max_upload_bytes < 1
        or max_total_bytes < 1
        or max_compressed_bytes < 1
        or max_uploads < 1
        or max_central_directory_bytes < 1
    ):
        raise ValueError('보고서 자산 용량 상한은 1 이상이어야 합니다')
    if len(uploads) > max_uploads:
        raise ValueError(f'보고서 자산 업로드 수가 {max_uploads}개를 초과했습니다')

    assets: dict[str, bytes] = {}
    registry = AssetNameRegistry(max_members, max_filename_bytes)
    compressed_total = 0
    decompressed_total = 0
    for upload in uploads:
        name = upload.filename or ''
        try:
            if len(name.encode('utf-8')) > max_filename_bytes:
                raise ValueError('자산 파일명 바이트 상한을 초과했습니다')
        except UnicodeEncodeError as exc:
            raise ValueError('자산 파일명은 UTF-8로 표현할 수 있어야 합니다') from exc

        canonical_name = canonical_asset_name(name)
        suffix = PurePosixPath(canonical_name).suffix.lower()
        if suffix not in IMAGE_SUFFIXES and suffix != '.zip':
            raise ValueError(f'지원하지 않는 자산 확장자입니다: {suffix or "(없음)"}')

        compressed_remaining = max_compressed_bytes - compressed_total
        if compressed_remaining <= 0:
            raise UploadSizeLimitExceeded('보고서 자산 압축 업로드 총 용량 상한을 초과했습니다')
        decompressed_remaining = max_total_bytes - decompressed_total
        if decompressed_remaining <= 0:
            raise ValueError('보고서 자산 압축 해제 총 용량 상한을 초과했습니다')
        compressed_limit_message = (
            '보고서 자산 압축 업로드 총 용량 상한을 초과했습니다'
            if compressed_remaining < max_upload_bytes
            else '업로드가 크기 상한을 초과했습니다'
        )

        with staged_bounded_stream(
            upload.file,
            max_bytes=min(max_upload_bytes, compressed_remaining),
            limit_message=compressed_limit_message,
        ) as staged:
            staged.seek(0, 2)
            compressed_size = staged.tell()
            staged.seek(0)
            compressed_total += compressed_size

            if suffix == '.zip':
                if registry.remaining_members < 1:
                    raise ValueError(f'보고서 자산 멤버 수가 {max_members}개를 초과했습니다')
                extracted = unpack_asset_zip(
                    staged,
                    max_files=registry.remaining_members,
                    max_total_bytes=decompressed_remaining,
                    max_member_bytes=min(max_upload_bytes, decompressed_remaining),
                    max_compressed_bytes=compressed_remaining,
                    max_filename_bytes=max_filename_bytes,
                    max_central_directory_bytes=max_central_directory_bytes,
                    member_registry=registry,
                )
                extracted_total = sum(len(data) for data in extracted.values())
                decompressed_total += extracted_total
                assets.update(extracted)
            else:
                registry.reserve([canonical_name])
                if compressed_size > decompressed_remaining:
                    raise ValueError('보고서 자산 압축 해제 총 용량 상한을 초과했습니다')
                assets[canonical_name] = staged.read()
                decompressed_total += compressed_size
    return assets


@router.post('/generate', response_model=ReportGenerateResponse, dependencies=[Depends(require_csrf)])
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
    """Markdown 을 sanitize HTML 보고서로 변환한다. 업로드 크기 초과는 413이다."""

    suffix = PurePosixPath(markdown_file.filename or '').suffix.lower()
    if suffix not in REPORT_MARKDOWN_SUFFIXES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f'지원하지 않는 Markdown 확장자입니다: {suffix or "(없음)"}',
        )

    try:
        markdown_bytes = read_bounded_bytes(
            markdown_file.file,
            max_bytes=MAX_REPORT_UPLOAD_BYTES,
        )
        collected = _collect_assets(
            assets,
            max_upload_bytes=MAX_REPORT_UPLOAD_BYTES,
            max_total_bytes=MAX_REPORT_ASSET_TOTAL_BYTES,
            max_compressed_bytes=MAX_REPORT_ASSET_COMPRESSED_BYTES,
            max_uploads=MAX_REPORT_ASSET_UPLOADS,
            max_members=MAX_REPORT_ASSET_MEMBERS,
            max_filename_bytes=MAX_REPORT_ASSET_FILENAME_BYTES,
        )
        record = generate_report(
            store=store,
            owner_id=user.id,
            markdown_filename=markdown_file.filename or 'report.md',
            markdown_bytes=markdown_bytes,
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
    except UploadSizeLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)) from exc
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
