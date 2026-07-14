"""office-tools 상위 라우터 — 하위 서브라우터를 한 자리에서 마운트한다.

라우터-레벨 의존성으로 세션 로그인(``get_current_user``)과 정확한
``office.use`` 권한을 강제한다. 따라서 모든 하위 엔드포인트는 미로그인 시 401,
로그인했지만 권한이 없으면 403 이다.

main.py 는 이 라우터를 prefix ``/api/v1/office-tools`` 로 등록한다. 최종 경로:
- ``/api/v1/office-tools/health``            (system)
- ``/api/v1/office-tools/capabilities``      (system)
- ``/api/v1/office-tools/jobs/{job_id}``     (jobs)
- ``/api/v1/office-tools/reports/...``       (reports)
- ``/api/v1/office-tools/charts/...``        (charts)
- ``/api/v1/office-tools/diagrams/...``      (diagrams)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.modules.auth.dependencies import get_current_user, require_permission
from app.modules.office_tools.api import charts, diagrams, jobs, reports, samples, system

router = APIRouter(dependencies=[Depends(get_current_user), Depends(require_permission('office.use'))])

router.include_router(system.router)
router.include_router(samples.router, prefix='/samples')
router.include_router(jobs.router, prefix='/jobs')
router.include_router(reports.router, prefix='/reports')
router.include_router(charts.router, prefix='/charts')
router.include_router(diagrams.router, prefix='/diagrams')
