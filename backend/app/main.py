from __future__ import annotations

import logging

from contextlib import asynccontextmanager

from app.core.maintenance_gate_bootstrap import maintenance_gate_ready as _maintenance_gate_ready

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.core.config import Settings, ensure_runtime_directories, get_settings
from app.db.session import Database, get_engine
from app.modules.auth.services import preflight_configured_admin
from app.modules.auth.api import router as auth_router
from app.modules.admin.api import router as operations_admin_router
from app.modules.ai.api.public import router as ai_router
from app.modules.ai.api.admin import router as ai_admin_router
from app.modules.newsletter.api.admin import router as newsletter_admin_router
from app.modules.newsletter.api.imports import router as imports_router
from app.modules.newsletter.api.public import router as public_router
from app.modules.newsletter.services.newsletter_autosync_service import AutoSyncState
from app.modules.collections.api.public import router as collections_router
from app.modules.documents.api.public import router as documents_router
from app.modules.read_tracking.api.admin import router as read_events_admin_router
from app.modules.read_tracking.api.public import router as read_beacon_router
from app.modules.reports.api.public import router as reports_router
from app.modules.render.api import router as render_router
from app.modules.office_tools.api.router import router as office_tools_router
from app.modules.leantime.api import router as leantime_router
from app.modules.leantime.admin_api import router as leantime_admin_router
from app.modules.leantime.read_api import router as leantime_read_router
from app.modules.launchers.api import router as launchers_router
from app.modules.aero_work import api as aero_work_api
from app.modules.aero_work.api import router as aero_work_router
from app.modules.office_tools.core.job_store import OfficeJobStore
from app.modules.office_tools.upload_limits import (
    CHART_MULTIPART_LIMITS,
    REPORT_MULTIPART_LIMITS,
    OfficeMultipartIngressLimitMiddleware,
)

