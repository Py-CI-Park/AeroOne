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


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    ensure_runtime_directories(settings)
    database = Database(settings.database_url)
    app = FastAPI(title=settings.app_name)
    app.state.settings = settings
    app.state.db = database
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )
    app.mount('/storage', StaticFiles(directory=settings.managed_storage_root), name='storage')

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
    return app


app = create_app()
