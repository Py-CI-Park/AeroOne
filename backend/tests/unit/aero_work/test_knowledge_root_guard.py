# -*- coding: utf-8 -*-
"""AW-R01: 지식폴더 등록 허용 루트 path-guard 단위 테스트."""
from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.modules.aero_work import models as aero_models  # noqa: F401  (테이블 등록)
from app.modules.aero_work.knowledge_service import KnowledgeError, KnowledgeService


class _FakeEmbedder:
    model = 'fake-embed'

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] for _ in texts]

    def embed_one(self, text: str) -> list[float]:
        return [0.0]


@pytest.fixture()
def db() -> Session:
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _svc(db: Session) -> KnowledgeService:
    return KnowledgeService(db, _FakeEmbedder())


def test_allowed_roots_empty_permits_any_absolute_dir(db: Session, tmp_path: Path) -> None:
    # 허용 루트가 비어 있으면(하위호환) 임의 절대 디렉터리 등록 가능.
    folder = _svc(db).register_folder('kb', str(tmp_path), allowed_roots=[])
    assert folder.path


def test_path_inside_allowed_root_is_accepted(db: Session, tmp_path: Path) -> None:
    root = tmp_path / 'kb-root'
    sub = root / '부서자료'
    sub.mkdir(parents=True)
    folder = _svc(db).register_folder('부서', str(sub), allowed_roots=[str(root)])
    assert '부서자료' in folder.path


def test_path_outside_allowed_root_is_rejected(db: Session, tmp_path: Path) -> None:
    root = tmp_path / 'kb-root'
    root.mkdir()
    outside = tmp_path / 'secret'
    outside.mkdir()
    with pytest.raises(KnowledgeError, match='허용된 지식 루트'):
        _svc(db).register_folder('탈출', str(outside), allowed_roots=[str(root)])


def test_symlink_escape_outside_root_is_rejected(db: Session, tmp_path: Path) -> None:
    # 허용 루트 안의 symlink 가 루트 밖을 가리켜도 resolve() 실경로로 차단한다.
    root = tmp_path / 'kb-root'
    root.mkdir()
    outside = tmp_path / 'outside-target'
    outside.mkdir()
    link = root / 'escape'
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip('이 환경에서 symlink 생성 불가(권한/OS)')
    with pytest.raises(KnowledgeError, match='허용된 지식 루트'):
        _svc(db).register_folder('링크탈출', str(link), allowed_roots=[str(root)])
