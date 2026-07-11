"""office-tools 상위 라우터 — 하위 서브라우터를 한 자리에서 마운트한다.

라우터-레벨 의존성으로 세션 로그인(``get_current_user``)을 강제한다. 따라서
모든 하위 엔드포인트(system/jobs/reports/charts/diagrams)는 미로그인 시 401 이다.

main.py 는 이 라우터를 prefix ``/api/v1/office-tools`` 로 등록한다. 최종 경로:
- ``/api/v1/office-tools/health``            (system)
- ``/api/v1/office-tools/capabilities``      (system)
- ``/api/v1/office-tools/jobs/{job_id}``     (jobs)
- ``/api/v1/office-tools/reports/...``       (reports, 다음 단계)
- ``/api/v1/office-tools/charts/...``        (charts, 다음 단계)
- ``/api/v1/office-tools/diagrams/...``      (diagrams, 다음 단계)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.modules.auth.dependencies import get_current_user
from app.modules.office_tools.api import charts, diagrams, jobs, reports, system

router = APIRouter(dependencies=[Depends(get_current_user)])

router.include_router(system.router)
router.include_router(jobs.router, prefix='/jobs')
router.include_router(reports.router, prefix='/reports')
router.include_router(charts.router, prefix='/charts')
router.include_router(diagrams.router, prefix='/diagrams')
