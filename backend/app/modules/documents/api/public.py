from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.core.config import Settings
from app.modules.auth.dependencies import get_settings
from app.modules.collections.service import CollectionItemError, HtmlCollectionService
from app.modules.newsletter.services.html_render_service import HTML_CSP
from app.modules.shared.storage.service import StorageError

router = APIRouter()

service = HtmlCollectionService()


@router.get('/list')
def list_documents(settings: Settings = Depends(get_settings)) -> dict[str, list[dict[str, str]]]:
    # 좌측 폴더 트리를 그리기 위한 문서 목록. 콘텐츠는 /content/html 에서 별도로 받는다.
    # 목록 수집은 공유 HtmlCollectionService 에 위임한다(document/civil/nsa 단일 구현).
    return {'documents': service.discover_list(settings.document_root_path)}


@router.get('/content/html')
def get_document_html(
    response: Response,
    path: str = Query(..., description='_database/document 기준 상대 경로(.html)'),
    settings: Settings = Depends(get_settings),
):
    # 선택한 문서 1개를 뉴스레터 HTML 과 동일한 sanitize 파이프라인으로 렌더한다 —
    # 렌더/경로가드는 공유 HtmlCollectionService 에 위임하고, 잘못된 경로/비-.html/_debug 는
    # 404, 경로탈출(../..) 등 path-guard 위반은 400 으로 매핑한다. CSP 헤더는 라우터가 붙인다.
    try:
        content_html = service.render_one(settings.document_root_path, path, settings.managed_storage_root)
    except CollectionItemError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Document not found') from exc
    except StorageError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid document path') from exc
    response.headers['Content-Security-Policy'] = HTML_CSP
    return {'asset_type': 'html', 'content_html': content_html}
