"""보고서 스튜디오(svc01) 서비스 — Markdown 을 사내 표준 HTML 보고서로 변환한다.

MVP ``svc01/service.py`` 를 AeroOne 로 이식하되 두 가지를 바꾼다.

- 렌더는 벤더 subprocess 대신 경량 경로(``renderer.render_report_html`` = markdown +
  sanitize_html_fragment)를 쓴다(BUILD_CONTRACT §2.5).
- AI 편집은 산출물 A 의 활성 LLM 연결(``OpenAiCompatibleClient``)을 쓰고, 없거나
  실패하면 규칙 없이 원문을 유지한다(경고 첨부).

산출물: ``source_original.md`` / ``aeroone_report.md`` / ``aeroone_report.html`` /
``manifest.json``. 반환 dict 에는 즉시 미리보기용 ``html`` 을 담되 job.json 에는
저장하지 않는다(중복 회피 — 영구본은 HTML artifact).
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.modules.ai.openai_client import OpenAiCompatibleClient
from app.modules.office_tools.core.job_store import OfficeJobStore
from app.modules.office_tools.security import validate_offline_html

from .assets import embed_markdown_images
from .enhancer import enhance_markdown
from .renderer import markdown_to_body, render_report_html


def _decode_markdown(data: bytes) -> str:
    """업로드 바이트를 UTF-8(BOM)/CP949 순으로 디코드한다. 실패 시 ``ValueError``."""

    for encoding in ('utf-8-sig', 'utf-8', 'cp949'):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError('Markdown 은 UTF-8, UTF-8 BOM 또는 CP949 텍스트여야 합니다')


def _derive_title(markdown_text: str, requested: str) -> str:
    """제목을 결정한다: 요청값 우선, 없으면 첫 ``# `` 헤더, 그래도 없으면 기본값."""

    if requested.strip():
        return requested.strip()[:200]
    match = re.search(r'^#\s+(.+)$', markdown_text, flags=re.M)
    return (match.group(1).strip() if match else 'AeroOne 보고서')[:200]


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate_report(
    *,
    store: OfficeJobStore,
    owner_id: int,
    markdown_filename: str,
    markdown_bytes: bytes,
    assets: dict[str, bytes],
    title: str,
    subtitle: str,
    document_version: str,
    tags: str,
    ai_mode: str,
    client: OpenAiCompatibleClient | None,
    app_version: str,
    max_upload_bytes: int,
    max_markdown_chars: int,
) -> dict[str, Any]:
    """보고서 job 을 생성한다. 크기/문자수 위반은 ``ValueError`` 로 라우트가 422 처리."""

    record = store.create(
        'report',
        owner_id=owner_id,
        request_summary={
            'source_filename': Path(markdown_filename).name,
            'ai_mode': ai_mode,
            'asset_count': len(assets),
        },
    )
    job_id = record['job_id']
    warnings: list[str] = []
    try:
        if len(markdown_bytes) > max_upload_bytes:
            raise ValueError('Markdown 업로드가 크기 상한을 초과했습니다')
        raw = _decode_markdown(markdown_bytes)
        if len(raw) > max_markdown_chars:
            raise ValueError('Markdown 문자 수가 상한을 초과했습니다')
        resolved_title = _derive_title(raw, title)

        store.write_bytes(job_id, 'source_original.md', markdown_bytes, 'text/markdown')

        with_images, image_warnings, embedded_count = embed_markdown_images(raw, assets)
        warnings.extend(image_warnings)

        enhancement = enhance_markdown(with_images, ai_mode, client)
        warnings.extend(enhancement.warnings)
        final_markdown = enhancement.markdown

        md_path = store.write_text(job_id, 'aeroone_report.md', final_markdown, 'text/markdown')

        body_html = markdown_to_body(final_markdown)
        html_text = render_report_html(
            body_html=body_html,
            title=resolved_title,
            subtitle=subtitle,
            version=document_version,
            tags=tags,
        )
        html_path = store.write_text(job_id, 'aeroone_report.html', html_text, 'text/html')

        offline_warnings = validate_offline_html(html_text)
        warnings.extend(offline_warnings)

        manifest = {
            'schema_version': '1.0',
            'aeroone_version': app_version,
            'service': 'report',
            'job_id': job_id,
            'generated_at': datetime.now(UTC).isoformat(),
            'input': {
                'filename': Path(markdown_filename).name,
                'sha256': _sha256_bytes(markdown_bytes),
                'asset_count': len(assets),
                'embedded_image_count': embedded_count,
            },
            'processing': {
                'ai_mode': ai_mode,
                'llm_used': enhancement.llm_used,
                'renderer': 'markdown+sanitize',
            },
            'outputs': {
                'markdown_sha256': _sha256_file(md_path),
                'html_sha256': _sha256_file(html_path),
                'html_size_bytes': html_path.stat().st_size,
            },
            'validation': {
                'offline_resource_warnings': offline_warnings,
                'warnings': list(dict.fromkeys(warnings)),
            },
        }
        store.write_text(
            job_id,
            'manifest.json',
            json.dumps(manifest, ensure_ascii=False, indent=2),
            'application/json',
        )
        completed = store.complete(
            job_id,
            warnings=warnings,
            extra={
                'title': resolved_title,
                'ai_mode': ai_mode,
                'llm_used': enhancement.llm_used,
                'preview_url': f'/api/v1/office-tools/jobs/{job_id}/artifacts/aeroone_report.html',
                'bundle_url': f'/api/v1/office-tools/jobs/{job_id}/bundle',
            },
        )
        # html 은 응답 편의(iframe srcdoc)용으로만 반환하고 job.json 에는 저장하지 않는다.
        return {**completed, 'html': html_text}
    except Exception as exc:
        store.fail(job_id, str(exc), warnings)
        raise
