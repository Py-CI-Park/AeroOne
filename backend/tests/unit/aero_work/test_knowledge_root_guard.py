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


def test_alias_path_of_existing_folder_is_rejected(db: Session, tmp_path: Path) -> None:
    # B1: 같은 물리 폴더를 별칭(.., 하위→상위)으로 다른 문자열로 재등록하려 해도 실경로 정규화로 차단된다.
    real = tmp_path / 'kb-real'
    (real / 'sub').mkdir(parents=True)
    svc_a = KnowledgeService(db, _FakeEmbedder(), owner_id=1)
    svc_a.register_folder('A', str(real))
    db.commit()

    alias = str(real / 'sub' / '..')  # 실경로는 kb-real 로 동일
    svc_b = KnowledgeService(db, _FakeEmbedder(), owner_id=2)
    with pytest.raises(KnowledgeError, match='이미 등록'):
        svc_b.register_folder('B-별칭', alias)


def test_symlink_alias_of_existing_folder_is_rejected(db: Session, tmp_path: Path) -> None:
    # B1: symlink 별칭으로 같은 물리 폴더를 타 사용자가 재등록하는 우회도 실경로로 붕괴돼 차단된다.
    real = tmp_path / 'kb-real2'
    real.mkdir()
    KnowledgeService(db, _FakeEmbedder(), owner_id=1).register_folder('A', str(real))
    db.commit()

    link = tmp_path / 'kb-link'
    try:
        link.symlink_to(real, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip('이 환경에서 symlink 생성 불가(권한/OS)')
    with pytest.raises(KnowledgeError, match='이미 등록'):
        KnowledgeService(db, _FakeEmbedder(), owner_id=2).register_folder('B-링크', str(link))
