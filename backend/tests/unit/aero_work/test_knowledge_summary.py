"""지식 문서 요약 — 주입 chat·저장·실패 경로 단위 검증(실 LLM 없이)."""

from __future__ import annotations

from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.base import Base
from app.modules.aero_work import models as aero_work_models  # noqa: F401
from app.modules.aero_work.knowledge_service import KnowledgeService
from app.modules.aero_work.knowledge_summary import SummaryUnavailable, summarize_file

_TABLES = ('aero_work_knowledge_folders', 'aero_work_knowledge_files', 'aero_work_knowledge_chunks')


class FakeEmbedder:
    model = 'fake'

    def embed_one(self, text: str) -> list[float]:
        return [1.0]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] for _ in texts]


@pytest.fixture()
def session() -> Session:
    engine = sa.create_engine('sqlite://')
    Base.metadata.create_all(bind=engine, tables=[Base.metadata.tables[t] for t in _TABLES])
    with Session(engine) as db:
        yield db


def _indexed_file_id(session: Session, tmp_path: Path) -> int:
    root = tmp_path / 'kb'
    root.mkdir()
    (root / '예산지침.md').write_text('예산 편성 기준과 집행 절차를 정리한 문서', encoding='utf-8')
    service = KnowledgeService(session, FakeEmbedder())
    folder = service.register_folder('kb', str(root))
    session.commit()
    service.reindex(folder.id)
    session.commit()
    return folder.files[0].id


def test_summarize_stores_and_returns(session: Session, tmp_path: Path) -> None:
    file_id = _indexed_file_id(session, tmp_path)
    captured: dict = {}

    def fake_chat(settings, db, messages):
        captured['user'] = messages[1].content
        return '예산 편성 기준을 정리한 지침 문서임.'

    summary = summarize_file(Settings(app_env='test', jwt_secret_key='x'), session, file_id, chat=fake_chat)
    assert summary == '예산 편성 기준을 정리한 지침 문서임.'
    assert '예산지침.md' in captured['user'] and '예산 편성 기준' in captured['user']
    # 저장 확인 → wiki 가 summary 를 실어 나른다
    wiki = KnowledgeService(session, FakeEmbedder()).wiki()
    assert wiki[0]['representative']['summary'] == summary


def test_summarize_missing_file_and_chat_failure(session: Session, tmp_path: Path) -> None:
    settings = Settings(app_env='test', jwt_secret_key='x')
    with pytest.raises(SummaryUnavailable):
        summarize_file(settings, session, 99999, chat=lambda *a: 'x')

    file_id = _indexed_file_id(session, tmp_path)

    def boom(settings, db, messages):
        raise RuntimeError('down')

    with pytest.raises(SummaryUnavailable):
        summarize_file(settings, session, file_id, chat=boom)
