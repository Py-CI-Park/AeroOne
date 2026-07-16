"""office-tools 공통 인증·권한·CSRF 경계 검증.

모든 Office API 는 미로그인 시 401, ``office.use`` 가 없는 일반 사용자는 403 이어야 한다.
Office mutation은 관리자에게도 세션 CSRF 토큰을 요구하며, capabilities 는 base_url 을 노출하지 않는다.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.modules.admin.models import AdminAuditEvent, UserPermission
from app.modules.auth.repositories import UserRepository
from app.modules.office_tools.api.jobs import get_office_job_store
from app.modules.office_tools.core.job_store import OfficeJobStore

_VALID_JOB_ID = 'a' * 32  # 정규식 [0-9a-f]{32} 을 만족하지만 존재하지 않는 job.
_CSV = '지역,매출\n서울,120\n부산,80\n'.encode('utf-8')
_GET_ENDPOINTS = (
    '/api/v1/office-tools/health',
    '/api/v1/office-tools/capabilities',
    '/api/v1/office-tools/samples',
    '/api/v1/office-tools/samples/diagram-flow',
    f'/api/v1/office-tools/jobs/{_VALID_JOB_ID}',
    '/api/v1/office-tools/jobs',
)
_POST_ENDPOINTS = (
    'reports/generate',
    'charts/inspect',
    'charts/generate',
    'diagrams/generate',
    'jobs/admin/purge',
)
_ADMIN_OFFICE_MANAGEMENT_ROUTES = (
    pytest.param(
        'GET',
        '/api/v1/office-tools/jobs/quarantine',
        'quarantine',
        None,
        id='quarantine-inventory',
    ),
    pytest.param(
        'DELETE',
        '/api/v1/office-tools/jobs/quarantine/{quarantine_id}',
        'quarantine',
        'office_jobs.quarantine.delete',
        id='quarantine-delete',
    ),
    pytest.param(
        'POST',
        '/api/v1/office-tools/jobs/quarantine/{quarantine_id}/restore',
        'quarantine',
        'office_jobs.quarantine.restore',
        id='quarantine-restore',
    ),
    pytest.param(
        'GET',
        '/api/v1/office-tools/jobs/recovery',
        'recovery',
        None,
        id='recovery-inventory',
    ),
    pytest.param(
        'DELETE',
        '/api/v1/office-tools/jobs/recovery/{recovery_id}',
        'recovery',
        'office_jobs.recovery.delete',
        id='recovery-discard',
    ),
    pytest.param(
        'GET',
        '/api/v1/office-tools/jobs/storage',
        'storage',
        None,
        id='storage-accounting',
    ),
    pytest.param(
        'DELETE',
        '/api/v1/office-tools/jobs/evidence/{management_token}',
        'evidence',
        'office_jobs.evidence.dispose',
        id='corrupt-evidence-disposition',
    ),
)


def _assert_completed_durability(outcome: dict[str, object], *, owner: bool = False) -> None:
    expected = 'platform_best_effort' if os.name == 'nt' else 'synced'
    assert outcome['durability'] == expected
    assert outcome['durably_synced'] is (expected == 'synced')
    assert outcome['retry_required'] is False
    if owner:
        assert outcome['owner_identity_durability'] == expected
        assert outcome['owner_identity_durably_synced'] is (expected == 'synced')


def _management_request(
    client: TestClient,
    method: str,
    endpoint: str,
    csrf_token: str | None = None,
):
    headers = {} if csrf_token is None else {'x-csrf-token': csrf_token}
    return client.request(method, endpoint, headers=headers)


def _seed_recovery_evidence(store: OfficeJobStore, marker: str) -> dict[str, object]:
    transaction_id = f'create-{marker * 32}'
    store._preserve_unresolved_recovery(None, transaction_id, 'management authorization matrix')
    return next(
        item
        for item in store.list_recovery()['items']
        if item['transaction_id'] == transaction_id
    )


def _seed_quarantine_evidence(store: OfficeJobStore, marker: str) -> dict[str, object]:
    job = store.create('report', owner_id=1)
    store.write_bytes(
        job['job_id'],
        f'{marker}-evidence.txt',
        f'{marker}-quarantine-evidence'.encode('utf-8'),
        'text/plain',
    )
    store.complete(job['job_id'])
    quarantine_item = store._quarantine_corrupt_job(
        store.job_dir(job['job_id']),
        'management authorization matrix',
    )
    assert quarantine_item is not None
    return quarantine_item


def _seed_corrupt_evidence(
    store: OfficeJobStore,
    marker: str,
) -> tuple[dict[str, object], Path]:
    evidence = store._quarantine_root / f'{marker}-malformed-evidence'
    evidence.mkdir()
    (evidence / 'payload.bin').write_bytes(f'{marker}-corrupt-evidence'.encode('utf-8'))
    corrupt_items = [
        item for item in store.list_quarantine()['items'] if item['kind'] == 'corrupt'
    ]
    assert len(corrupt_items) == 1
    assert corrupt_items[0]['management_token'] is not None
    return corrupt_items[0], evidence


def _seed_admin_office_management_evidence(store: OfficeJobStore) -> dict[str, dict[str, object]]:
    return {
        'quarantine': _seed_quarantine_evidence(store, 'target'),
        'other_quarantine': _seed_quarantine_evidence(store, 'other'),
        'recovery': _seed_recovery_evidence(store, 'a'),
        'other_recovery': _seed_recovery_evidence(store, 'b'),
    }


def _directory_snapshot(directory) -> tuple[tuple[str, str, bytes | None], ...]:
    return tuple(
        (
            path.relative_to(directory).as_posix(),
            'directory' if path.is_dir() else 'file',
            path.read_bytes() if path.is_file() else None,
        )
        for path in sorted(directory.rglob('*'))
    )


def _office_store_snapshot(store: OfficeJobStore) -> dict[str, object]:
    return {
        'quarantine': store.list_quarantine(),
        'recovery': store.list_recovery(),
        'storage': store.storage_accounting(),
        'filesystem': _directory_snapshot(store.root),
    }


def _owned_job_snapshot(
    store: OfficeJobStore,
    job_id: str,
    owner_id: int,
) -> dict[str, object]:
    record = store.get(job_id)
    job_dir = store.job_dir(job_id)
    return {
        'job': record,
        'artifacts': {
            artifact['filename']: (job_dir / artifact['filename']).read_bytes()
            for artifact in record['artifacts']
        },
        'usage': store.usage_for_owner(owner_id),
        'directory': _directory_snapshot(job_dir),
    }


def _management_audit_events(app, target_id: str, action: str) -> list[AdminAuditEvent]:
    with app.state.db.session() as session:
        return session.scalars(
            select(AdminAuditEvent)
            .where(
                AdminAuditEvent.target_id == target_id,
                AdminAuditEvent.action.in_([f'{action}.intent', action]),
            )
            .order_by(AdminAuditEvent.id)
        ).all()


def _office_management_audit_events(app) -> list[AdminAuditEvent]:
    with app.state.db.session() as session:
        return session.scalars(
            select(AdminAuditEvent)
            .where(AdminAuditEvent.action.like('office_jobs.%'))
            .order_by(AdminAuditEvent.id)
        ).all()



def _assert_denied_management_request(
    app,
    store: OfficeJobStore,
    response,
    *,
    expected_status: int,
    baseline: dict[str, object],
    target_id: str | None,
    audit_action: str | None,
) -> None:
    assert response.status_code == expected_status
    assert _office_store_snapshot(store) == baseline
    if audit_action is not None:
        assert target_id is not None
        assert _management_audit_events(app, target_id, audit_action) == []


def _assert_successful_management_audit(
    app,
    *,
    target_id: str,
    audit_action: str,
    manager_id: int,
) -> None:
    events = _management_audit_events(app, target_id, audit_action)
    assert [(event.action, event.status, event.actor_user_id) for event in events] == [
        (f'{audit_action}.intent', 'intent', manager_id),
        (audit_action, 'success', manager_id),
    ]



def _user_client(
    app,
    username: str,
    *,
    permission_keys: tuple[str, ...] = (),
    role: str = 'user',
) -> tuple[TestClient, str, int]:
    password = f'{username}-test-password'
    with app.state.db.session() as session:
        user = UserRepository(session).create(
            username=username,
            password_hash=hash_password(password),
            role=role,
        )
        for permission_key in permission_keys:
            session.add(UserPermission(user_id=user.id, permission_key=permission_key))

    client = TestClient(app)
    login = client.post('/api/v1/auth/login', json={'username': username, 'password': password})
    assert login.status_code == 200
    return client, login.json()['csrf_token'], user.id


def _office_post(client: TestClient, endpoint: str, csrf_token: str | None):
    headers = {} if csrf_token is None else {'x-csrf-token': csrf_token}
    url = f'/api/v1/office-tools/{endpoint}'
    if endpoint == 'reports/generate':
        return client.post(
            url,
            headers=headers,
            files={'markdown_file': ('input.md', '# 테스트'.encode('utf-8'), 'text/markdown')},
        )
    if endpoint in {'charts/inspect', 'charts/generate'}:
        return client.post(
            url,
            headers=headers,
            files={'data_file': ('sales.csv', _CSV, 'text/csv')},
        )
    if endpoint == 'diagrams/generate':
        return client.post(
            url,
            headers=headers,
            json={'description': '승인 요청을 검토하고 결과를 알린다.', 'ai_assist': False},
        )
    if endpoint == 'jobs/admin/purge':
        return client.post(url, headers=headers)
    raise AssertionError(f'unknown Office POST endpoint: {endpoint}')


def test_health_ok_when_logged_in(csrf_client: TestClient) -> None:
    resp = csrf_client.get('/api/v1/office-tools/health')
    assert resp.status_code == 200
    body = resp.json()
    assert body['status'] == 'ok'
    assert isinstance(body['service'], str) and body['service']


def test_capabilities_reports_services_and_hides_base_url(csrf_client: TestClient) -> None:
    resp = csrf_client.get('/api/v1/office-tools/capabilities')
    assert resp.status_code == 200
    body = resp.json()
    assert body['services'] == {'report': True, 'chart': True, 'diagram': True}
    # 활성 LLM 연결이 없는 상태 → active False, 규칙기반 폴백 신호.
    assert body['llm']['active'] is False
    assert body['llm']['fallback'] == 'rule-based'
    # base_url/api_key 는 어떤 형태로도 노출되지 않는다.
    assert 'base_url' not in resp.text
    assert 'api_key' not in resp.text


def test_jobs_unknown_id_returns_404_when_logged_in(csrf_client: TestClient) -> None:
    # 로그인 상태에서 존재하지 않는(하지만 형식은 유효한) job → 404(401 아님).
    assert csrf_client.get(f'/api/v1/office-tools/jobs/{_VALID_JOB_ID}').status_code == 404


@pytest.mark.parametrize('endpoint', _GET_ENDPOINTS)
def test_all_office_get_endpoints_require_login(client: TestClient, endpoint: str) -> None:
    assert client.get(endpoint).status_code == 401


@pytest.mark.parametrize('endpoint', _POST_ENDPOINTS)
def test_all_office_post_endpoints_require_login(client: TestClient, endpoint: str) -> None:
    assert _office_post(client, endpoint, csrf_token=None).status_code == 401


@pytest.mark.parametrize('endpoint', _GET_ENDPOINTS)
def test_pending_user_without_office_use_is_denied_get_access(app, endpoint: str) -> None:
    # 1.16.3 부터 발급 계정(user 역할)은 office.use 를 기본 보유한다. 권한 없는
    # 인증 주체의 403 경로는 역할 기본 권한이 빈 pending 계정으로 검증한다.
    plain_client, _, _ = _user_client(app, 'plain', role='pending')
    assert plain_client.get(endpoint).status_code == 403


@pytest.mark.parametrize('endpoint', _POST_ENDPOINTS)
def test_pending_user_without_office_use_is_denied_post_access(app, endpoint: str) -> None:
    plain_client, csrf_token, _ = _user_client(app, 'plain', role='pending')
    assert _office_post(plain_client, endpoint, csrf_token).status_code == 403

def test_delegated_office_user_can_use_all_user_facing_routes(app, tmp_path) -> None:
    store = OfficeJobStore(
        tmp_path / 'office_jobs',
        max_jobs_per_owner=3,
        min_free_bytes=0,
    )
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        delegated, csrf_token, delegated_id = _user_client(
            app,
            'delegated-office-user',
            permission_keys=('office.use',),
        )

        health = delegated.get('/api/v1/office-tools/health')
        assert health.status_code == 200
        assert health.json()['status'] == 'ok'

        capabilities = delegated.get('/api/v1/office-tools/capabilities')
        assert capabilities.status_code == 200
        assert capabilities.json()['services'] == {'report': True, 'chart': True, 'diagram': True}

        samples = delegated.get('/api/v1/office-tools/samples')
        assert samples.status_code == 200
        assert 'diagram-flow' in {sample['key'] for sample in samples.json()}
        sample = delegated.get('/api/v1/office-tools/samples/diagram-flow')
        assert sample.status_code == 200
        assert sample.json()['key'] == 'diagram-flow'
        assert sample.json()['content']

        report = delegated.post(
            '/api/v1/office-tools/reports/generate',
            headers={'x-csrf-token': csrf_token},
            files={'markdown_file': ('input.md', '# 위임 보고서'.encode('utf-8'), 'text/markdown')},
        )
        assert report.status_code == 200
        report_job = report.json()
        assert report_job['status'] == 'completed'
        assert '위임 보고서' in report_job['html']

        inspected = delegated.post(
            '/api/v1/office-tools/charts/inspect',
            headers={'x-csrf-token': csrf_token},
            files={'data_file': ('sales.csv', _CSV, 'text/csv')},
        )
        assert inspected.status_code == 200
        assert inspected.json()['row_count'] == 2
        assert inspected.json()['column_count'] == 2

        chart = delegated.post(
            '/api/v1/office-tools/charts/generate',
            headers={'x-csrf-token': csrf_token},
            data={'prompt': '지역별 매출', 'ai_assist': 'false', 'chart_type': 'bar'},
            files={'data_file': ('sales.csv', _CSV, 'text/csv')},
        )
        assert chart.status_code == 200
        chart_job = chart.json()
        assert chart_job['status'] == 'completed'
        assert chart_job['chart_spec']['type'] == 'bar'
        assert chart_job['echarts_option']['series'][0]['type'] == 'bar'

        diagram = delegated.post(
            '/api/v1/office-tools/diagrams/generate',
            headers={'x-csrf-token': csrf_token},
            json={'description': '접수 후 검토하고 승인 결과를 알린다.', 'ai_assist': False},
        )
        assert diagram.status_code == 200
        diagram_job = diagram.json()
        assert diagram_job['status'] == 'completed'
        assert diagram_job['diagram_type'] == 'flowchart'
        assert diagram_job['mermaid']

        generated_jobs = {
            'report': report_job,
            'chart': chart_job,
            'diagram': diagram_job,
        }
        generated_job_ids = {job['job_id'] for job in generated_jobs.values()}
        assert len(generated_job_ids) == len(generated_jobs)

        jobs = delegated.get('/api/v1/office-tools/jobs')
        assert jobs.status_code == 200
        jobs_body = jobs.json()
        assert {job['job_id'] for job in jobs_body['jobs']} == generated_job_ids
        assert jobs_body['usage']['job_count'] == len(generated_jobs)
        assert jobs_body['usage']['total_bytes'] > 0

        for service, generated_job in generated_jobs.items():
            detail = delegated.get(f"/api/v1/office-tools/jobs/{generated_job['job_id']}")
            assert detail.status_code == 200
            assert detail.json()['service'] == service
            assert detail.json()['owner_id'] == delegated_id

        report_artifact = report_job['artifacts'][0]
        artifact = delegated.get(report_artifact['download_url'])
        assert artifact.status_code == 200
        assert artifact.content == store.artifact_path(
            report_job['job_id'],
            report_artifact['filename'],
        ).read_bytes()

        bundle = delegated.get(report_job['bundle_url'])
        assert bundle.status_code == 200
        assert bundle.content.startswith(b'PK')
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)



@pytest.mark.parametrize('endpoint', _POST_ENDPOINTS)
def test_office_post_endpoints_require_matching_csrf_for_admin(
    app,
    csrf_client: TestClient,
    endpoint: str,
    tmp_path,
) -> None:
    store = OfficeJobStore(tmp_path / 'office_jobs', min_free_bytes=0)
    app.dependency_overrides[get_office_job_store] = lambda: store
    csrf_token = csrf_client.headers.pop('x-csrf-token')
    try:
        assert _office_post(csrf_client, endpoint, csrf_token=None).status_code == 403
        assert _office_post(csrf_client, endpoint, csrf_token='mismatched-csrf-token').status_code == 403

        accepted = _office_post(csrf_client, endpoint, csrf_token)
        assert accepted.status_code == 200
        if endpoint == 'jobs/admin/purge':
            body = accepted.json()
            assert body['deleted_jobs'] == 0
            assert body['freed_bytes'] == 0
            assert body.get('quarantined_job_ids', []) == []
            assert body.get('quarantined_bytes', 0) == 0
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)

@pytest.mark.parametrize(
    ('method', 'path_template', 'resource', 'audit_action'),
    _ADMIN_OFFICE_MANAGEMENT_ROUTES,
)
def test_admin_office_management_routes_require_exact_permission_csrf_and_audit(
    app,
    tmp_path,
    method: str,
    path_template: str,
    resource: str,
    audit_action: str | None,
) -> None:
    store = OfficeJobStore(tmp_path / 'office_jobs', min_free_bytes=0)
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        evidence = _seed_admin_office_management_evidence(store)
        corrupt_evidence_path: Path | None = None
        if resource == 'evidence':
            corrupt_item, corrupt_evidence_path = _seed_corrupt_evidence(store, 'target')
            evidence['evidence'] = corrupt_item
        target_item = evidence.get(resource)
        target_id = None
        if target_item is not None:
            target_id_key = 'management_token' if resource == 'evidence' else f'{resource}_id'
            target_id = str(target_item[target_id_key])
        endpoint = path_template.format(
            quarantine_id=evidence['quarantine']['quarantine_id'],
            recovery_id=evidence['recovery']['recovery_id'],
            management_token=target_id,
        )
        baseline = _office_store_snapshot(store)
        baseline_management_audits = _office_management_audit_events(app)

        anonymous = TestClient(app)
        _assert_denied_management_request(
            app,
            store,
            _management_request(anonymous, method, endpoint),
            expected_status=401,
            baseline=baseline,
            target_id=target_id,
            audit_action=audit_action,
        )

        office_user, office_user_csrf_token, _ = _user_client(
            app,
            f'{resource}-{method.lower()}-office-only',
            permission_keys=('office.use',),
        )
        _assert_denied_management_request(
            app,
            store,
            _management_request(office_user, method, endpoint, office_user_csrf_token),
            expected_status=403,
            baseline=baseline,
            target_id=target_id,
            audit_action=audit_action,
        )
        # admin.office.manage 단독으로는 부족하다(office.use 병행 요구). user 역할은
        # 1.16.3 부터 office.use 를 기본 보유하므로 pending 역할로 단독 보유를 재현한다.
        management_only, management_only_csrf_token, _ = _user_client(
            app,
            f'{resource}-{method.lower()}-manage-only',
            permission_keys=('admin.office.manage',),
            role='pending',
        )
        _assert_denied_management_request(
            app,
            store,
            _management_request(
                management_only,
                method,
                endpoint,
                management_only_csrf_token if audit_action is not None else None,
            ),
            expected_status=403,
            baseline=baseline,
            target_id=target_id,
            audit_action=audit_action,
        )
        assert _office_management_audit_events(app) == baseline_management_audits

        manager, manager_csrf_token, manager_id = _user_client(
            app,
            f'{resource}-{method.lower()}-manager',
            permission_keys=('office.use', 'admin.office.manage'),
        )
        if audit_action is not None:
            _assert_denied_management_request(
                app,
                store,
                _management_request(manager, method, endpoint),
                expected_status=403,
                baseline=baseline,
                target_id=target_id,
                audit_action=audit_action,
            )
            _assert_denied_management_request(
                app,
                store,
                _management_request(manager, method, endpoint, 'mismatched-csrf-token'),
                expected_status=403,
                baseline=baseline,
                target_id=target_id,
                audit_action=audit_action,
            )
        if resource == 'quarantine' and audit_action is not None:
            assert target_item is not None
            assert target_id is not None
            target_quarantine_dir = store.root / '.quarantine' / target_id
            other_quarantine_dir = (
                store.root / '.quarantine' / evidence['other_quarantine']['quarantine_id']
            )
            target_payload_dir = target_quarantine_dir / 'payload'
            target_quarantine_physical_bytes = store._directory_size(target_quarantine_dir)
            baseline_quarantine_physical_bytes = store.storage_accounting()[
                'quarantine_physical_bytes'
            ]
            target_payload_snapshot = _directory_snapshot(target_payload_dir)
            target_artifact_bytes = {
                path.name: path.read_bytes()
                for path in target_payload_dir.iterdir()
                if path.is_file() and path.name != 'job.json'
            }
            other_quarantine_snapshot = _directory_snapshot(other_quarantine_dir)

        successful = _management_request(
            manager,
            method,
            endpoint,
            manager_csrf_token if audit_action is not None else None,
        )
        assert successful.status_code == 200
        if audit_action is None:
            assert successful.json() == baseline[resource]
        else:
            assert target_item is not None
            assert target_id is not None
            successful_body = successful.json()
            assert successful_body['outcome']['target_id'] == target_id
            assert successful_body['outcome']['removed'] is True
            _assert_completed_durability(successful_body['outcome'])
            if resource == 'evidence':
                assert successful_body['outcome']['management_token'] == target_id
            else:
                assert successful_body['item'][f'{resource}_id'] == target_id
            _assert_successful_management_audit(
                app,
                target_id=target_id,
                audit_action=audit_action,
                manager_id=manager_id,
            )
            if resource == 'quarantine':
                assert not target_quarantine_dir.exists()
                assert not target_quarantine_dir.is_symlink()
                assert _directory_snapshot(other_quarantine_dir) == other_quarantine_snapshot
                assert {
                    item['quarantine_id'] for item in store.list_quarantine()['items']
                } == {evidence['other_quarantine']['quarantine_id']}
                assert store.list_recovery() == baseline['recovery']
                if audit_action == 'office_jobs.quarantine.delete':
                    assert store.storage_accounting()['quarantine_physical_bytes'] == (
                        baseline_quarantine_physical_bytes - target_quarantine_physical_bytes
                    )
                else:
                    target_job_id = str(target_item['job_id'])
                    restored_job = store.get(target_job_id)
                    restored_job_dir = store.job_dir(target_job_id)
                    assert restored_job['job_id'] == target_job_id
                    assert _directory_snapshot(restored_job_dir) == target_payload_snapshot
                    assert target_artifact_bytes
                    assert {
                        artifact['filename'] for artifact in restored_job['artifacts']
                    } == set(target_artifact_bytes)
                    assert {
                        filename: (restored_job_dir / filename).read_bytes()
                        for filename in target_artifact_bytes
                    } == target_artifact_bytes
            elif resource == 'recovery':
                remaining_recovery_ids = {
                    item['recovery_id'] for item in store.list_recovery()['items']
                }
                assert remaining_recovery_ids == {evidence['other_recovery']['recovery_id']}
                assert store.list_quarantine() == baseline['quarantine']
            else:
                assert resource == 'evidence'
                assert corrupt_evidence_path is not None
                assert not corrupt_evidence_path.exists()
                assert not corrupt_evidence_path.is_symlink()
                assert corrupt_evidence_path.name not in successful.text
                assert {
                    item['quarantine_id'] for item in store.list_quarantine()['items']
                } == {
                    evidence['quarantine']['quarantine_id'],
                    evidence['other_quarantine']['quarantine_id'],
                }
                assert store.list_recovery() == baseline['recovery']
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)


def test_delegated_office_user_owns_generated_job_and_blocks_other_actors(app, tmp_path) -> None:
    owner_byte_quota = 1_024
    store = OfficeJobStore(
        tmp_path / 'office_jobs',
        max_jobs_per_owner=1,
        max_bytes_per_owner=owner_byte_quota,
        min_free_bytes=0,
    )
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        owner, owner_csrf_token, owner_id = _user_client(
            app,
            'office-owner',
            permission_keys=('office.use',),
        )
        foreign_owner, foreign_csrf_token, _ = _user_client(
            app,
            'office-foreign-owner',
            permission_keys=('office.use',),
        )
        missing_permission, missing_permission_csrf_token, _ = _user_client(
            app,
            'office-without-permission',
        )

        generated = owner.post(
            '/api/v1/office-tools/diagrams/generate',
            headers={'x-csrf-token': owner_csrf_token},
            json={'description': '수집 -> 검토 -> 발행', 'ai_assist': False},
        )
        assert generated.status_code == 200
        generated_job = generated.json()
        job_id = generated_job['job_id']
        job_url = f'/api/v1/office-tools/jobs/{job_id}'
        artifact_url = next(
            artifact['download_url']
            for artifact in generated_job['artifacts']
            if artifact['filename'] == 'diagram.mmd'
        )
        bundle_url = generated_job['bundle_url']
        artifact_bytes = sum(artifact['size_bytes'] for artifact in generated_job['artifacts'])
        assert artifact_bytes > owner_byte_quota // 2
        assert artifact_bytes <= owner_byte_quota

        job = owner.get(job_url)
        assert job.status_code == 200
        assert job.json()['owner_id'] == owner_id
        listed_jobs = owner.get('/api/v1/office-tools/jobs')
        assert listed_jobs.status_code == 200
        listed_body = listed_jobs.json()
        assert job_id in {item['job_id'] for item in listed_body['jobs']}
        owner_capacity = {
            'max_jobs_per_owner': 1,
            'max_bytes_per_owner': owner_byte_quota,
        }
        assert listed_body['usage'] == {
            'job_count': 1,
            'total_bytes': artifact_bytes,
            **owner_capacity,
        }
        assert owner.get(artifact_url).status_code == 200
        assert owner.get(bundle_url).status_code == 200

        anonymous = TestClient(app)
        assert anonymous.get(artifact_url).status_code == 401
        assert anonymous.get(bundle_url).status_code == 401
        assert anonymous.delete(job_url).status_code == 401

        assert missing_permission.get(artifact_url).status_code == 403
        assert missing_permission.get(bundle_url).status_code == 403
        assert missing_permission.delete(
            job_url,
            headers={'x-csrf-token': missing_permission_csrf_token},
        ).status_code == 403

        assert foreign_owner.get(job_url).status_code == 403
        foreign_jobs = foreign_owner.get('/api/v1/office-tools/jobs')
        assert foreign_jobs.status_code == 200
        assert job_id not in {item['job_id'] for item in foreign_jobs.json()['jobs']}
        assert foreign_owner.get(artifact_url).status_code == 403
        assert foreign_owner.get(bundle_url).status_code == 403
        assert foreign_owner.delete(
            job_url,
            headers={'x-csrf-token': foreign_csrf_token},
        ).status_code == 403
        before_owner_delete = _owned_job_snapshot(store, job_id, owner_id)
        assert owner.delete(job_url).status_code == 403
        assert _owned_job_snapshot(store, job_id, owner_id) == before_owner_delete
        assert owner.delete(
            job_url,
            headers={'x-csrf-token': 'mismatched-csrf-token'},
        ).status_code == 403
        assert _owned_job_snapshot(store, job_id, owner_id) == before_owner_delete
        deleted = owner.delete(job_url, headers={'x-csrf-token': owner_csrf_token})
        assert deleted.status_code == 200
        deleted_outcome = deleted.json()['outcome']
        assert deleted_outcome['operation'] == 'owner_delete'
        assert deleted_outcome['job_id'] == job_id
        assert deleted_outcome['owner_id'] == owner_id
        assert deleted_outcome['removed'] is True
        _assert_completed_durability(deleted_outcome, owner=True)
        assert owner.get(job_url).status_code == 404
        assert owner.get(artifact_url).status_code == 404
        assert owner.get(bundle_url).status_code == 404

        post_delete_list = owner.get('/api/v1/office-tools/jobs')
        assert post_delete_list.status_code == 200
        assert post_delete_list.json() == {
            'jobs': [],
            'usage': {
                'job_count': 0,
                'total_bytes': 0,
                **owner_capacity,
            },
        }

        regenerated = owner.post(
            '/api/v1/office-tools/diagrams/generate',
            headers={'x-csrf-token': owner_csrf_token},
            json={'description': '수집 -> 검토 -> 발행', 'ai_assist': False},
        )
        assert regenerated.status_code == 200
        regenerated_job = regenerated.json()
        regenerated_job_id = regenerated_job['job_id']
        regenerated_artifact_bytes = sum(
            artifact['size_bytes'] for artifact in regenerated_job['artifacts']
        )
        assert regenerated_job['mermaid'] == generated_job['mermaid']
        assert {
            (artifact['filename'], artifact['media_type'], artifact['size_bytes'])
            for artifact in regenerated_job['artifacts']
        } == {
            (artifact['filename'], artifact['media_type'], artifact['size_bytes'])
            for artifact in generated_job['artifacts']
        }
        assert regenerated_artifact_bytes == artifact_bytes
        regenerated_artifact_url = next(
            artifact['download_url']
            for artifact in regenerated_job['artifacts']
            if artifact['filename'] == 'diagram.mmd'
        )
        assert owner.get(regenerated_artifact_url).status_code == 200
        assert owner.get(regenerated_job['bundle_url']).status_code == 200
        regenerated_list = owner.get('/api/v1/office-tools/jobs')
        assert regenerated_list.status_code == 200
        regenerated_list_body = regenerated_list.json()
        assert {item['job_id'] for item in regenerated_list_body['jobs']} == {regenerated_job_id}
        assert regenerated_list_body['usage'] == {
            'job_count': 1,
            'total_bytes': regenerated_artifact_bytes,
            **owner_capacity,
        }
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)
