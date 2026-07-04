from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import FileResponse

from app.core.config import Settings
from app.modules.auth.dependencies import get_db, get_optional_user, get_settings
from app.modules.auth.models import User
from app.modules.collections.policy import can_read_collection, readable_collections
from app.modules.collections.service import CollectionItemError, HtmlCollectionService
from app.modules.collections.search_service import (
    ALL_SEARCH_COLLECTIONS,
    DEFAULT_SEARCH_COLLECTIONS,
    CollectionSearchRoot,
    CollectionSearchUnavailable,
    HtmlCollectionSearchService,
)
from sqlalchemy.orm import Session
from app.modules.newsletter.services.html_render_service import HTML_CSP
from app.modules.shared.storage.service import StorageError

router = APIRouter()

service = HtmlCollectionService()
search_service = HtmlCollectionSearchService(service)


def _resolve_collection_root(collection: str, settings: Settings) -> Path:
    # document / civil / nsa 만 허용하는 화이트리스트. config 가 해석한 루트로 매핑하며,
    # 미등록 collection 은 파일시스템에 손대기 전에 404 로 차단한다(경로탈출 표면 축소).
    whitelist: dict[str, Path] = {
        'document': settings.document_root_path,
        'civil': settings.civil_aircraft_root_path,
        'nsa': settings.nsa_root_path,
    }
    root = whitelist.get(collection)
    if root is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Unknown collection')
    return root


def _parse_search_collections(raw: str | None) -> list[str]:
    requested = DEFAULT_SEARCH_COLLECTIONS if raw is None else tuple(
        collection.strip() for collection in raw.split(',') if collection.strip()
    )
    unknown = [collection for collection in requested if collection not in ALL_SEARCH_COLLECTIONS]
    if unknown:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Unknown collection')
    return list(dict.fromkeys(requested))
def _ensure_collection_readable(db: Session, user: User | None, collection: str) -> None:
    if not can_read_collection(db, user, collection):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Collection access denied')




@router.get('/search')
def search_collections(
    q: str = Query('', description='검색어'),
    collections: str | None = Query(None, description='쉼표로 구분한 검색 컬렉션. 기본 document,civil'),
    limit: int = Query(20, ge=1, le=100),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> dict[str, object]:
    # 빠른 본문 검색은 컬렉션 계층의 책임이다. 기본 global scope 는 document,civil 이며
    # NSA 는 /nsa unlock 이후 명시 scope 로만 요청하게 한다.
    requested_collections = _parse_search_collections(collections)
    allowed_collections = readable_collections(db, user, requested_collections)
    roots = [
        CollectionSearchRoot(collection=collection, root=_resolve_collection_root(collection, settings))
        for collection in allowed_collections
    ]
    try:
        results = search_service.search(roots, q, settings.managed_storage_root, limit=limit)
    except CollectionSearchUnavailable as exc:
        return {
            'results': [],
            'degraded': True,
            'reason': str(exc),
            'collections': allowed_collections,
        }
    return {
        'results': [result.as_dict() for result in results],
        'degraded': False,
        'collections': allowed_collections,
    }


@router.get('/{collection}/list')
def list_collection(
    collection: str,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> dict[str, list[dict[str, str]]]:
    # 좌측 폴더 트리를 그리기 위한 컬렉션 목록. 콘텐츠는 /content/html 에서 별도로 받는다.
    root = _resolve_collection_root(collection, settings)
    _ensure_collection_readable(db, user, collection)
    return {'documents': service.discover_list(root)}


@router.get('/{collection}/content/html')
def get_collection_html(
    collection: str,
    response: Response,
    path: str = Query(..., description='컬렉션 루트 기준 상대 경로(.html)'),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    # 선택한 문서 1개를 뉴스레터 HTML 과 동일한 sanitize 파이프라인으로 렌더한다.
    # CSP 헤더 부착은 라우터 책임(서비스는 html 문자열만 반환). 잘못된 경로/비-.html/_debug 는
    # 404, 경로탈출(../..) 등 path-guard 위반은 400 으로 매핑한다.
    root = _resolve_collection_root(collection, settings)
    _ensure_collection_readable(db, user, collection)
    try:
        content_html = service.render_one(root, path, settings.managed_storage_root)
    except CollectionItemError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Document not found') from exc
    except StorageError as exc:
        # 디렉토리 이탈(../..) 등 경로 가드 위반.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid document path') from exc
    response.headers['Content-Security-Policy'] = HTML_CSP
    return {'asset_type': 'html', 'content_html': content_html}


@router.get('/{collection}/download/html')
def download_collection_html(
    collection: str,
    path: str = Query(..., description='컬렉션 루트 기준 상대 경로(.html)'),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    # 원본 HTML 파일을 첨부 다운로드로 제공한다. 렌더용 content/html 과 동일한
    # collection whitelist, .html/_debug 정책, path-guard 를 공유한다.
    root = _resolve_collection_root(collection, settings)
    _ensure_collection_readable(db, user, collection)
    try:
        file_path = service.resolve_download_path(root, path, settings.managed_storage_root)
    except CollectionItemError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Document not found') from exc
    except StorageError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid document path') from exc
    return FileResponse(file_path, media_type='text/html; charset=utf-8', filename=file_path.name)
