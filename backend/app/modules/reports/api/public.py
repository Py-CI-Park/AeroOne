from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.core.config import Settings
from app.modules.auth.dependencies import get_settings
from app.modules.collections.service import CollectionItemError, HtmlCollectionService
from app.modules.newsletter.services.html_render_service import HTML_CSP
from app.modules.shared.storage.service import StorageError

router = APIRouter()

service = HtmlCollectionService()


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
    # 폴더의 단일(최신) 보고서를 선택하는 정책(_latest_report)만 보존하고, 실제 렌더/경로가드는
    # 공유 HtmlCollectionService 에 위임한다(document/civil/nsa 단일 구현). 보고서가 없으면 404,
    # 렌더는 뉴스레터 HTML 과 동일한 sanitize 파이프라인 + 동일 CSP 헤더로 제공한다.
    root = settings.civil_aircraft_root_path
    report = _latest_report(root)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Civil aircraft report not found')
    try:
        content_html = service.render_one(root, report.name, settings.managed_storage_root)
    except (CollectionItemError, StorageError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Civil aircraft report not found') from exc
    response.headers['Content-Security-Policy'] = HTML_CSP
    return {'asset_type': 'html', 'content_html': content_html}
