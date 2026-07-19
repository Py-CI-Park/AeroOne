"""Aero Work 지식폴더 서비스 — 색인/증분/검색/오류 경로 단위 검증.

실 Ollama 없이 결정적 bag-of-vocab 임베더를 주입해 코사인 검색 관련성과 증분 동기화를
검증한다(``KnowledgeService`` 는 임베더를 생성자 주입받는다).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.db.base import Base
from app.modules.aero_work import models as aero_work_models  # noqa: F401  (register tables)
from app.modules.aero_work.embedding_client import EmbeddingUnavailable
from app.modules.aero_work.knowledge_service import (
    KnowledgeError,
    KnowledgeService,
    chunk_text,
    cosine_similarity,
)


class FakeEmbedder:
    """결정적 bag-of-vocab 벡터 — 어휘 겹침이 코사인 유사도로 드러난다."""

    model = 'fake-embed'
    VOCAB = (
        'apple', 'banana', 'cherry', 'report', 'meeting', 'schedule',
        'aero', 'work', 'knowledge', 'folder', 'rocket', 'engine',
    )

    def __init__(self) -> None:
        self.embed_calls = 0

    def embed_one(self, text: str) -> list[float]:
        low = text.lower()
        return [float(low.count(term)) for term in self.VOCAB]

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.embed_calls += 1
        return [self.embed_one(text) for text in texts]


class FailingEmbedder(FakeEmbedder):
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise EmbeddingUnavailable('Ollama 미기동')

    def embed_one(self, text: str) -> list[float]:
        raise EmbeddingUnavailable('Ollama 미기동')


@pytest.fixture()
def session() -> Session:
    engine = sa.create_engine('sqlite://')
    sa.event.listen(engine, 'connect', lambda conn, _rec: conn.execute('PRAGMA foreign_keys=ON'))
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Base.metadata.tables['aero_work_knowledge_folders'],
            Base.metadata.tables['aero_work_knowledge_files'],
            Base.metadata.tables['aero_work_knowledge_chunks'],
        ],
    )
    with Session(engine) as db:
        yield db


def _seed_folder(tmp_path: Path) -> Path:
    root = tmp_path / 'kb'
    root.mkdir()
    (root / 'fruit.md').write_text('# Fruit\n\napple apple banana. cherry.', encoding='utf-8')
    (root / 'ops.txt').write_text('weekly meeting schedule report.', encoding='utf-8')
    (root / 'ignore.bin').write_bytes(b'\x00\x01\x02')  # 미지원 확장자 → 색인 제외
    return root


def test_register_reindex_and_search(session: Session, tmp_path: Path) -> None:
    root = _seed_folder(tmp_path)
    service = KnowledgeService(session, FakeEmbedder())

    folder = service.register_folder('업무 지식', str(root))
    session.commit()
    assert folder.status == 'pending'

    indexed = service.reindex(folder.id)
    session.commit()
    assert indexed.status == 'ready'
    assert indexed.file_count == 2  # ignore.bin 은 제외
    assert indexed.chunk_count >= 2

    fruit_hits = service.search('apple', top_k=5)
    assert fruit_hits, '과일 문서가 검색되어야 한다'
    assert fruit_hits[0]['rel_path'] == 'fruit.md'
    assert fruit_hits[0]['score'] > 0

    ops_hits = service.search('meeting report')
    assert ops_hits[0]['rel_path'] == 'ops.txt'


def test_incremental_sync_add_modify_delete(session: Session, tmp_path: Path) -> None:
    root = _seed_folder(tmp_path)
    service = KnowledgeService(session, FakeEmbedder())
    folder = service.register_folder('kb', str(root))
    session.commit()
    service.reindex(folder.id)
    session.commit()
    assert folder.file_count == 2

    # 추가
    (root / 'launch.md').write_text('rocket engine knowledge base.', encoding='utf-8')
    service.reindex(folder.id)
    session.commit()
    assert folder.file_count == 3
    assert service.search('rocket')[0]['rel_path'] == 'launch.md'

    # 수정(내용·크기 변경 → 시그니처 변경 → 재임베딩)
    (root / 'fruit.md').write_text('cherry cherry only now.', encoding='utf-8')
    service.reindex(folder.id)
    session.commit()
    assert service.search('apple') == []  # apple 제거됨

    # 삭제
    (root / 'ops.txt').unlink()
    service.reindex(folder.id)
    session.commit()
    assert folder.file_count == 2
    assert all(hit['rel_path'] != 'ops.txt' for hit in service.search('meeting'))


def test_reindex_skips_unchanged_files(session: Session, tmp_path: Path) -> None:
    root = _seed_folder(tmp_path)
    embedder = FakeEmbedder()
    service = KnowledgeService(session, embedder)
    folder = service.register_folder('kb', str(root))
    session.commit()
    service.reindex(folder.id)
    session.commit()
    calls_after_first = embedder.embed_calls
    assert calls_after_first > 0

    # 변경 없이 재색인 → 추가 임베딩 호출 없음(증분 스킵)
    service.reindex(folder.id)
    session.commit()
    assert embedder.embed_calls == calls_after_first


def test_register_rejects_missing_and_duplicate(session: Session, tmp_path: Path) -> None:
    root = _seed_folder(tmp_path)
    service = KnowledgeService(session, FakeEmbedder())
    with pytest.raises(KnowledgeError):
        service.register_folder('x', str(tmp_path / 'does-not-exist'))
    service.register_folder('kb', str(root))
    session.commit()
    with pytest.raises(KnowledgeError):
        service.register_folder('kb2', str(root))


def test_reindex_marks_error_when_embedder_unavailable(session: Session, tmp_path: Path) -> None:
    root = _seed_folder(tmp_path)
    service = KnowledgeService(session, FailingEmbedder())
    folder = service.register_folder('kb', str(root))
    session.commit()
    with pytest.raises(EmbeddingUnavailable):
        service.reindex(folder.id)
    session.commit()
    assert folder.status == 'error'
    assert 'Ollama' in folder.status_detail


def test_chunk_text_and_cosine_units() -> None:
    assert chunk_text('') == []
    assert chunk_text('   \n  ') == []
    long_text = '\n'.join(f'line {i} ' + 'x' * 40 for i in range(200))
    pieces = chunk_text(long_text, size=300, overlap=50)
    assert len(pieces) > 1
    assert all(len(piece) <= 300 for piece in pieces)

    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine_similarity([], [1.0]) == 0.0
    assert cosine_similarity([1.0], [1.0, 2.0]) == 0.0
