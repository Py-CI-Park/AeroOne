from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import FileResponse

from app.core.config import Settings
from app.modules.auth.dependencies import get_settings
from app.modules.collections.service import CollectionItemError, HtmlCollectionService
from app.modules.newsletter.services.html_render_service import HTML_CSP
from app.modules.shared.storage.service import StorageError

router = APIRouter()

service = HtmlCollectionService()

# Bundled interactive Civil Aircraft dashboard (v1.8). Shipped with the package under
# the reports module so it is always present; an operator override under
# _database/civil_aircraft/dashboard/ takes precedence when it exists.
_DASHBOARD_BUNDLE = Path(__file__).resolve().parents[1] / 'civil_aircraft_dashboard'

# Self-only CSP for the trusted internal dashboard bundle. Scripts/styles are
# self-hosted (no external CDN); the bundle uses one inline print handler and inline
# style attributes, so 'unsafe-inline' is required — but no external origin is allowed.
_DASHBOARD_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    # blob: 는 PNG 내보내기(SVG를 blob URL 이미지로 로드→canvas 직렬화)에 필요하다.
    # blob: 는 same-origin ephemeral URL 이라 self-only 원칙을 깨지 않는다(외부 origin 아님).
    "img-src 'self' data: blob:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'self'; "
    "base-uri 'none'; "
    "object-src 'none'; "
    "form-action 'self'"
)

_CONTENT_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.htm': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'text/javascript; charset=utf-8',
    '.mjs': 'text/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.svg': 'image/svg+xml',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.webp': 'image/webp',
    '.gif': 'image/gif',
    '.ico': 'image/x-icon',
    '.csv': 'text/csv; charset=utf-8',
    '.md': 'text/markdown; charset=utf-8',
    '.txt': 'text/plain; charset=utf-8',
    '.woff2': 'font/woff2',
    '.woff': 'font/woff',
}


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


def _dashboard_root(settings: Settings) -> Path:
    override = settings.civil_aircraft_root_path / 'dashboard'
    if (override / 'index.html').is_file():
        return override
    return _DASHBOARD_BUNDLE


def _resolve_within(base: Path, rel: str) -> Path | None:
    # Strict path guard: normalize under the base and reject any traversal escape.
    cleaned = rel.replace('\\', '/').lstrip('/')
    target = (base / cleaned).resolve() if cleaned else (base / 'index.html').resolve()
    try:
        target.relative_to(base.resolve())
    except ValueError:
        return None
    if target.is_dir():
        target = target / 'index.html'
    if not target.is_file():
        return None
    return target


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


@router.get('/civil-aircraft/app')
@router.get('/civil-aircraft/app/{path:path}')
def get_civil_aircraft_app(path: str = '', settings: Settings = Depends(get_settings)) -> FileResponse:
    # Serve the interactive v1.8 dashboard bundle as same-origin static files so its
    # own bundled scripts run (unlike the sanitized single-report path above). Path is
    # guarded against traversal and only files under the bundle/override root are served.
    base = _dashboard_root(settings)
    target = _resolve_within(base, path)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Not found')
    media_type = _CONTENT_TYPES.get(target.suffix.lower(), 'application/octet-stream')
    response = FileResponse(target, media_type=media_type)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    if target.suffix.lower() in {'.html', '.htm'}:
        response.headers['Content-Security-Policy'] = _DASHBOARD_CSP
    return response
