from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import sqlite3
from urllib.parse import quote

from bs4 import BeautifulSoup

from app.modules.collections.service import CollectionItemError, HtmlCollectionService
from app.modules.shared.storage.service import StorageError


DEFAULT_SEARCH_COLLECTIONS = ('document', 'civil')
ALL_SEARCH_COLLECTIONS = ('document', 'civil', 'nsa')


class CollectionSearchError(RuntimeError):
    pass


class CollectionSearchUnavailable(CollectionSearchError):
    pass


@dataclass(frozen=True)
class CollectionSearchRoot:
    collection: str
    root: Path


@dataclass(frozen=True)
class CollectionSearchResult:
    collection: str
    path: str
    name: str
    folder: str
    snippet: str
    navigation_url: str
    score: float

    def as_dict(self) -> dict[str, object]:
        return {
            'collection': self.collection,
            'path': self.path,
            'name': self.name,
            'folder': self.folder,
            'snippet': self.snippet,
            'navigation_url': self.navigation_url,
            'score': self.score,
        }


class HtmlCollectionSearchService:
    # HTML 본문 검색은 AI 가 아니라 컬렉션 인프라의 책임이다. 이 서비스는
    # HtmlCollectionService.discover_list/resolve_download_path 를 재사용해 목록/본문/다운로드와
    # 동일한 .html, _debug 제외, path-guard 정책을 따른 뒤 SQLite FTS5 로 검색한다.

    def __init__(self, collection_service: HtmlCollectionService | None = None) -> None:
        self.collection_service = collection_service or HtmlCollectionService()

    def search(
        self,
        roots: list[CollectionSearchRoot],
        query: str,
        managed_storage_root: Path,
        limit: int = 20,
    ) -> list[CollectionSearchResult]:
        terms = self._query_terms(query)
        if not terms:
            return []

        connection = sqlite3.connect(':memory:')
        try:
            self._create_fts_table(connection)
            self._populate(connection, roots, managed_storage_root)
            return self._query(connection, terms, limit)
        finally:
            connection.close()

    def load_refs(
        self,
        refs: list[tuple[str, str]],
        roots: dict[str, Path],
        managed_storage_root: Path,
        snippet_chars: int = 600,
    ) -> list[CollectionSearchResult]:
        """사용자가 명시 선택한 (collection, path) 참조의 본문을 컬렉션 정책으로 로드한다.

        목록/검색/다운로드와 동일하게 ``resolve_download_path`` (path-guard, .html,
        _debug 제외)를 강제 경유한다. AI service 가 자체 경로 해석/본문 추출을 하지
        않도록 컬렉션 인프라에 위임한다. 잘못된/traversal/미허용 컬렉션 참조는 조용히
        건너뛴다(silent drop). Authorization is enforced by the caller: routes must pass
        only collection roots and refs already filtered through collections.policy.
        """

        results: list[CollectionSearchResult] = []
        seen: set[tuple[str, str]] = set()
        for collection, path in refs:
            key = (collection, path)
            if key in seen:
                continue
            seen.add(key)
            root = roots.get(collection)
            if root is None:
                continue
            try:
                file_path = self.collection_service.resolve_download_path(root, path, managed_storage_root)
            except (CollectionItemError, StorageError):
                continue
            try:
                html = file_path.read_text(encoding='utf-8', errors='ignore')
            except OSError:
                continue
            text = self._html_to_text(html)
            name = Path(path).name
            folder = str(Path(path).parent).replace('\\', '/')
            folder = '' if folder in {'.', ''} else folder
            results.append(
                CollectionSearchResult(
                    collection=collection,
                    path=path,
                    name=name,
                    folder=folder,
                    snippet=text[:snippet_chars],
                    navigation_url=self._navigation_url(collection, path),
                    score=0.0,
                )
            )
        return results

    def _create_fts_table(self, connection: sqlite3.Connection) -> None:
        try:
            connection.execute(
                "CREATE VIRTUAL TABLE collection_docs USING fts5("
                "collection UNINDEXED, path UNINDEXED, name, folder, body)"
            )
        except sqlite3.OperationalError as exc:
            raise CollectionSearchUnavailable('SQLite FTS5 is unavailable') from exc

    def _populate(
        self,
        connection: sqlite3.Connection,
        roots: list[CollectionSearchRoot],
        managed_storage_root: Path,
    ) -> None:
        for search_root in roots:
            for item in self.collection_service.discover_list(search_root.root):
                path = item['path']
                try:
                    file_path = self.collection_service.resolve_download_path(
                        search_root.root,
                        path,
                        managed_storage_root,
                    )
                except (CollectionItemError, StorageError):
                    # discover_list 와 resolve_download_path 정책이 달라지는 경우 검색에서는 노출하지 않는다.
                    continue
                html = file_path.read_text(encoding='utf-8', errors='ignore')
                text = self._html_to_text(html)
                connection.execute(
                    'INSERT INTO collection_docs(collection, path, name, folder, body) VALUES (?, ?, ?, ?, ?)',
                    (search_root.collection, path, item['name'], item['folder'], text),
                )
        connection.commit()

    def _query(self, connection: sqlite3.Connection, terms: list[str], limit: int) -> list[CollectionSearchResult]:
        fts_query = ' OR '.join(f'"{term}"' for term in terms)
        rows = connection.execute(
            "SELECT collection, path, name, folder, "
            "snippet(collection_docs, 4, '', '', '…', 18) AS snippet, "
            "bm25(collection_docs) AS score "
            "FROM collection_docs WHERE collection_docs MATCH ? "
            "ORDER BY score LIMIT ?",
            (fts_query, max(1, min(limit, 100))),
        ).fetchall()
        return [
            CollectionSearchResult(
                collection=row[0],
                path=row[1],
                name=row[2],
                folder=row[3],
                snippet=self._clean_snippet(row[4]),
                navigation_url=self._navigation_url(row[0], row[1]),
                score=float(row[5]),
            )
            for row in rows
        ]

    @staticmethod
    def _query_terms(query: str) -> list[str]:
        # FTS5 query syntax injection 을 피하기 위해 사용자의 원문을 그대로 MATCH 에 넣지 않고
        # 단어/숫자/한글 시퀀스만 phrase term 으로 변환한다.
        return [term for term in re.findall(r'[\w가-힣]+', query, flags=re.UNICODE) if term][:8]

    @staticmethod
    def _html_to_text(html: str) -> str:
        soup = BeautifulSoup(html, 'html.parser')
        for node in soup(['script', 'style', 'noscript']):
            node.decompose()
        return ' '.join(soup.get_text(' ', strip=True).split())

    @staticmethod
    def _clean_snippet(snippet: str) -> str:
        return ' '.join((snippet or '').split())

    @staticmethod
    def _navigation_url(collection: str, path: str) -> str:
        encoded_path = quote(path, safe='')
        if collection == 'document':
            return f'/documents?path={encoded_path}'
        if collection == 'civil':
            return f'/reports/civil-aircraft?path={encoded_path}'
        if collection == 'nsa':
            return f'/nsa?path={encoded_path}'
        return ''
