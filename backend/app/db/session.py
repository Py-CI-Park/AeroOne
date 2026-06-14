from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def _normalize_database_url(database_url: str) -> str:
    prefix = 'sqlite:///'
    if database_url.startswith(prefix) and not database_url.startswith('sqlite:////'):
        raw = database_url[len(prefix):]
        path = Path(raw)
        if not path.is_absolute():
            return f"sqlite:///{(get_settings().project_root / path).resolve()}"
    return database_url


def _enable_sqlite_foreign_keys(engine):
    """SQLite 연결마다 PRAGMA foreign_keys=ON 을 건다.

    SQLite 는 연결별로 명시하지 않으면 FK 제약(ondelete=CASCADE 포함)을 강제하지
    않는다. 운영 엔진에서 이걸 켜지 않으면 ai_conversations 삭제 시 ai_messages/
    citations 가 고아로 남아(삭제=실제 삭제가 아님) 프라이버시 결함이 되고, SQLite
    rowid 재사용으로 타 세션 고아 메시지가 새 대화에 붙는 교차 노출 경로가 생긴다.
    테스트 픽스처와 동일하게 운영 엔진에도 적용해 패리티를 맞춘다.
    """

    if engine.url.get_backend_name() == 'sqlite':
        @event.listens_for(engine, 'connect')
        def _set_sqlite_pragma(dbapi_connection, _connection_record):  # noqa: ANN001
            cursor = dbapi_connection.cursor()
            cursor.execute('PRAGMA foreign_keys=ON')
            cursor.close()
    return engine

class Database:
    def __init__(self, database_url: str) -> None:
        database_url = _normalize_database_url(database_url)
        connect_args = {'check_same_thread': False} if database_url.startswith('sqlite') else {}
        self.engine = _enable_sqlite_foreign_keys(create_engine(database_url, connect_args=connect_args, future=True))
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False)

    @contextmanager
    def session(self) -> Session:
        db = self.session_factory()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


@lru_cache(maxsize=1)
def get_engine():
    settings = get_settings()
    normalized_url = _normalize_database_url(settings.database_url)
    connect_args = {'check_same_thread': False} if normalized_url.startswith('sqlite') else {}
    return _enable_sqlite_foreign_keys(create_engine(normalized_url, future=True, connect_args=connect_args))


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)


def reset_db_caches() -> None:
    get_session_factory.cache_clear()
    get_engine.cache_clear()


def get_db_session() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
