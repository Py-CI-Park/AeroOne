"""지식폴더 색인 서비스 — in-place 스캔 + 청크 + Ollama 임베딩 + 증분 동기화 + 코사인 검색.

임베더는 생성자 주입이라 테스트에서 실 Ollama 없이 결정적 벡터로 대체할 수 있다. 재색인은
동기 호출(``reindex``)과 백그라운드 스레드 호출을 모두 지원하며, ``progress_cb`` 로 진행률을
알린다(호출자는 API 라우터 — 새 ``SessionLocal`` 로 별도 스레드에서 돌린다).
"""

from __future__ import annotations

import json
import logging
import math
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from app.modules.aero_work.embedding_client import CompatibleEmbedder, EmbeddingUnavailable, OllamaEmbedder
from app.modules.aero_work.models import KnowledgeChunk, KnowledgeFile, KnowledgeFolder
from app.modules.aero_work.text_extract import extract_text, is_supported
from app.modules.aero_work.version_ranker import group_by_family

MAX_INDEX_BYTES = 20 * 1024 * 1024  # 파일당 20MB 상한(PDF/DOCX 등 오피스 문서 대응)
CHUNK_SIZE = 900
CHUNK_OVERLAP = 150
FTS_TABLE = 'aero_work_chunk_fts'  # 0031 — trigram(폴백 unicode61) FTS5 가상 테이블
PROGRESS_EVERY = 5  # 재색인 진행률(status_detail) 갱신 주기(파일 수 기준)

logger = logging.getLogger(__name__)


def _fts_available(db: Session) -> bool:
    """``aero_work_chunk_fts`` 가상 테이블 존재 여부를 세션당 1회만 확인해 캐싱한다.

    ``sqlite_master`` 조회는 테이블이 없어도 예외 없이 빈 결과만 돌려주므로, 트랜잭션
    도중(재색인 중) 호출해도 ``db.rollback()`` 이 필요 없다 — 진행 중이던 flush 내용을
    건드리지 않는다.
    """

    cached = db.info.get('_aero_work_fts_available')
    if cached is not None:
        return cached
    row = db.execute(
        sql_text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:name"),
        {'name': FTS_TABLE},
    ).first()
    result = row is not None
    db.info['_aero_work_fts_available'] = result
    return result


def _fts_index_chunk(db: Session, chunk_id: int, content: str, rel_path: str) -> None:
    """청크 upsert 시 FTS 색인에 반영한다(부분일치는 소문자 정규화된 본문으로 매칭).

    delete-then-insert 로 처리한다 — FTS5 가상 테이블은 rowid 에 대한 UPSERT 문법이
    없고, 같은 chunk_id 로 다시 색인을 걸 가능성(예: 향후 in-place 갱신 경로)에도
    ``UNIQUE constraint`` 위반 없이 항상 최신 본문으로 덮어써야 한다.
    """

    if not _fts_available(db):
        return
    db.execute(sql_text(f'DELETE FROM {FTS_TABLE} WHERE rowid = :id'), {'id': chunk_id})
    db.execute(
        sql_text(f'INSERT INTO {FTS_TABLE}(rowid, content, rel_path) VALUES (:id, :content, :rel_path)'),
        {'id': chunk_id, 'content': content.lower(), 'rel_path': rel_path},
    )


def _fts_delete_chunk(db: Session, chunk_id: int) -> None:
    """청크 삭제 시 FTS 색인에서도 함께 제거한다(rowid 재사용으로 인한 오염 방지)."""

    if not _fts_available(db):
        return
    db.execute(sql_text(f'DELETE FROM {FTS_TABLE} WHERE rowid = :id'), {'id': chunk_id})


class KnowledgeError(RuntimeError):
    """지식폴더 작업 실패(경로 없음·중복·미등록 등)."""


