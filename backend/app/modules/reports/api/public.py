from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.core.config import Settings
from app.modules.auth.dependencies import get_settings
from app.modules.newsletter.services.html_render_service import HTML_CSP, HtmlRenderService
from app.modules.shared.storage.service import StorageService

router = APIRouter()


def _latest_report(root: Path) -> Path | None:
    # _database/civil_aircraft 는 정적 보고서 보관소다(뉴스레터처럼 DB 인덱싱하지 않음).
    # 현재는 단일 보고서지만, 운영자가 새 버전(v2.1 등)을 떨궈도 최신본이 뜨도록
    # mtime 이 가장 최근인 .html 1개를 고른다. 뉴스레터와 같은 정책으로 _debug.html 은 제외.
    if not root.exists() or not root.is_dir():
        return None
    candidates = [p for p in root.glob('*.html') if p.is_file() and not p.name.endswith('_debug.html')]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


@router.get('/civil-aircraft/content/html')
def get_civil_aircraft_report(response: Response, settings: Settings = Depends(get_settings)):
    # 뉴스레터 HTML 과 동일한 sanitize 파이프라인(HtmlRenderService.render)을 재사용한다 —
    # 폐쇄망 순도를 위해 외부 <link>/외부 src 만 차단하고 인라인 스크립트/스타일은 보존.
    # 격리는 프론트엔드의 sandbox iframe(allow-scripts)이 담당한다. 달력/DB/슬러그 없이
    # 폴더의 단일 보고서를 곧바로 렌더하는 읽기 전용 경로다.
    root = settings.civil_aircraft_root_path
    report = _latest_report(root)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Civil aircraft report not found')
    storage = StorageService(root, settings.managed_storage_root)
    response.headers['Content-Security-Policy'] = HTML_CSP
    return {'asset_type': 'html', 'content_html': HtmlRenderService(storage).render(report.name)}
