from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.core.config import Settings
from app.modules.auth.dependencies import get_settings
from app.modules.newsletter.services.html_render_service import HTML_CSP, HtmlRenderService
from app.modules.shared.storage.service import StorageError, StorageService

router = APIRouter()


def _discover_documents(root: Path) -> list[dict[str, str]]:
    # _database/document 는 운영자가 떨군 정적 HTML 보관소다(뉴스레터처럼 DB 인덱싱하지 않음).
    # 하위 폴더로 분류해 넣으면 그 구조를 그대로 인식하도록 rglob 로 재귀 수집한다.
    # 뉴스레터/민간항공기 보고서와 같은 정책으로 _debug.html 은 제외한다.
    if not root.exists() or not root.is_dir():
        return []
    items: list[dict[str, str]] = []
    for path in root.rglob('*.html'):
        if not path.is_file() or path.name.endswith('_debug.html'):
            continue
        relative = path.relative_to(root)
        # 폴더 구분/선택을 위해 상대 경로(forward-slash), 표시 이름(stem), 부모 폴더("" = 루트)를 함께 넘긴다.
        parent = relative.parent
        folder = '' if parent == Path('.') else str(parent).replace('\\', '/')
        items.append({
            'path': str(relative).replace('\\', '/'),
            'name': path.stem,
            'folder': folder,
        })
    # 폴더 → 이름 순으로 안정 정렬해 좌측 트리가 결정적으로 그려지게 한다.
    items.sort(key=lambda item: (item['folder'], item['name']))
    return items


@router.get('/list')
def list_documents(settings: Settings = Depends(get_settings)) -> dict[str, list[dict[str, str]]]:
    # 좌측 폴더 트리를 그리기 위한 문서 목록. 콘텐츠는 /content/html 에서 별도로 받는다.
    return {'documents': _discover_documents(settings.document_root_path)}


@router.get('/content/html')
def get_document_html(
    response: Response,
    path: str = Query(..., description='_database/document 기준 상대 경로(.html)'),
    settings: Settings = Depends(get_settings),
):
    # 선택한 문서 1개를 뉴스레터 HTML 과 동일한 sanitize 파이프라인(HtmlRenderService.render)으로
    # 렌더한다 — 외부 <link>/외부 src 만 차단하고 인라인 스크립트/스타일은 보존, 격리는
    # 프론트엔드의 sandbox iframe(allow-scripts)이 담당한다. 경로는 StorageService 의
    # path-guard(ensure_within_root)로 _database/document 밖을 차단한다.
    root = settings.document_root_path
    if not path.lower().endswith('.html') or path.endswith('_debug.html'):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Document not found')
    storage = StorageService(root, settings.managed_storage_root)
    try:
        resolved = storage.resolve_external_relative_path(path)
    except StorageError as exc:
        # 디렉토리 이탈(../..) 등 경로 가드 위반.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid document path') from exc
    if not resolved.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Document not found')
    response.headers['Content-Security-Policy'] = HTML_CSP
    return {'asset_type': 'html', 'content_html': HtmlRenderService(storage).render(path)}
