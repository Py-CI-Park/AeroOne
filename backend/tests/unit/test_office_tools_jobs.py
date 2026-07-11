"""jobs 라우터의 소유권 스코프 + 경로 방어 검증.

JobStore 를 tmp 루트로 주입(의존성 오버라이드)해 실제 저장소를 오염시키지 않는다.
소유자는 job/artifact/bundle 을 받고, 타인은 403, 잘못된 id/경로 탈출은 404.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.modules.auth.models import User
from app.modules.office_tools.api.jobs import get_office_job_store
from app.modules.office_tools.core.job_store import OfficeJobStore


def _admin_id(app) -> int:
    with app.state.db.session() as session:
        return session.execute(select(User).where(User.username == 'admin')).scalar_one().id


def test_owner_reads_job_and_artifact(app, csrf_client: TestClient, tmp_path: Path) -> None:
    store = OfficeJobStore(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        owner = _admin_id(app)
        record = store.create('report', owner_id=owner)
        store.write_text(record['job_id'], 'aeroone_report.md', '# hi', 'text/markdown')
        job_id = record['job_id']

        resp = csrf_client.get(f'/api/v1/office-tools/jobs/{job_id}')
        assert resp.status_code == 200
        assert resp.json()['owner_id'] == owner

        art = csrf_client.get(f'/api/v1/office-tools/jobs/{job_id}/artifacts/aeroone_report.md')
        assert art.status_code == 200
        assert art.content == b'# hi'

        bundle = csrf_client.get(f'/api/v1/office-tools/jobs/{job_id}/bundle')
        assert bundle.status_code == 200
        assert bundle.headers['content-type'] == 'application/zip'
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)


def test_other_owner_forbidden(app, csrf_client: TestClient, tmp_path: Path) -> None:
    store = OfficeJobStore(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        foreign = store.create('report', owner_id=_admin_id(app) + 9999)
        resp = csrf_client.get(f"/api/v1/office-tools/jobs/{foreign['job_id']}")
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)


def test_invalid_job_id_and_traversal_blocked(app, csrf_client: TestClient, tmp_path: Path) -> None:
    store = OfficeJobStore(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        # 정규식 [0-9a-f]{32} 밖 → 404.
        assert csrf_client.get('/api/v1/office-tools/jobs/not-a-valid-id').status_code == 404
        # 소유 job 이라도 경로 탈출 파일명은 safe_name 정규화로 디렉터리 밖을 못 가리켜 404.
        record = store.create('report', owner_id=_admin_id(app))
        resp = csrf_client.get(f"/api/v1/office-tools/jobs/{record['job_id']}/artifacts/..%2f..%2fjob.json")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)
