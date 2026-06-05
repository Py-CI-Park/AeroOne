from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.core.config import Settings, ensure_runtime_directories, get_settings
from app.db.session import Database, get_engine
from app.modules.auth.api import router as auth_router
from app.modules.newsletter.api.admin import router as admin_router
from app.modules.newsletter.api.imports import router as imports_router
from app.modules.newsletter.api.public import router as public_router
from app.modules.newsletter.services.newsletter_autosync_service import AutoSyncState
from app.modules.collections.api.public import router as collections_router
from app.modules.documents.api.public import router as documents_router
from app.modules.read_tracking.api.admin import router as read_events_admin_router
from app.modules.read_tracking.api.public import router as read_beacon_router
from app.modules.reports.api.public import router as reports_router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    settings.validate_runtime_security()
    ensure_runtime_directories(settings)
    database = Database(settings.database_url)
    app = FastAPI(title=settings.app_name)
    app.state.settings = settings
    app.state.db = database
    # 공개 읽기 경로의 지연 자동 동기화 상태(프로세스 1개 공유). 운영자가
    # _database/newsletter 에 파일을 넣으면 서버 재시작 없이 다음 페이지 로드에서 반영된다.
    app.state.autosync_state = AutoSyncState()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )
    app.mount('/storage/thumbnails', StaticFiles(directory=settings.thumbnails_root), name='thumbnails')

    @app.get('/api/v1/health')
    def health() -> dict[str, object]:
        import_root_exists = settings.import_root.exists()
        storage_root_exists = settings.managed_storage_root.exists()
        db_ok = True
        try:
            with get_engine().connect() as connection:
                connection.execute(text('SELECT 1'))
        except Exception:
            db_ok = False
        return {
            'status': 'ok' if db_ok else 'degraded',
            'db_ok': db_ok,
            'import_root_exists': import_root_exists,
            'storage_root_exists': storage_root_exists,
        }

    app.include_router(auth_router, prefix='/api/v1/auth')
    app.include_router(public_router, prefix='/api/v1/newsletters')
    app.include_router(admin_router, prefix='/api/v1/admin')
    app.include_router(imports_router, prefix='/api/v1/admin')
    # 읽음추적: 공개 비콘(POST /newsletters/{id}/read)과 관리자 조회/purge(/admin/read-events).
    app.include_router(read_beacon_router, prefix='/api/v1/newsletters')
    app.include_router(read_events_admin_router, prefix='/api/v1/admin')
    # 정적 보고서(민간 항공기 종합 분석 등) — DB/달력 없이 _database/civil_aircraft 의 HTML 을 sanitize 해 제공.
    app.include_router(reports_router, prefix='/api/v1/reports')
    # 문서 보관소 — _database/document 의 HTML 을 폴더 트리로 목록화하고 선택 1개를 sanitize 해 제공.
    app.include_router(documents_router, prefix='/api/v1/documents')
    # HTML 컬렉션 공유 라우터 — document/civil/nsa 화이트리스트로 목록/본문을 한 자리에서 제공.
    app.include_router(collections_router, prefix='/api/v1/collections')
    return app


app = create_app()