def chunk_text(text: str, *, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """문자 윈도우(가능하면 개행 경계) 기준으로 겹침을 두고 청크 분할한다."""

    normalized = '\n'.join(line.rstrip() for line in text.splitlines()).strip()
    if not normalized:
        return []
    chunks: list[str] = []
    start = 0
    length = len(normalized)
    while start < length:
        end = min(start + size, length)
        if end < length:
            boundary = normalized.rfind('\n', start + overlap, end)
            if boundary > start:
                end = boundary
        piece = normalized[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= length:
            break
        start = max(end - overlap, start + 1)
    return chunks


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = na = nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / math.sqrt(na * nb)


def _file_signature(path: Path) -> str:
    stat = path.stat()
    return f'{int(stat.st_mtime_ns)}-{stat.st_size}'

def _chunk_uses_active_embedding_model(
    chunk: KnowledgeChunk, embedder: OllamaEmbedder | CompatibleEmbedder
) -> bool:
    return chunk.embed_model == embedder.model or (
        chunk.embed_model is None and isinstance(embedder, OllamaEmbedder)
    )



class KnowledgeService:
    def __init__(self, db: Session, embedder: OllamaEmbedder | CompatibleEmbedder) -> None:
        self.db = db
        self.embedder = embedder

    # ---- 폴더 CRUD ----
    def list_folders(self) -> list[KnowledgeFolder]:
        return list(
            self.db.execute(select(KnowledgeFolder).order_by(KnowledgeFolder.id)).scalars().all()
        )

    def get_folder(self, folder_id: int) -> KnowledgeFolder | None:
        return self.db.get(KnowledgeFolder, folder_id)

    def register_folder(self, name: str, path: str) -> KnowledgeFolder:
        resolved = Path(path).expanduser()
        if not resolved.is_absolute():
            raise KnowledgeError('폴더 경로는 절대 경로여야 합니다.')
        if not resolved.is_dir():
            raise KnowledgeError(f'폴더를 찾을 수 없습니다: {resolved}')
        canonical = str(resolved)
        existing = self.db.execute(
            select(KnowledgeFolder).where(KnowledgeFolder.path == canonical)
        ).scalar_one_or_none()
        if existing is not None:
            raise KnowledgeError('이미 등록된 폴더입니다.')
        folder = KnowledgeFolder(name=(name or '').strip() or resolved.name, path=canonical, status='pending')
        self.db.add(folder)
        self.db.flush()
        return folder

    def delete_folder(self, folder_id: int) -> bool:
        folder = self.get_folder(folder_id)
        if folder is None:
            return False
        for file_row in folder.files:
            for chunk in file_row.chunks:
                _fts_delete_chunk(self.db, chunk.id)
        self.db.delete(folder)
        self.db.flush()
        return True

    # ---- 색인(증분) ----
    def _scan_disk(self, root: Path) -> dict[str, tuple[Path, str]]:
        disk: dict[str, tuple[Path, str]] = {}
        for path in sorted(root.rglob('*')):
            try:
                if not path.is_file() or not is_supported(path):
                    continue
                if path.stat().st_size > MAX_INDEX_BYTES:
                    continue
                disk[str(path.relative_to(root))] = (path, _file_signature(path))
            except OSError:
                continue
        return disk

    def reindex(
        self, folder_id: int, *, progress_cb: Callable[[int, int], None] | None = None
    ) -> KnowledgeFolder:
        """폴더를 증분 재색인한다.

        ``progress_cb`` 는 (처리한 파일 수, 이번 스캔의 전체 파일 수) 로 주기 호출된다
        (API 라우터가 백그라운드 스레드에서 ``status_detail`` 갱신에 쓴다 — G004).
        """

        folder = self.get_folder(folder_id)
        if folder is None:
            raise KnowledgeError('폴더를 찾을 수 없습니다.')
        root = Path(folder.path)
        if not root.is_dir():
            folder.status = 'error'
            folder.status_detail = f'폴더가 사라졌습니다: {root}'
            self.db.flush()
            raise KnowledgeError(folder.status_detail)

        disk = self._scan_disk(root)
        total = len(disk)
        existing = {f.rel_path: f for f in folder.files}

        # 디스크에서 사라진 파일 제거(증분 삭제) — FTS 색인도 함께 정리한다.
        for rel_path, file_row in list(existing.items()):
            if rel_path not in disk:
                for chunk in list(file_row.chunks):
                    _fts_delete_chunk(self.db, chunk.id)
                self.db.delete(file_row)

        changed = 0
        processed = 0
        try:
            for rel_path, (path, signature) in disk.items():
                file_row = existing.get(rel_path)
                if file_row is not None and file_row.signature == signature and all(
                    _chunk_uses_active_embedding_model(chunk, self.embedder)
                    for chunk in file_row.chunks
                ):
                    processed += 1
                    if progress_cb and (processed % PROGRESS_EVERY == 0 or processed == total):
                        progress_cb(processed, total)
                    continue  # 파일·임베딩 공간 모두 미변경 → 스킵(증분)
                try:
                    text = extract_text(path)
                except OSError:
                    processed += 1
                    continue
                pieces = chunk_text(text)
                embeddings = self.embedder.embed(pieces) if pieces else []
                if file_row is None:
                    file_row = KnowledgeFile(folder_id=folder.id, rel_path=rel_path, signature=signature)
                    self.db.add(file_row)
                    self.db.flush()
                else:
                    for chunk in list(file_row.chunks):
                        _fts_delete_chunk(self.db, chunk.id)
                        self.db.delete(chunk)
                    file_row.signature = signature
                file_row.chunk_count = len(pieces)
                file_row.indexed_at = datetime.now(timezone.utc)
                new_chunks: list[tuple[KnowledgeChunk, str]] = []
                for index, (piece, vector) in enumerate(zip(pieces, embeddings)):
                    chunk = KnowledgeChunk(
                        file_id=file_row.id,
                        chunk_index=index,
                        content=piece,
                        embedding=json.dumps(vector),
                        embed_model=self.embedder.model,
                    )
                    self.db.add(chunk)
                    new_chunks.append((chunk, piece))
                if new_chunks:
                    self.db.flush()  # id 확보 후 FTS 색인(rowid=chunk.id)
                    for chunk, piece in new_chunks:
                        _fts_index_chunk(self.db, chunk.id, piece, rel_path)
                changed += 1
                processed += 1
                if progress_cb and (processed % PROGRESS_EVERY == 0 or processed == total):
                    progress_cb(processed, total)
        except EmbeddingUnavailable as exc:
            folder.status = 'error'
            folder.status_detail = str(exc)
            self.db.flush()
            raise

        self.db.flush()
        folder.file_count = int(
            self.db.execute(
                select(func.count(KnowledgeFile.id)).where(KnowledgeFile.folder_id == folder.id)
            ).scalar_one()
        )
        folder.chunk_count = int(
            self.db.execute(
                select(func.coalesce(func.sum(KnowledgeFile.chunk_count), 0)).where(
                    KnowledgeFile.folder_id == folder.id
                )
            ).scalar_one()
        )
        folder.status = 'ready'
        folder.status_detail = (
            f'{folder.file_count}개 파일 · {folder.chunk_count}개 청크 (이번 {changed}개 갱신)'
        )
        folder.last_indexed_at = datetime.now(timezone.utc)
        self.db.flush()
        return folder

    # ---- 검색 ----
    def search(self, query: str, *, folder_id: int | None = None, top_k: int = 8) -> list[dict]:
        query = (query or '').strip()
        if not query:
            return []
        query_vec = self.embedder.embed_one(query)
        stmt = (
            select(KnowledgeChunk, KnowledgeFile, KnowledgeFolder)
            .join(KnowledgeFile, KnowledgeChunk.file_id == KnowledgeFile.id)
            .join(KnowledgeFolder, KnowledgeFile.folder_id == KnowledgeFolder.id)
        )
        if folder_id is not None:
            stmt = stmt.where(KnowledgeFolder.id == folder_id)
        hits: list[dict] = []
        for chunk, file_row, folder in self.db.execute(stmt).all():
            if not _chunk_uses_active_embedding_model(chunk, self.embedder):
                continue
            try:
                vector = json.loads(chunk.embedding)
            except (ValueError, TypeError):
                continue
            score = cosine_similarity(query_vec, vector)
            if score <= 0.0:
                continue
            hits.append(
                {
                    'folder_id': folder.id,
                    'folder_name': folder.name,
                    'rel_path': file_row.rel_path,
                    'chunk_index': chunk.chunk_index,
                    'content': chunk.content,
                    'score': round(score, 4),
                }
            )
        hits.sort(key=lambda item: item['score'], reverse=True)
        return hits[:top_k]

    # ---- 키워드 검색 (FTS5 MATCH 우선 · 부분일치, 실패/미지원 시 LIKE 폴백) ----
    def keyword_search(self, query: str, *, folder_id: int | None = None, top_k: int = 20) -> list[dict]:
        """공백으로 나눈 키워드가 모두 포함된 청크를 찾는다(대소문자 무시). 임베딩/Ollama 불필요.

        내부적으로 FTS5 가상 테이블(``aero_work_chunk_fts``)이 있으면 그걸 우선 쓴다 —
        trigram 토크나이저는 짧은 한국어 부분 문자열(예: '예산' → '예산편성')도 인덱싱된
        ``LIKE`` 로 빠르게 찾아준다(MATCH 연산자는 트라이그램 최소 길이 제약 때문에
        2글자 질의를 못 잡는다 — 설계 근거는 보고서 참조). FTS 테이블이 없거나 조회 중
        오류가 나면 항상 기존 LIKE 폴백 경로로 넘어간다(응답 형태·score 정의 불변).
        """

        terms = [term for term in (query or '').split() if term]
        if not terms:
            return []
        if _fts_available(self.db):
            try:
                return self._keyword_search_fts(terms, folder_id=folder_id, top_k=top_k)
            except Exception:  # noqa: BLE001 — FTS 조회 실패는 항상 LIKE 폴백으로 흡수
                # 폴백 자체는 안전하지만 실패 증거를 남겨야 운영 중 FTS 손상(파일 손상,
                # sqlite 빌드 교체 등)을 조기에 발견할 수 있다 — 재리뷰 P3 반영.
                logger.warning('FTS 키워드 검색 실패 — LIKE 폴백으로 전환함', exc_info=True)
        return self._keyword_search_like(terms, folder_id=folder_id, top_k=top_k)

    def _keyword_search_fts(
        self, terms: list[str], *, folder_id: int | None, top_k: int
    ) -> list[dict]:
        """FTS rowid 를 한 번 조회해 Python 리스트로 옮긴 뒤 다시 ``IN``으로 넣는 대신,
        ``chunk.id IN (SELECT rowid FROM fts WHERE ...)`` 상관 서브쿼리 한 문장으로
        묶는다 — 왕복 1회 감소 + rowid 리스트 크기에 따른 파라미터 폭증을 피한다.
        """

        conditions = ' AND '.join(f'content LIKE :t{i}' for i in range(len(terms)))
        params: dict[str, str] = {f't{i}': f'%{term.lower()}%' for i, term in enumerate(terms)}
        fts_rowids = sql_text(f'SELECT rowid FROM {FTS_TABLE} WHERE {conditions}')
        stmt = (
            select(KnowledgeChunk, KnowledgeFile, KnowledgeFolder)
            .join(KnowledgeFile, KnowledgeChunk.file_id == KnowledgeFile.id)
            .join(KnowledgeFolder, KnowledgeFile.folder_id == KnowledgeFolder.id)
            .where(KnowledgeChunk.id.in_(fts_rowids))
        )
        if folder_id is not None:
            stmt = stmt.where(KnowledgeFolder.id == folder_id)
        return self._build_keyword_hits(stmt, terms, top_k, params=params)

    def _keyword_search_like(
        self, terms: list[str], *, folder_id: int | None, top_k: int
    ) -> list[dict]:
        stmt = (
            select(KnowledgeChunk, KnowledgeFile, KnowledgeFolder)
            .join(KnowledgeFile, KnowledgeChunk.file_id == KnowledgeFile.id)
            .join(KnowledgeFolder, KnowledgeFile.folder_id == KnowledgeFolder.id)
        )
        if folder_id is not None:
            stmt = stmt.where(KnowledgeFolder.id == folder_id)
        # L2: 폴백(LIKE) 정규화 동등성 범위 — func.lower()/str.lower() 는 한국어(완성형 음절에는
        # 대소문자 개념이 없어 항등) 와 ASCII 영문에서는 FTS 경로(_fts_index_chunk 의
        # content.lower())와 결과가 항상 동일하다. 다만 일부 비ASCII 문자(예: 터키어 'İ/i',
        # 독일어 'ß' 등 케이스 폴딩이 언어별로 다른 문자)는 sqlite3 내장 lower() 와 Python
        # str.lower() 가 다르게 접을 수 있어 이 경계에서만 두 경로의 대소문자 무시 결과가
        # 갈릴 수 있다 — 폐쇄망 사용자 문서가 한국어/영문 위주라 실무 영향은 없다고 판단.
        for term in terms:
            stmt = stmt.where(func.lower(KnowledgeChunk.content).like(f'%{term.lower()}%'))
        return self._build_keyword_hits(stmt, terms, top_k)

    def _build_keyword_hits(
        self, stmt, terms: list[str], top_k: int, *, params: dict[str, str] | None = None
    ) -> list[dict]:
        hits: list[dict] = []
        rows = self.db.execute(stmt, params).all() if params else self.db.execute(stmt).all()
        for chunk, file_row, folder in rows:
            lowered = chunk.content.lower()
            score = sum(lowered.count(term.lower()) for term in terms)
            hits.append(
                {
                    'folder_id': folder.id,
                    'folder_name': folder.name,
                    'rel_path': file_row.rel_path,
                    'chunk_index': chunk.chunk_index,
                    'content': chunk.content,
                    'score': float(score),
                }
            )
        hits.sort(key=lambda item: item['score'], reverse=True)
        return hits[:top_k]

    # ---- 위키 (버전 가족 문서 목록) ----
    def wiki(self, *, folder_id: int | None = None) -> list[dict]:
        """색인된 파일을 버전 가족(대표 + 판본 이력)으로 묶어 반환한다(gongmuwon 업무 허브 백본)."""

        stmt = select(KnowledgeFile, KnowledgeFolder).join(
            KnowledgeFolder, KnowledgeFile.folder_id == KnowledgeFolder.id
        )
        if folder_id is not None:
            stmt = stmt.where(KnowledgeFolder.id == folder_id)
        items = [
            {
                'id': file_row.id,
                'folder_id': folder.id,
                'folder_name': folder.name,
                'rel_path': file_row.rel_path,
                'chunk_count': file_row.chunk_count,
                'summary': file_row.summary,
            }
            for file_row, folder in self.db.execute(stmt).all()
        ]
        return group_by_family(items)
