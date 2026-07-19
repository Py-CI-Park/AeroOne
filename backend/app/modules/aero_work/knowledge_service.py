"""지식폴더 색인 서비스 — in-place 스캔 + 청크 + Ollama 임베딩 + 증분 동기화 + 코사인 검색.

임베더는 생성자 주입이라 테스트에서 실 Ollama 없이 결정적 벡터로 대체할 수 있다. 색인은
현재 동기(요청 스레드) 실행 — 대용량 폴더 백그라운드 색인은 후속(P5) 범위다.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.aero_work.embedding_client import EmbeddingUnavailable, OllamaEmbedder
from app.modules.aero_work.models import KnowledgeChunk, KnowledgeFile, KnowledgeFolder
from app.modules.aero_work.text_extract import extract_text, is_supported
from app.modules.aero_work.version_ranker import group_by_family

MAX_INDEX_BYTES = 20 * 1024 * 1024  # 파일당 20MB 상한(PDF/DOCX 등 오피스 문서 대응)
CHUNK_SIZE = 900
CHUNK_OVERLAP = 150


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


class KnowledgeService:
    def __init__(self, db: Session, embedder: OllamaEmbedder) -> None:
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

    def reindex(self, folder_id: int) -> KnowledgeFolder:
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
        existing = {f.rel_path: f for f in folder.files}

        # 디스크에서 사라진 파일 제거(증분 삭제)
        for rel_path, file_row in list(existing.items()):
            if rel_path not in disk:
                self.db.delete(file_row)

        changed = 0
        try:
            for rel_path, (path, signature) in disk.items():
                file_row = existing.get(rel_path)
                if file_row is not None and file_row.signature == signature:
                    continue  # 미변경 → 스킵(증분)
                try:
                    text = extract_text(path)
                except OSError:
                    continue
                pieces = chunk_text(text)
                embeddings = self.embedder.embed(pieces) if pieces else []
                if file_row is None:
                    file_row = KnowledgeFile(folder_id=folder.id, rel_path=rel_path, signature=signature)
                    self.db.add(file_row)
                    self.db.flush()
                else:
                    for chunk in list(file_row.chunks):
                        self.db.delete(chunk)
                    file_row.signature = signature
                file_row.chunk_count = len(pieces)
                file_row.indexed_at = datetime.now(timezone.utc)
                for index, (piece, vector) in enumerate(zip(pieces, embeddings)):
                    self.db.add(
                        KnowledgeChunk(
                            file_id=file_row.id,
                            chunk_index=index,
                            content=piece,
                            embedding=json.dumps(vector),
                        )
                    )
                changed += 1
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

    # ---- 키워드 검색 (LIKE, 임베딩 불필요) ----
    def keyword_search(self, query: str, *, folder_id: int | None = None, top_k: int = 20) -> list[dict]:
        """공백으로 나눈 키워드가 모두 포함된 청크를 찾는다(대소문자 무시). 임베딩/Ollama 불필요."""

        terms = [term for term in (query or '').split() if term]
        if not terms:
            return []
        stmt = (
            select(KnowledgeChunk, KnowledgeFile, KnowledgeFolder)
            .join(KnowledgeFile, KnowledgeChunk.file_id == KnowledgeFile.id)
            .join(KnowledgeFolder, KnowledgeFile.folder_id == KnowledgeFolder.id)
        )
        if folder_id is not None:
            stmt = stmt.where(KnowledgeFolder.id == folder_id)
        for term in terms:
            stmt = stmt.where(func.lower(KnowledgeChunk.content).like(f'%{term.lower()}%'))
        hits: list[dict] = []
        for chunk, file_row, folder in self.db.execute(stmt).all():
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
                'folder_id': folder.id,
                'folder_name': folder.name,
                'rel_path': file_row.rel_path,
                'chunk_count': file_row.chunk_count,
            }
            for file_row, folder in self.db.execute(stmt).all()
        ]
        return group_by_family(items)
