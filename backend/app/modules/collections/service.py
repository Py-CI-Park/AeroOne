from __future__ import annotations

from pathlib import Path

from app.modules.newsletter.services.html_render_service import HtmlRenderService
from app.modules.shared.storage.service import StorageError, StorageService


class CollectionItemError(ValueError):
    # 잘못된 경로(.html 아님 / _debug.html)나 존재하지 않는 파일 등 "찾을 수 없음" 신호.
    # 라우터는 이를 404 로 매핑한다.
    pass


class HtmlCollectionService:
    # document / civil / nsa 는 모두 같은 "HTML 컬렉션" 동작이다 — 운영자가 떨군 정적 HTML 을
    # 폴더 트리로 목록화하고, 선택 1개를 뉴스레터와 동일한 sanitize 파이프라인으로 렌더한다.
    # 목록 수집(discover_list)과 단일 렌더(render_one) 두 동작을 단일 구현으로 모아
    # documents/reports 라우터가 병렬 복제 없이 위임하게 한다.

    def discover_list(self, root: Path) -> list[dict[str, str]]:
        # 루트 아래 .html 을 재귀(rglob) 수집한다. 하위 폴더 구조를 그대로 인식하며,
        # 뉴스레터/보고서와 같은 정책으로 _debug.html 은 제외한다. 루트가 없으면 빈 목록.
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

    def render_one(self, root: Path, path: str, managed_storage_root: Path) -> str:
        # 선택한 문서 1개를 뉴스레터 HTML 과 동일한 sanitize 파이프라인(HtmlRenderService.render)으로
        # 렌더한다 — 외부 <link>/외부 src 만 차단하고 인라인 스크립트/스타일은 보존, 격리는
        # 프론트엔드의 sandbox iframe(allow-scripts)이 담당한다. 경로는 StorageService 의
        # path-guard(ensure_within_root)로 루트 밖을 차단한다. CSP 헤더 책임은 라우터에 둔다.
        if not path.lower().endswith('.html') or path.endswith('_debug.html'):
            raise CollectionItemError('Document not found')
        storage = StorageService(root, managed_storage_root)
        resolved = storage.resolve_external_relative_path(path)
        if not resolved.is_file():
            raise CollectionItemError('Document not found')
        return HtmlRenderService(storage).render(path)

    def resolve_download_path(self, root: Path, path: str, managed_storage_root: Path) -> Path:
        # 다운로드도 렌더와 동일한 allowlist(.html, _debug 제외)와 path-guard 를 거친다.
        # 반환값은 원본 HTML 파일 경로이며, 라우터가 FileResponse 로 첨부 전송한다.
        if not path.lower().endswith('.html') or path.endswith('_debug.html'):
            raise CollectionItemError('Document not found')
        storage = StorageService(root, managed_storage_root)
        resolved = storage.resolve_external_relative_path(path)
        if not resolved.is_file():
            raise CollectionItemError('Document not found')
        return resolved