assert _maintenance_gate_ready

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    settings.validate_runtime_security()
    ensure_runtime_directories(settings)
    database = Database(settings.database_url)
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        preflight_configured_admin(database, settings)
        # H2: 이전 프로세스가 재색인 도중(status='indexing') 죽었으면 좀비 상태로 남는다 —
        # 인메모리 가드는 재시작으로 항상 비어 시작해 아무도 이어받지 않으므로 error 로
        # 리셋해 UI 가 영원히 '색인 중'에 멈추지 않게 한다(예외 안전 — 실패해도 기동은 계속).
        with database.session() as sweep_session:
            aero_work_api.reset_stale_indexing_folders(sweep_session)
        yield

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.state.settings = settings
    app.state.db = database
    office_job_store = OfficeJobStore.from_settings(settings)
    office_job_recovery = office_job_store.recover()
    app.state.office_job_store = office_job_store
    app.state.office_job_recovery_report = office_job_recovery
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

    @app.middleware('http')
    async def protect_activity_response(request: Request, call_next):
        if request.url.path != '/api/v1/auth/activity':
            return await call_next(request)
        try:
            response = await call_next(request)
        except Exception:
            logger.exception('Unhandled activity response failure')
            response = JSONResponse(
                status_code=500,
                content={'detail': 'Activity data is temporarily unavailable.'},
            )
        response.headers['Cache-Control'] = 'no-store'
        return response
    # FastAPI spools multipart bodies before endpoint code runs; count chunked
    # Office uploads here so the parser never receives an over-limit part.
    app.add_middleware(
        OfficeMultipartIngressLimitMiddleware,
        limits_by_path={
            '/api/v1/office-tools/charts/inspect': CHART_MULTIPART_LIMITS,
            '/api/v1/office-tools/charts/generate': CHART_MULTIPART_LIMITS,
            '/api/v1/office-tools/reports/generate': REPORT_MULTIPART_LIMITS,
        },
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

        try:
            recovery_inventory = app.state.office_job_store.list_recovery()
            recovery_items = recovery_inventory['items']
            if not isinstance(recovery_items, list):
                raise TypeError('recovery inventory items must be a list')
            office_job_unresolved_recovery_transactions = len(recovery_items)
            office_job_recovery_ok = office_job_unresolved_recovery_transactions == 0
        except Exception:
            office_job_unresolved_recovery_transactions = 0
            office_job_recovery_ok = False

        return {
            'status': 'ok' if db_ok and office_job_recovery_ok else 'degraded',
            'db_ok': db_ok,
            'office_job_recovery_ok': office_job_recovery_ok,
            'office_job_unresolved_recovery_transactions':
                office_job_unresolved_recovery_transactions,
            'import_root_exists': import_root_exists,
            'storage_root_exists': storage_root_exists,
        }

    app.include_router(auth_router, prefix='/api/v1/auth')
    app.include_router(public_router, prefix='/api/v1/newsletters')
    app.include_router(newsletter_admin_router, prefix='/api/v1/admin')
    app.include_router(imports_router, prefix='/api/v1/admin')
    app.include_router(operations_admin_router, prefix='/api/v1/admin')
    # 읽음추적: 공개 비콘(POST /newsletters/{id}/read)과 관리자 조회/purge(/admin/read-events).
    app.include_router(read_beacon_router, prefix='/api/v1/newsletters')
    app.include_router(read_events_admin_router, prefix='/api/v1/admin')
    # 정적 보고서(민간 항공기 종합 분석 등) — DB/달력 없이 _database/civil_aircraft 의 HTML 을 sanitize 해 제공.
    app.include_router(reports_router, prefix='/api/v1/reports')
    # 문서 보관소 — _database/document 의 HTML 을 폴더 트리로 목록화하고 선택 1개를 sanitize 해 제공.
    app.include_router(documents_router, prefix='/api/v1/documents')
    # HTML 컬렉션 공유 라우터 — document/civil/nsa 화이트리스트로 목록/본문을 한 자리에서 제공.
    app.include_router(collections_router, prefix='/api/v1/collections')
    # 폐쇄망 Ollama AI — 브라우저는 same-origin 프록시만 호출하고, 백엔드가 Ollama 와 통신한다.
    app.include_router(ai_router, prefix='/api/v1/ai')
    # LLM 연결 레지스트리(관리자) — OpenAI 호환 엔드포인트 등록/암호화/검증. admin 프록시 재사용을 위해 /api/v1/admin.
    app.include_router(ai_admin_router, prefix='/api/v1/admin')
    # stateless 렌더 — 원본 텍스트(markdown/html)를 서버 sanitize HTML 로 변환한다. 저장소/경로 접근 없음.
    app.include_router(render_router, prefix='/api/v1/render')
    # office-tools(보고서/차트/다이어그램) — 로그인 필수. 산출물은 파일 JobStore 에 사용자 스코프로 저장.
    app.include_router(office_tools_router, prefix='/api/v1/office-tools')
    app.include_router(leantime_router, prefix='/api/v1/leantime')
    # Leantime 서버측 연결 레지스트리(관리자) — base_url + 암호화 scoped API key 등록/검증/회전/삭제.
    app.include_router(leantime_admin_router, prefix='/api/v1/admin')
    # Leantime 읽기 어댑터 — 프로젝트·작업·일정 요약을 서버 JSON-RPC 프록시로 제공(leantime.read).
    app.include_router(leantime_read_router, prefix='/api/v1/leantime')
    # 외부 앱 런처(Open Notebook/OpenWebUI) 헬스 배지 — loopback 전용 TCP+HTTP 프로브.
    app.include_router(launchers_router, prefix='/api/v1/launchers')
    # Aero Work 지식폴더 — 로그인 필수. 지정 폴더 in-place 색인 + Ollama 임베딩 벡터 검색(폐쇄망 순도).
    app.include_router(aero_work_router, prefix='/api/v1/aero-work')
    return app


app = create_app()
