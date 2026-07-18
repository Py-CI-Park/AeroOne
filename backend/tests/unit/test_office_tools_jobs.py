"""jobs 라우터의 소유권·수명주기·경로 방어 검증.

JobStore 를 제한값이 명시된 tmp 루트로 주입해 실제 저장소와 머신 디스크 여유 공간에
의존하지 않는다. 소유자는 job/artifact/bundle 을 받고, 타인은 403, 잘못된 id/경로
탈출은 404 이며, 목록·삭제·관리자 purge 는 소유권과 권한 경계를 지킨다.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import json
import multiprocessing
import os
import threading
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

import app.modules.office_tools.core.job_store as job_store_module
import app.modules.office_tools.api.jobs as jobs_api
import app.main as main_module
from app.core.config import Settings
from app.main import create_app
from app.core.security import hash_password
from app.modules.admin.models import AdminAuditEvent, UserPermission
from app.modules.auth.models import User
from app.modules.auth.repositories import UserRepository
from app.modules.office_tools.api.jobs import _stream_artifact, get_office_job_store
from app.modules.office_tools.core.job_store import (
    OfficeJobCapacityError,
    OfficeJobCorruptionError,
    OfficeJobDeletionError,
    OfficeJobDeletionOutcome,
    OfficeJobDirectMutationError,
    OfficeJobPendingResultError,
    OfficeJobStore,
    OfficeJobOwnerDeletionError,
    OfficeJobPurgeError,
)
from pydantic import ValidationError


def _admin_id(app) -> int:
    with app.state.db.session() as session:
        return session.execute(select(User).where(User.username == 'admin')).scalar_one().id


def _store(root: Path, **overrides: int) -> OfficeJobStore:
    limits = {
        'retention_days': 365,
        'max_jobs_per_owner': 100,
        'max_bytes_per_owner': 1024 * 1024,
        'min_free_bytes': 0,
    }
    limits.update(overrides)
    return OfficeJobStore(root, **limits)

def _completed_durability_fields() -> dict[str, object]:
    if os.name == 'nt':
        return {
            'durably_synced': False,
            'durability': 'platform_best_effort',
            'retry_required': False,
        }
    return {
        'durably_synced': True,
        'durability': 'synced',
        'retry_required': False,
    }


def _completed_owner_durability_fields() -> dict[str, object]:
    completed = _completed_durability_fields()
    return {
        **completed,
        'owner_identity_durably_synced': completed['durably_synced'],
        'owner_identity_durability': completed['durability'],
    }


def _set_job_timestamp(store: OfficeJobStore, job_id: str, timestamp: datetime) -> None:
    """보존 기간 경계 검사용으로 공개 job 메타데이터의 수정 시각을 준비한다."""

    job_dir = store.job_dir(job_id)
    record_path = job_dir / 'job.json'
    record = json.loads(record_path.read_text(encoding='utf-8'))
    record['updated_at'] = timestamp.isoformat()
    record_path.write_text(json.dumps(record), encoding='utf-8')
    os.utime(job_dir, (timestamp.timestamp(), timestamp.timestamp()))
def _preserve_recovery_entry(store: OfficeJobStore, marker: str) -> dict[str, object]:
    """실제 recovery quarantine entry를 만들어 API inventory와 discard를 검증한다."""
    transaction_id = f'create-{marker * 32}'
    store._preserve_unresolved_recovery(None, transaction_id, 'injected recovery failure')
    return next(
        item
        for item in store.list_recovery()['items']
        if item['transaction_id'] == transaction_id
    )


def _filesystem_snapshot(root: Path) -> dict[str, bytes | None]:
    """파일 바이트와 빈 디렉터리를 함께 보존 검증용으로 기록한다."""

    if root.is_file():
        return {root.name: root.read_bytes()}
    return {
        path.relative_to(root).as_posix(): path.read_bytes() if path.is_file() else None
        for path in sorted(root.rglob('*'))
    }


def _office_user_client(
    app,
    username: str,
    permissions: tuple[str, ...] = ('office.use',),
    *,
    role: str = 'pending',
) -> TestClient:
    """명시된 Office 권한'만' 가진 세션을 만든다.

    1.16.3 부터 user 역할 기본값에 office.use 가 포함되므로, 명시 권한 외에는
    아무것도 없는 주체를 만들기 위해 기본은 역할 기본 권한이 빈 pending 계정을 쓴다
    (pending 도 로그인은 가능하다 — is_active 만 로그인 조건). 감사 로그의 actor
    role 까지 검증하는 테스트는 role='user' 로 발급 계정을 명시한다.
    """
    with app.state.db.session() as session:
        user = UserRepository(session).create(
            username=username,
            password_hash=hash_password('password123'),
            role=role,
        )
        session.add_all(UserPermission(user_id=user.id, permission_key=permission) for permission in permissions)

    client = TestClient(app)
    login = client.post('/api/v1/auth/login', json={'username': username, 'password': 'password123'})
    assert login.status_code == 200
    client.headers.update({'x-csrf-token': login.json()['csrf_token']})
    return client


def _user_id(app, username: str) -> int:
    with app.state.db.session() as session:
        return session.execute(select(User).where(User.username == username)).scalar_one().id


def _create_job_in_process(
    root: str,
    ready: multiprocessing.synchronize.Event,
    finished: multiprocessing.synchronize.Event,
    result: multiprocessing.queues.Queue,
) -> None:
    store = _store(Path(root), max_jobs_per_owner=1)
    ready.set()
    try:
        result.put(('created', store.create('report', owner_id=1)['job_id']))
    except OfficeJobCapacityError:
        result.put(('capacity', None))
    finally:
        finished.set()

def test_app_initialization_recovers_office_job_store_once_without_retention_cleanup(
    settings: Settings,
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = _store(tmp_path / 'office_jobs', retention_days=1)
    construction_settings: list[Settings] = []
    purge_calls = 0
    past = datetime.now(UTC) - timedelta(days=31)

    expired = store.create('report', owner_id=704)
    _set_job_timestamp(store, expired['job_id'], datetime.now(UTC) - timedelta(days=2))
    retained = store.create('diagram', owner_id=705)
    store.write_bytes(retained['job_id'], 'retained.txt', b'retained', 'text/plain')

    expired_quarantine_job = store.create('chart', owner_id=706)
    store.write_bytes(
        expired_quarantine_job['job_id'],
        'expired-quarantine.txt',
        b'expired quarantine evidence',
        'text/plain',
    )
    expired_quarantine_item = store._quarantine_corrupt_job(
        store.job_dir(expired_quarantine_job['job_id']),
        'startup retention control',
    )
    assert expired_quarantine_item is not None
    expired_quarantine_entry = store._quarantine_root / expired_quarantine_item['quarantine_id']
    expired_quarantine_metadata_path = expired_quarantine_entry / 'metadata.json'
    expired_quarantine_metadata = json.loads(expired_quarantine_metadata_path.read_text(encoding='utf-8'))
    expired_quarantine_metadata['quarantined_at'] = past.isoformat()
    expired_quarantine_metadata_path.write_text(
        json.dumps(expired_quarantine_metadata),
        encoding='utf-8',
    )

    stale_bundle = store._bundles_root / f'bundle-{"e" * 32}.zip'
    stale_bundle.write_bytes(b'stale bundle evidence')
    os.utime(stale_bundle, (past.timestamp(), past.timestamp()))

    recovered = store.create('report', owner_id=701)
    recovered_stage_id = f'create-{"a" * 32}'
    recovered_stage = store._staging_root / recovered_stage_id
    recovered_stage.mkdir()
    store.job_dir(recovered['job_id']).replace(recovered_stage / recovered['job_id'])
    store._write_journal(
        recovered_stage_id,
        {
            'version': 1,
            'operation': 'create',
            'phase': 'prepared',
            'job_id': recovered['job_id'],
            'stage_id': recovered_stage_id,
            'owner_id': 701,
        },
    )

    rolled_back = store.create('chart', owner_id=702)
    store.write_bytes(rolled_back['job_id'], 'result.txt', b'original', 'text/plain')
    old_record = store.get(rolled_back['job_id'])
    rollback_stage_id = f'artifact-{"b" * 32}'
    rollback_stage = store._staging_root / rollback_stage_id
    rollback_stage.mkdir()
    staged_artifact = rollback_stage / 'new'
    staged_artifact.write_bytes(b'replacement')
    replacement = store._artifact_metadata(
        rolled_back['job_id'],
        'result.txt',
        'text/plain',
        staged_artifact,
    )
    new_record = store._record_with_artifact(old_record, replacement)
    store._write_journal(
        rollback_stage_id,
        {
            'version': 1,
            'operation': 'artifact_replace',
            'phase': 'prepared',
            'job_id': rolled_back['job_id'],
            'stage_id': rollback_stage_id,
            'artifact_name': 'result.txt',
            'old_record': old_record,
            'new_record': new_record,
        },
    )

    unresolved_stage_id = f'create-{"c" * 32}'
    store._write_journal(
        unresolved_stage_id,
        {
            'version': 1,
            'operation': 'create',
            'phase': 'prepared',
            'job_id': 'd' * 32,
            'stage_id': unresolved_stage_id,
        },
    )

    orphan_stage_id = f'create-{"d" * 32}'
    orphan_stage = store._staging_root / orphan_stage_id
    orphan_stage_evidence = orphan_stage / 'nested' / 'orphan-stage.bin'
    orphan_stage_evidence.parent.mkdir(parents=True)
    orphan_stage_payload = b'orphan stage evidence'
    orphan_stage_evidence.write_bytes(orphan_stage_payload)

    retained_stage = store._staging_root / 'retained-stage-control'
    retained_stage_payload = b'retained stage control'
    retained_stage.mkdir()
    (retained_stage / 'control.bin').write_bytes(retained_stage_payload)

    def from_settings(_cls, configured_settings: Settings) -> OfficeJobStore:
        construction_settings.append(configured_settings)
        return store

    def purge_expired() -> dict[str, int | list[str]]:
        nonlocal purge_calls
        purge_calls += 1
        raise AssertionError('application initialization must not purge retained jobs')

    monkeypatch.setattr(OfficeJobStore, 'from_settings', classmethod(from_settings))
    monkeypatch.setattr(store, 'purge_expired', purge_expired)

    initialized_app = create_app(settings)

    expected_report = {
        'recovered_transactions': 1,
        'rolled_back_transactions': 1,
        'unresolved_recovery_transactions': 2,
        'unresolved_recovery_ids': [unresolved_stage_id, orphan_stage_id],
        'malformed_recovery_evidence': 0,
        'owner_deletion_tombstone_failures': [],
        'orphan_stage_dirs': 1,
        'orphan_stage_bytes': len(orphan_stage_payload),
        'stale_bundles': 0,
        'stale_bundle_bytes': 0,
        'expired_quarantine_entries': 0,
        'expired_quarantine_bytes': 0,
    }
    assert construction_settings == [settings]
    assert purge_calls == 0
    assert initialized_app.state.office_job_store is store
    assert initialized_app.state.office_job_recovery_report == expected_report
    monkeypatch.setattr(main_module, 'get_engine', lambda: initialized_app.state.db.engine)
    health = TestClient(initialized_app).get('/api/v1/health')
    assert health.status_code == 200
    assert health.json()['db_ok'] is True
    assert health.json()['status'] == 'degraded'
    assert health.json()['office_job_recovery_ok'] is False
    assert (
        health.json()['office_job_unresolved_recovery_transactions'] == 2
    )
    assert 'office_recovery_ok' not in health.json()
    assert 'office_recovery_unresolved_count' not in health.json()
    assert store.last_maintenance == expected_report

    assert store.get(recovered['job_id'])['owner_id'] == 701
    assert not recovered_stage.exists()
    assert not store._journal_path(recovered_stage_id).exists()
    assert store.artifact_path(rolled_back['job_id'], 'result.txt').read_bytes() == b'original'
    assert store.get(rolled_back['job_id']) == old_record
    assert not rollback_stage.exists()
    assert not store._journal_path(rollback_stage_id).exists()

    recovery_items = {
        item['transaction_id']: item
        for item in store.list_recovery()['items']
    }
    assert set(recovery_items) == {unresolved_stage_id, orphan_stage_id}

    unresolved_item = recovery_items[unresolved_stage_id]
    unresolved_entry = store._recovery_quarantine_root / unresolved_item['recovery_id']
    unresolved_metadata = json.loads((unresolved_entry / 'metadata.json').read_text(encoding='utf-8'))
    assert unresolved_metadata['transaction_id'] == unresolved_stage_id
    assert unresolved_metadata['journal_preserved'] is True
    assert unresolved_metadata['stage_preserved'] is False
    assert (unresolved_entry / 'journal').is_file()
    assert not store._journal_path(unresolved_stage_id).exists()

    orphan_item = recovery_items[orphan_stage_id]
    orphan_entry = store._recovery_quarantine_root / orphan_item['recovery_id']
    orphan_metadata = json.loads((orphan_entry / 'metadata.json').read_text(encoding='utf-8'))
    assert orphan_item['stage_preserved'] is True
    assert orphan_metadata['transaction_id'] == orphan_stage_id
    assert orphan_metadata['journal_preserved'] is False
    assert orphan_metadata['stage_preserved'] is True
    assert orphan_item['size_bytes'] == (
        (orphan_entry / 'metadata.json').stat().st_size + len(orphan_stage_payload)
    )
    assert not orphan_stage.exists()
    assert (orphan_entry / 'stage' / 'nested' / 'orphan-stage.bin').read_bytes() == orphan_stage_payload

    assert store.get(expired['job_id'])['job_id'] == expired['job_id']
    assert store.get(retained['job_id'])['job_id'] == retained['job_id']
    assert (retained_stage / 'control.bin').read_bytes() == retained_stage_payload
    assert stale_bundle.read_bytes() == b'stale bundle evidence'
    quarantine_items = store.list_quarantine()['items']
    assert len(quarantine_items) == 1
    assert quarantine_items[0]['quarantine_id'] == expired_quarantine_item['quarantine_id']
    assert quarantine_items[0]['quarantined_at'] == past.isoformat()
    assert quarantine_items[0]['kind'] == 'quarantine'
    assert quarantine_items[0]['physical_bytes'] >= expired_quarantine_item['size_bytes']
def test_recovery_inventory_requires_manage_permission(app, tmp_path: Path) -> None:
    store = _store(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        recovery_item = _preserve_recovery_entry(store, 'd')
        office_only_client = _office_user_client(app, 'recovery-office-only')
        manager_client = _office_user_client(
            app,
            'recovery-manager',
            permissions=('office.use', 'admin.office.manage'),
        )

        assert office_only_client.get('/api/v1/office-tools/jobs/recovery').status_code == 403
        response = manager_client.get('/api/v1/office-tools/jobs/recovery')

        assert response.status_code == 200
        assert response.json() == {
            'items': [{**recovery_item, 'management_token': None}],
            'recovery_ids': [recovery_item['recovery_id']],
            'management_tokens': [],
            'total_bytes': recovery_item['size_bytes'],
            'corrupt_entries': 0,
        }
        assert 'journal' not in response.json()['items'][0]
        assert 'stage' not in response.json()['items'][0]
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)

def test_owner_identity_inventory_requires_both_permissions_and_uses_sanitized_evidence_token(
    app,
    tmp_path: Path,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    normal_owner_id = 17
    normal_job = store.create('report', owner_id=normal_owner_id)
    raw_filename = 'owner-identity-private-evidence.json'
    corrupt_evidence = store._owner_identities_root / raw_filename
    corrupt_evidence.write_bytes(b'{invalid owner identity')
    try:
        anonymous_client = TestClient(app)
        office_only_client = _office_user_client(app, 'owner-identity-office-only')
        manage_only_client = _office_user_client(
            app,
            'owner-identity-manage-only',
            permissions=('admin.office.manage',),
        )
        manager_client = _office_user_client(
            app,
            'owner-identity-manager',
            permissions=('office.use', 'admin.office.manage'),
        )
        with app.state.db.session() as session:
            audit_ids_before_reads = list(
                session.scalars(select(AdminAuditEvent.id).order_by(AdminAuditEvent.id))
            )
        filesystem_before_reads = _filesystem_snapshot(store.root)

        assert anonymous_client.get('/api/v1/office-tools/jobs/owner-identities').status_code == 401
        assert office_only_client.get('/api/v1/office-tools/jobs/owner-identities').status_code == 403
        assert manage_only_client.get('/api/v1/office-tools/jobs/owner-identities').status_code == 403
        response = manager_client.get('/api/v1/office-tools/jobs/owner-identities')

        assert response.status_code == 200
        assert _filesystem_snapshot(store.root) == filesystem_before_reads
        with app.state.db.session() as session:
            assert list(session.scalars(select(AdminAuditEvent.id).order_by(AdminAuditEvent.id))) == (
                audit_ids_before_reads
            )

        payload = response.json()
        normal_item = next(item for item in payload['items'] if item['kind'] == 'owner_identity')
        corrupt_item = next(item for item in payload['items'] if item['kind'] == 'corrupt')
        assert normal_item == {
            'kind': 'owner_identity',
            'management_token': None,
            'job_id': normal_job['job_id'],
            'owner_id': normal_owner_id,
            'physical_bytes': store._physical_size_no_follow(
                store._owner_identity_path(normal_job['job_id'])
            ),
            'reason': None,
        }
        assert corrupt_item['job_id'] is None
        assert corrupt_item['owner_id'] is None
        assert corrupt_item['physical_bytes'] == corrupt_evidence.stat().st_size
        assert corrupt_item['reason'] == 'evidence name is invalid'
        token = corrupt_item['management_token']
        assert isinstance(token, str)
        assert token
        assert token != raw_filename
        assert raw_filename not in response.text
        assert store._owner_identities_root.name not in response.text
        assert set(corrupt_item) == {
            'kind',
            'management_token',
            'job_id',
            'owner_id',
            'physical_bytes',
            'reason',
        }
        assert payload['total_bytes'] == sum(item['physical_bytes'] for item in payload['items'])
        assert payload['corrupt_entries'] == 1
        assert payload['corrupt_physical_bytes'] == corrupt_item['physical_bytes']

        disposition = manager_client.delete(f'/api/v1/office-tools/jobs/evidence/{token}')

        assert disposition.status_code == 200
        assert disposition.json()['outcome']['management_token'] == token
        assert disposition.json()['outcome']['operation'] == 'owner_identity_corrupt_disposition'
        assert not corrupt_evidence.exists()
        with app.state.db.session() as session:
            events = session.scalars(
                select(AdminAuditEvent)
                .where(
                    AdminAuditEvent.target_id == token,
                    AdminAuditEvent.action.in_(
                        ['office_jobs.evidence.dispose.intent', 'office_jobs.evidence.dispose']
                    ),
                )
                .order_by(AdminAuditEvent.id)
            ).all()
        assert [(event.action, event.status) for event in events] == [
            ('office_jobs.evidence.dispose.intent', 'intent'),
            ('office_jobs.evidence.dispose', 'success'),
        ]
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)


def test_recovery_discard_requires_csrf_audits_and_reflects_live_health(
    app,
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    original_app_store = app.state.office_job_store
    app.state.office_job_store = store
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        stage_id = f'create-{"e" * 32}'
        stage_evidence = store._staging_root / stage_id / 'nested' / 'stage-evidence.bin'
        stage_evidence.parent.mkdir(parents=True)
        stage_evidence_payload = b'nested recovery stage evidence'
        stage_evidence.write_bytes(stage_evidence_payload)
        journal = {
            'version': 1,
            'operation': 'create',
            'phase': 'prepared',
            'job_id': 'a' * 32,
            'stage_id': stage_id,
            'owner_id': 1,
        }
        store._write_journal(stage_id, journal)
        journal_path = store._journal_path(stage_id)
        store._preserve_unresolved_recovery(journal_path, stage_id, 'discard evidence fixture')

        recovery_item = next(
            item
            for item in store.list_recovery()['items']
            if item['transaction_id'] == stage_id
        )
        recovery_id = str(recovery_item['recovery_id'])
        recovery_entry = store._recovery_quarantine_root / recovery_id
        recovery_entry_bytes = sum(
            path.stat().st_size
            for path in [
                recovery_entry / 'metadata.json',
                recovery_entry / 'journal',
                recovery_entry / 'stage' / 'nested' / 'stage-evidence.bin',
            ]
        )
        assert recovery_item['journal_preserved'] is True
        assert recovery_item['stage_preserved'] is True
        assert recovery_item['size_bytes'] == recovery_entry_bytes
        assert not journal_path.exists()
        assert not (store._staging_root / stage_id).exists()


        manager_client = _office_user_client(
            app,
            'recovery-discard-manager',
            permissions=('office.use', 'admin.office.manage'),
            role='user',
        )
        manager_id = _user_id(app, 'recovery-discard-manager')
        pre_discard_inventory = manager_client.get('/api/v1/office-tools/jobs/recovery').json()
        pre_discard_physical_bytes = store._directory_size(store._recovery_quarantine_root)
        assert pre_discard_inventory == {
            'items': [{**recovery_item, 'management_token': None}],
            'recovery_ids': [recovery_id],
            'management_tokens': [],
            'total_bytes': recovery_entry_bytes,
            'corrupt_entries': 0,
        }
        assert pre_discard_physical_bytes == recovery_entry_bytes
        unresolved_health = manager_client.get('/api/v1/health')
        assert unresolved_health.status_code == 200
        assert unresolved_health.json()['status'] == 'degraded'
        assert unresolved_health.json()['office_job_recovery_ok'] is False
        assert (
            unresolved_health.json()['office_job_unresolved_recovery_transactions'] == 1
        )
        assert 'office_recovery_ok' not in unresolved_health.json()
        assert 'office_recovery_unresolved_count' not in unresolved_health.json()
        no_csrf_client = TestClient(app)
        login = no_csrf_client.post(
            '/api/v1/auth/login',
            json={'username': 'recovery-discard-manager', 'password': 'password123'},
        )
        assert login.status_code == 200
        assert no_csrf_client.delete(f'/api/v1/office-tools/jobs/recovery/{recovery_id}').status_code == 403

        original_delete_recovery_outcome = store.delete_recovery_outcome
        intent_was_committed = False

        def delete_after_committed_intent(discard_id: str) -> dict[str, object]:
            nonlocal intent_was_committed
            with app.state.db.session() as session:
                events = session.scalars(
                    select(AdminAuditEvent)
                    .where(
                        AdminAuditEvent.target_id == discard_id,
                        AdminAuditEvent.action == 'office_jobs.recovery.delete.intent',
                    )
                    .order_by(AdminAuditEvent.id)
                ).all()
            assert [(event.status, event.actor_user_id) for event in events] == [('intent', manager_id)]
            intent_was_committed = True
            return original_delete_recovery_outcome(discard_id)

        monkeypatch.setattr(store, 'delete_recovery_outcome', delete_after_committed_intent)
        discarded = manager_client.delete(f'/api/v1/office-tools/jobs/recovery/{recovery_id}')

        assert discarded.status_code == 200
        expected_recovery_outcome = {
            'operation': 'recovery_delete',
            'target_id': recovery_id,
            'management_token': None,
            'job_id': None,
            'owner_id': None,
            'logical_bytes': 0,
            'physical_bytes': recovery_entry_bytes,
            'partial_bytes_removed': recovery_entry_bytes,
            'published': False,
            'removed': True,
            'durably_synced': True,
            **_completed_durability_fields(),
        }
        assert discarded.json() == {
            'item': {**recovery_item, 'management_token': None},
            'outcome': expected_recovery_outcome,
        }
        assert intent_was_committed
        restored_health = manager_client.get('/api/v1/health')
        assert restored_health.status_code == 200
        assert restored_health.json()['status'] == 'ok'
        assert restored_health.json()['office_job_recovery_ok'] is True
        assert (
            restored_health.json()['office_job_unresolved_recovery_transactions'] == 0
        )
        assert 'office_recovery_ok' not in restored_health.json()
        assert 'office_recovery_unresolved_count' not in restored_health.json()
        post_discard_inventory = manager_client.get('/api/v1/office-tools/jobs/recovery').json()
        assert post_discard_inventory == {
            'items': [],
            'recovery_ids': [],
            'management_tokens': [],
            'total_bytes': 0,
            'corrupt_entries': 0,
        }
        assert not recovery_entry.exists()
        assert store._directory_size(store._recovery_quarantine_root) == 0
        assert pre_discard_physical_bytes - store._directory_size(
            store._recovery_quarantine_root
        ) == recovery_entry_bytes


        with app.state.db.session() as session:
            events = session.scalars(
                select(AdminAuditEvent)
                .where(
                    AdminAuditEvent.target_id == recovery_id,
                    AdminAuditEvent.action.in_(
                        ['office_jobs.recovery.delete.intent', 'office_jobs.recovery.delete']
                    ),
                )
                .order_by(AdminAuditEvent.id)
            ).all()
        assert [(event.action, event.status, event.actor_user_id) for event in events] == [
            ('office_jobs.recovery.delete.intent', 'intent', manager_id),
            ('office_jobs.recovery.delete', 'success', manager_id),
        ]
        assert [(event.actor_username, event.actor_role, event.method, event.path) for event in events] == [
            (
                'recovery-discard-manager',
                'user',
                'DELETE',
                f'/api/v1/office-tools/jobs/recovery/{recovery_id}',
            ),
            (
                'recovery-discard-manager',
                'user',
                'DELETE',
                f'/api/v1/office-tools/jobs/recovery/{recovery_id}',
            ),
        ]
        assert events[0].idempotency_key is not None
        assert events[1].idempotency_key is not None
        assert events[0].idempotency_key.endswith(':intent')
        assert events[1].idempotency_key.endswith(':result')
        assert events[0].idempotency_key != events[1].idempotency_key
        assert json.loads(events[0].metadata_json or '{}') == {
            **recovery_item,
            'management_token': '[REDACTED]',
        }
        success_metadata = json.loads(events[1].metadata_json or '{}')
        assert success_metadata == {
            'item': {
                **discarded.json()['item'],
                'management_token': '[REDACTED]',
            },
            'outcome': {
                **discarded.json()['outcome'],
                'management_token': '[REDACTED]',
            },
        }
    finally:
        app.state.office_job_store = original_app_store
        app.dependency_overrides.pop(get_office_job_store, None)


def test_recovery_discard_corruption_records_partial_failure_audit(
    app,
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        recovery_item = _preserve_recovery_entry(store, 'f')
        recovery_id = str(recovery_item['recovery_id'])
        manager_client = _office_user_client(
            app,
            'recovery-failure-manager',
            permissions=('office.use', 'admin.office.manage'),
        )
        manager_id = _user_id(app, 'recovery-failure-manager')
        intent_was_committed = False

        def fail_after_committed_intent(discard_id: str) -> dict[str, object]:
            nonlocal intent_was_committed
            with app.state.db.session() as session:
                intent = session.scalar(
                    select(AdminAuditEvent).where(
                        AdminAuditEvent.target_id == discard_id,
                        AdminAuditEvent.action == 'office_jobs.recovery.delete.intent',
                    )
                )
            assert intent is not None
            assert intent.status == 'intent'
            assert intent.actor_user_id == manager_id
            intent_was_committed = True
            raise OfficeJobCorruptionError([discard_id])

        monkeypatch.setattr(store, 'delete_recovery_outcome', fail_after_committed_intent)
        response = manager_client.delete(f'/api/v1/office-tools/jobs/recovery/{recovery_id}')

        assert response.status_code == 409
        assert response.json()['detail'] == 'recovery entry is corrupt'
        assert intent_was_committed
        assert store.list_recovery()['items'] == [recovery_item]
        with app.state.db.session() as session:
            events = session.scalars(
                select(AdminAuditEvent)
                .where(
                    AdminAuditEvent.target_id == recovery_id,
                    AdminAuditEvent.action.in_(
                        ['office_jobs.recovery.delete.intent', 'office_jobs.recovery.delete']
                    ),
                )
                .order_by(AdminAuditEvent.id)
            ).all()
        assert [(event.action, event.status, event.actor_user_id) for event in events] == [
            ('office_jobs.recovery.delete.intent', 'intent', manager_id),
            ('office_jobs.recovery.delete', 'partial_failure', manager_id),
        ]
        assert json.loads(events[1].metadata_json or '{}')['intent'] == {
            **recovery_item,
            'management_token': '[REDACTED]',
        }
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)
@pytest.mark.parametrize(
    ('route_id', 'store_id'),
    [
        ('00000000-0000-0000-0000-000000000000', '00000000-0000-0000-0000-000000000000'),
        ('%2Foutside', '/outside'),
        ('%5Coutside', r'\outside'),
        ('..%2F..%5Coutside', r'../..\outside'),
        ('C%3A%5Coutside', r'C:\outside'),
        ('%5C%5Cserver%5Cshare', r'\\server\share'),
    ],
    ids=[
        'malformed-uuid',
        'encoded-separator',
        'encoded-backslash',
        'mixed-separators',
        'drive-path',
        'unc-path',
    ],
)
def test_management_identifiers_reject_path_forms_without_audit_or_filesystem_mutation(
    app,
    tmp_path: Path,
    route_id: str,
    store_id: str,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        quarantined_job = store.create('report', owner_id=1)
        store.write_bytes(quarantined_job['job_id'], 'evidence.txt', b'quarantine evidence', 'text/plain')
        quarantine_item = store._quarantine_corrupt_job(
            store.job_dir(quarantined_job['job_id']),
            'identifier rejection fixture',
        )
        assert quarantine_item is not None
        recovery_item = _preserve_recovery_entry(store, 'a')
        quarantine_inventory_before = store.list_quarantine()
        recovery_inventory_before = store.list_recovery()
        quarantine_entry = store._quarantine_root / quarantine_item['quarantine_id']
        recovery_entry = store._recovery_quarantine_root / recovery_item['recovery_id']
        outside_root_sentinel = tmp_path / 'outside-root-sentinel.bin'
        outside_root_sentinel.write_bytes(b'outside root must remain unchanged')

        manager_client = _office_user_client(
            app,
            'management-id-manager',
            permissions=('office.use', 'admin.office.manage'),
        )
        responses = [
            manager_client.delete(f'/api/v1/office-tools/jobs/recovery/{route_id}'),
            manager_client.post(f'/api/v1/office-tools/jobs/quarantine/{route_id}/restore'),
            manager_client.delete(f'/api/v1/office-tools/jobs/quarantine/{route_id}'),
        ]
        assert [response.status_code for response in responses] == [404, 404, 404]

        for operation in [
            store.delete_recovery_outcome,
            store.restore_quarantine_outcome,
            store.delete_quarantine_outcome,
        ]:
            with pytest.raises(FileNotFoundError):
                operation(store_id)

        assert store.list_quarantine() == quarantine_inventory_before
        assert store.list_recovery() == recovery_inventory_before
        assert quarantine_entry.is_dir()
        assert recovery_entry.is_dir()
        assert outside_root_sentinel.read_bytes() == b'outside root must remain unchanged'

        with app.state.db.session() as session:
            intents = session.scalars(
                select(AdminAuditEvent).where(
                    AdminAuditEvent.action.in_(
                        [
                            'office_jobs.recovery.delete.intent',
                            'office_jobs.quarantine.restore.intent',
                            'office_jobs.quarantine.delete.intent',
                        ]
                    )
                )
            ).all()
        assert intents == []
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)


def test_storage_accounting_is_typed_exact_and_separate_from_owner_quota(app, tmp_path: Path) -> None:
    store = _store(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        owner_id = _admin_id(app)
        record = store.create('report', owner_id=owner_id)
        baseline = store.storage_accounting()
        job_metadata_path = store.job_dir(record['job_id']) / 'job.json'
        job_metadata_before = job_metadata_path.stat().st_size

        artifact_payload = b'owned artifact payload'
        store.write_bytes(record['job_id'], 'report.txt', artifact_payload, 'text/plain')
        job_metadata_delta = job_metadata_path.stat().st_size - job_metadata_before
        usage_after_artifact = store.usage_for_owner(owner_id)
        assert usage_after_artifact == {'job_count': 1, 'total_bytes': len(artifact_payload)}

        quarantine_payload = b'quarantine managed payload'
        quarantine_id = 'a' * 32
        quarantine_entry = store._quarantine_root / quarantine_id
        quarantine_entry.mkdir()
        quarantine_metadata = {
            'quarantine_id': quarantine_id,
            'job_id': 'b' * 32,
            'size_bytes': len(quarantine_payload),
            'quarantined_at': datetime.now(UTC).isoformat(),
            'reason': 'storage accounting evidence',
        }
        quarantine_metadata_bytes = json.dumps(quarantine_metadata).encode('utf-8')
        (quarantine_entry / 'metadata.json').write_bytes(quarantine_metadata_bytes)
        (quarantine_entry / 'payload').write_bytes(quarantine_payload)

        recovery_payload = b'recovery managed payload'
        staging_payload = b'staging managed payload'
        journal_payload = b'transaction journal payload'
        bundle_payload = b'temporary bundle payload'
        owner_lock_payload = b'owner identity lock payload'
        owner_identity_payload = b'owner identity physical payload'
        root_payload = b'root unclassified payload'
        (store._recovery_quarantine_root / 'recovery.bin').write_bytes(recovery_payload)
        (store._staging_root / 'stage.bin').write_bytes(staging_payload)
        (store._transactions_root / 'journal.bin').write_bytes(journal_payload)
        (store._bundles_root / f'bundle-{"c" * 32}.zip').write_bytes(bundle_payload)
        owner_identity_entry = store._owner_identities_root / f'{"d" * 32}.json'
        owner_identity_entry.write_bytes(owner_identity_payload)
        owner_identity_physical_delta = owner_identity_entry.stat().st_size
        (store._locks_root / 'owner-987654.lock').write_bytes(owner_lock_payload)
        (store.root / 'unclassified.bin').write_bytes(root_payload)

        manager_client = _office_user_client(
            app,
            'storage-manager',
            permissions=('office.use', 'admin.office.manage'),
        )
        response = manager_client.get('/api/v1/office-tools/jobs/storage')

        assert response.status_code == 200
        accounting = response.json()
        assert all(isinstance(value, int) for value in accounting.values())
        expected_deltas = {
            'job_bytes': len(artifact_payload),
            'artifact_logical_bytes': len(artifact_payload),
            'job_logical_bytes': len(artifact_payload),
            'job_physical_bytes': len(artifact_payload) + job_metadata_delta,
            'job_metadata_physical_bytes': job_metadata_delta,
            'job_temporary_physical_bytes': 0,
            'job_artifact_physical_bytes': len(artifact_payload),
            'job_unclassified_physical_bytes': 0,
            'quarantine_bytes': len(quarantine_metadata_bytes) + len(quarantine_payload),
            'quarantine_physical_bytes': len(quarantine_metadata_bytes) + len(quarantine_payload),
            'recovery_quarantine_physical_bytes': len(recovery_payload),
            'owner_identity_physical_bytes': owner_identity_physical_delta,
            'owner_identity_entries': 1,
            'owner_identity_corrupt_entries': 1,
            'owner_identity_corrupt_physical_bytes': owner_identity_physical_delta,
            'staging_physical_bytes': len(staging_payload),
            'transaction_journal_physical_bytes': len(journal_payload),
            'owner_deletion_tombstone_entries': 0,
            'owner_deletion_tombstone_physical_bytes': 0,
            'pending_result_entries': 0,
            'pending_result_physical_bytes': 0,
            'temporary_bundle_bytes': len(bundle_payload),
            'bundle_physical_bytes': len(bundle_payload),
            'lock_physical_bytes': len(owner_lock_payload),
            'root_unclassified_physical_bytes': len(root_payload),
        }
        for key, expected_delta in expected_deltas.items():
            assert accounting[key] - baseline[key] == expected_delta

        assert accounting['job_bytes'] == accounting['artifact_logical_bytes']
        assert accounting['job_logical_bytes'] == accounting['artifact_logical_bytes']
        assert accounting['temporary_bundle_bytes'] == accounting['bundle_physical_bytes']
        assert accounting['job_physical_bytes'] == sum(
            accounting[key]
            for key in [
                'job_metadata_physical_bytes',
                'job_temporary_physical_bytes',
                'job_artifact_physical_bytes',
                'job_unclassified_physical_bytes',
            ]
        )
        physical_category_keys = [
            'job_physical_bytes',
            'quarantine_physical_bytes',
            'recovery_quarantine_physical_bytes',
            'owner_identity_physical_bytes',
            'staging_physical_bytes',
            'transaction_journal_physical_bytes',
            'bundle_physical_bytes',
            'owner_deletion_tombstone_physical_bytes',
            'pending_result_physical_bytes',
            'lock_physical_bytes',
            'root_unclassified_physical_bytes',
        ]
        assert accounting['total_bytes'] == sum(accounting[key] for key in physical_category_keys)
        assert accounting['total_bytes'] - baseline['total_bytes'] == sum(
            expected_deltas[key] for key in physical_category_keys
        )
        assert store.usage_for_owner(owner_id) == usage_after_artifact
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)


def test_restore_of_another_owners_nonempty_quarantine_preserves_owner_manifest_and_audit(
    app,
    tmp_path: Path,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        _office_user_client(app, 'quarantined-owner')
        owner_id = _user_id(app, 'quarantined-owner')
        manager_client = _office_user_client(
            app,
            'quarantine-manager',
            permissions=('office.use', 'admin.office.manage'),
        )
        manager_id = _user_id(app, 'quarantine-manager')
        quarantined_job = store.create('report', owner_id=owner_id)
        store.write_bytes(quarantined_job['job_id'], 'report.txt', b'report bytes', 'text/plain')
        store.write_bytes(quarantined_job['job_id'], 'chart.csv', b'x,y\n1,2\n', 'text/csv')
        original_record = store.get(quarantined_job['job_id'])
        original_bytes = len(b'report bytes') + len(b'x,y\n1,2\n')
        quarantine_item = store._quarantine_corrupt_job(
            store.job_dir(quarantined_job['job_id']),
            'manual recovery verification',
        )
        assert quarantine_item is not None
        metadata_path = store._quarantine_root / str(quarantine_item['quarantine_id']) / 'metadata.json'
        metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
        assert metadata['owner_id'] == owner_id
        quarantine_inventory_item = store.list_quarantine()['items'][0]
        assert quarantine_inventory_item['owner_id'] == owner_id

        response = manager_client.post(
            f"/api/v1/office-tools/jobs/quarantine/{quarantine_item['quarantine_id']}/restore"
        )

        assert response.status_code == 200
        assert response.json() == {
            'item': {**quarantine_inventory_item, 'management_token': None},
            'outcome': {
                'operation': 'quarantine_restore',
                'target_id': quarantine_item['quarantine_id'],
                'management_token': None,
                'job_id': quarantined_job['job_id'],
                'owner_id': owner_id,
                'logical_bytes': original_bytes,
                'physical_bytes': quarantine_inventory_item['physical_bytes'],
                'partial_bytes_removed': (
                    quarantine_inventory_item['physical_bytes']
                    - quarantine_inventory_item['size_bytes']
                ),
                'published': True,
                'removed': True,
                'durably_synced': True,
                **_completed_durability_fields(),
            },
        }
        restored = store.get(quarantined_job['job_id'])
        assert restored['owner_id'] == owner_id
        assert restored['artifacts'] == original_record['artifacts']
        assert store.artifact_path(quarantined_job['job_id'], 'report.txt').read_bytes() == b'report bytes'
        assert store.artifact_path(quarantined_job['job_id'], 'chart.csv').read_bytes() == b'x,y\n1,2\n'
        assert store.usage_for_owner(owner_id) == {'job_count': 1, 'total_bytes': original_bytes}
        assert store.list_quarantine()['items'] == []
        assert not (store._quarantine_root / quarantine_item['quarantine_id']).exists()

        with app.state.db.session() as session:
            events = session.scalars(
                select(AdminAuditEvent)
                .where(
                    AdminAuditEvent.target_id == quarantine_item['quarantine_id'],
                    AdminAuditEvent.action.in_(
                        [
                            'office_jobs.quarantine.restore.intent',
                            'office_jobs.quarantine.restore',
                        ]
                    ),
                )
                .order_by(AdminAuditEvent.id)
            ).all()
        assert [(event.action, event.status, event.actor_user_id) for event in events] == [
            ('office_jobs.quarantine.restore.intent', 'intent', manager_id),
            ('office_jobs.quarantine.restore', 'success', manager_id),
        ]
        intent_metadata = json.loads(events[0].metadata_json or '{}')
        success_metadata = json.loads(events[1].metadata_json or '{}')
        assert intent_metadata['owner_id'] == owner_id
        assert success_metadata['item']['owner_id'] == owner_id
        assert success_metadata['outcome']['owner_id'] == owner_id
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)

def test_quarantine_owner_metadata_mismatch_is_never_attributed_or_mutated(
    app,
    tmp_path: Path,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        owner_id = _admin_id(app)
        record = store.create('report', owner_id=owner_id)
        store.write_bytes(record['job_id'], 'report.txt', b'payload', 'text/plain')
        quarantine_item = store._quarantine_corrupt_job(
            store.job_dir(record['job_id']),
            'owner attribution validation fixture',
        )
        assert quarantine_item is not None
        quarantine_id = str(quarantine_item['quarantine_id'])
        entry = store._quarantine_root / quarantine_id
        metadata_path = entry / 'metadata.json'
        metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
        metadata['owner_id'] = owner_id + 1
        metadata_path.write_text(json.dumps(metadata), encoding='utf-8')

        inventory = store.list_quarantine()
        assert inventory['items'][0]['kind'] == 'corrupt'
        assert inventory['items'][0]['quarantine_id'] is None
        assert inventory['items'][0]['job_id'] is None
        assert inventory['items'][0]['owner_id'] is None
        with pytest.raises(OfficeJobCorruptionError):
            store.restore_quarantine_outcome(quarantine_id)
        with pytest.raises(OfficeJobCorruptionError):
            store.delete_quarantine_outcome(quarantine_id)

        manager_client = _office_user_client(
            app,
            'quarantine-owner-mismatch-manager',
            permissions=('office.use', 'admin.office.manage'),
        )
        restore = manager_client.post(f'/api/v1/office-tools/jobs/quarantine/{quarantine_id}/restore')
        delete = manager_client.delete(f'/api/v1/office-tools/jobs/quarantine/{quarantine_id}')
        assert [restore.status_code, delete.status_code] == [404, 404]
        assert entry.is_dir()
        with app.state.db.session() as session:
            audits = session.scalars(
                select(AdminAuditEvent).where(
                    AdminAuditEvent.target_id == quarantine_id,
                    AdminAuditEvent.action.in_(
                        [
                            'office_jobs.quarantine.restore.intent',
                            'office_jobs.quarantine.restore',
                            'office_jobs.quarantine.delete.intent',
                            'office_jobs.quarantine.delete',
                        ]
                    ),
                )
            ).all()
        assert audits == []
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)

def test_quarantine_delete_preserves_known_owner_in_inventory_response_and_audit(
    app,
    tmp_path: Path,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        _office_user_client(app, 'quarantine-delete-owner')
        owner_id = _user_id(app, 'quarantine-delete-owner')
        manager_client = _office_user_client(
            app,
            'quarantine-delete-manager',
            permissions=('office.use', 'admin.office.manage'),
        )
        manager_id = _user_id(app, 'quarantine-delete-manager')
        quarantined_job = store.create('report', owner_id=owner_id)
        store.write_bytes(
            quarantined_job['job_id'],
            'delete.txt',
            b'delete payload',
            'text/plain',
        )
        quarantine_item = store._quarantine_corrupt_job(
            store.job_dir(quarantined_job['job_id']),
            'quarantine deletion owner fixture',
        )
        assert quarantine_item is not None
        metadata_path = store._quarantine_root / str(quarantine_item['quarantine_id']) / 'metadata.json'
        metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
        assert metadata['owner_id'] == owner_id
        assert not store._owner_identity_path(quarantined_job['job_id']).exists()
        quarantine_inventory_item = store.list_quarantine()['items'][0]
        assert quarantine_inventory_item['owner_id'] == owner_id

        response = manager_client.delete(
            f"/api/v1/office-tools/jobs/quarantine/{quarantine_item['quarantine_id']}"
        )

        expected_outcome = {
            'operation': 'quarantine_delete',
            'target_id': quarantine_item['quarantine_id'],
            'management_token': None,
            'job_id': quarantined_job['job_id'],
            'owner_id': owner_id,
            'logical_bytes': len(b'delete payload'),
            'physical_bytes': quarantine_inventory_item['physical_bytes'],
            'partial_bytes_removed': quarantine_inventory_item['physical_bytes'],
            'published': False,
            'removed': True,
            'durably_synced': True,
            **_completed_durability_fields(),
        }
        assert response.status_code == 200
        assert response.json() == {
            'item': {**quarantine_inventory_item, 'management_token': None},
            'outcome': expected_outcome,
        }
        assert not (store._quarantine_root / str(quarantine_item['quarantine_id'])).exists()

        with app.state.db.session() as session:
            events = session.scalars(
                select(AdminAuditEvent)
                .where(
                    AdminAuditEvent.target_id == quarantine_item['quarantine_id'],
                    AdminAuditEvent.action.in_(
                        [
                            'office_jobs.quarantine.delete.intent',
                            'office_jobs.quarantine.delete',
                        ]
                    ),
                )
                .order_by(AdminAuditEvent.id)
            ).all()
        assert [(event.action, event.status, event.actor_user_id) for event in events] == [
            ('office_jobs.quarantine.delete.intent', 'intent', manager_id),
            ('office_jobs.quarantine.delete', 'success', manager_id),
        ]
        intent_metadata = json.loads(events[0].metadata_json or '{}')
        success_metadata = json.loads(events[1].metadata_json or '{}')
        assert intent_metadata['owner_id'] == owner_id
        assert success_metadata['item']['owner_id'] == owner_id
        assert success_metadata['outcome'] == {
            **expected_outcome,
            'management_token': '[REDACTED]',
        }
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)

@pytest.mark.parametrize(
    ('limits', 'quarantined_bytes', 'active_bytes', 'detail'),
    [
        (
            {'max_jobs_per_owner': 1},
            b'quarantined',
            b'active',
            'owner job quota exceeded',
        ),
        (
            {'max_jobs_per_owner': 2, 'max_bytes_per_owner': 5},
            b'abc',
            b'xyz',
            'owner storage quota exceeded',
        ),
    ],
    ids=['job-count-quota', 'byte-quota'],
)
def test_restore_records_intent_before_atomic_capacity_failure_and_preserves_quarantine(
    app,
    tmp_path: Path,
    monkeypatch,
    limits: dict[str, int],
    quarantined_bytes: bytes,
    active_bytes: bytes,
    detail: str,
) -> None:
    store = _store(tmp_path / 'office_jobs', **limits)
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        _office_user_client(app, 'restore-owner')
        owner_id = _user_id(app, 'restore-owner')
        manager_client = _office_user_client(
            app,
            'restore-manager',
            permissions=('office.use', 'admin.office.manage'),
        )
        manager_id = _user_id(app, 'restore-manager')
        quarantined_job = store.create('report', owner_id=owner_id)
        store.write_bytes(quarantined_job['job_id'], 'quarantined.txt', quarantined_bytes, 'text/plain')
        quarantine_item = store._quarantine_corrupt_job(
            store.job_dir(quarantined_job['job_id']),
            'manual recovery verification',
        )
        assert quarantine_item is not None
        occupying_job = store.create('chart', owner_id=owner_id)
        store.write_bytes(occupying_job['job_id'], 'active.txt', active_bytes, 'text/plain')
        usage_before_restore = store.usage_for_owner(owner_id)
        original_restore_outcome = store.restore_quarantine_outcome
        intent_was_committed = False

        def restore_after_committed_intent(quarantine_id: str) -> dict[str, object]:
            nonlocal intent_was_committed
            with app.state.db.session() as session:
                intent_events = session.scalars(
                    select(AdminAuditEvent)
                    .where(
                        AdminAuditEvent.action == 'office_jobs.quarantine.restore.intent',
                        AdminAuditEvent.target_id == quarantine_id,
                    )
                    .order_by(AdminAuditEvent.id)
                ).all()
            assert [(event.status, event.actor_user_id) for event in intent_events] == [
                ('intent', manager_id)
            ]
            intent_was_committed = True
            return original_restore_outcome(quarantine_id)

        monkeypatch.setattr(store, 'restore_quarantine_outcome', restore_after_committed_intent)
        response = manager_client.post(
            f"/api/v1/office-tools/jobs/quarantine/{quarantine_item['quarantine_id']}/restore"
        )

        assert response.status_code == 422, response.json()
        assert response.json()['detail'] == detail
        assert intent_was_committed
        assert store.get(occupying_job['job_id'])['job_id'] == occupying_job['job_id']
        assert store.artifact_path(occupying_job['job_id'], 'active.txt').read_bytes() == active_bytes
        assert store.usage_for_owner(owner_id) == usage_before_restore
        with pytest.raises(FileNotFoundError):
            store.get(quarantined_job['job_id'])
        assert (store._quarantine_root / quarantine_item['quarantine_id'] / 'payload' / 'quarantined.txt').read_bytes() == quarantined_bytes
        assert [
            item['quarantine_id'] for item in store.list_quarantine()['items']
        ] == [quarantine_item['quarantine_id']]
        with app.state.db.session() as session:
            events = session.scalars(
                select(AdminAuditEvent)
                .where(
                    AdminAuditEvent.target_id == quarantine_item['quarantine_id'],
                    AdminAuditEvent.action.in_(
                        [
                            'office_jobs.quarantine.restore.intent',
                            'office_jobs.quarantine.restore',
                        ]
                    ),
                )
                .order_by(AdminAuditEvent.id)
            ).all()
        assert [(event.action, event.status, event.actor_user_id) for event in events] == [
            ('office_jobs.quarantine.restore.intent', 'intent', manager_id),
            ('office_jobs.quarantine.restore', 'partial_failure', manager_id),
        ]
        failure_metadata = json.loads(events[1].metadata_json or '{}')
        assert failure_metadata['error'] == detail
        assert failure_metadata['intent']['quarantine_id'] == quarantine_item['quarantine_id']
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)


@pytest.mark.parametrize(
    ('limits', 'disk_free', 'detail'),
    [
        ({'max_temporary_bundles': 0}, None, 'temporary office bundle limit exceeded'),
        ({'min_free_bytes': 1}, 0, 'office bundle volume is below the minimum free disk threshold'),
    ],
)
def test_bundle_capacity_errors_return_422_without_leaking_bundle_files(
    app,
    csrf_client: TestClient,
    tmp_path: Path,
    monkeypatch,
    limits: dict[str, int],
    disk_free: int | None,
    detail: str,
) -> None:
    store = _store(tmp_path / 'office_jobs', **limits)
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        record = store.create('report', owner_id=_admin_id(app))
        store.write_bytes(record['job_id'], 'report.txt', b'contents', 'text/plain')
        if disk_free is not None:
            monkeypatch.setattr(
                job_store_module.shutil,
                'disk_usage',
                lambda _path: SimpleNamespace(free=disk_free),
            )

        response = csrf_client.get(f"/api/v1/office-tools/jobs/{record['job_id']}/bundle")

        assert response.status_code == 422
        assert response.json()['detail'] == detail
        assert not list((store.root / '.bundles').iterdir())
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)
def test_temporary_bundle_limit_rejects_a_second_request_without_leaking_and_reuses_after_release(
    app,
    csrf_client: TestClient,
    tmp_path: Path,
) -> None:
    store = _store(tmp_path / 'office_jobs', max_temporary_bundles=1)
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        record = store.create('report', owner_id=_admin_id(app))
        store.write_bytes(record['job_id'], 'report.txt', b'contents', 'text/plain')
        held_bundle = store.create_temporary_bundle(record['job_id'])
        assert held_bundle.is_file()
        assert list(store._bundles_root.iterdir()) == [held_bundle]

        rejected = csrf_client.get(f"/api/v1/office-tools/jobs/{record['job_id']}/bundle")

        assert rejected.status_code == 422
        assert rejected.json()['detail'] == 'temporary office bundle limit exceeded'
        assert list(store._bundles_root.iterdir()) == [held_bundle]

        store.delete_temporary_bundle(held_bundle)
        assert not list(store._bundles_root.iterdir())

        reused = csrf_client.get(f"/api/v1/office-tools/jobs/{record['job_id']}/bundle")

        assert reused.status_code == 200
        assert not list(store._bundles_root.iterdir())
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)


def test_temporary_bundle_failure_after_publish_cleans_staging_and_partial_bundle(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    record = store.create('report', owner_id=1)
    store.write_bytes(record['job_id'], 'report.txt', b'contents', 'text/plain')
    original_fsync_directory = store._fsync_directory
    published_bundle_paths: list[Path] = []
    failed_after_publish = False

    def fail_after_bundle_publish(path: Path) -> None:
        nonlocal failed_after_publish
        if path == store._bundles_root and not failed_after_publish:
            failed_after_publish = True
            published_bundle_paths.extend(store._bundles_root.iterdir())
            assert any(path.name.startswith('bundle-') for path in published_bundle_paths)
            raise OSError('bundle directory fsync failed after publish')
        original_fsync_directory(path)

    monkeypatch.setattr(store, '_fsync_directory', fail_after_bundle_publish)

    with pytest.raises(OSError, match='bundle directory fsync failed after publish'):
        store.create_temporary_bundle(record['job_id'])

    assert failed_after_publish
    assert published_bundle_paths
    assert not list(store._bundles_root.iterdir())

def test_owner_reads_job_and_artifact(app, csrf_client: TestClient, tmp_path: Path) -> None:
    store = _store(tmp_path / 'office_jobs')
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


def test_owner_only_listing_is_newest_first_and_stable(app, csrf_client: TestClient, tmp_path: Path) -> None:
    store = _store(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        owner = _admin_id(app)
        older = store.create('report', owner_id=owner)
        newer = store.create('chart', owner_id=owner)
        foreign = store.create('diagram', owner_id=owner + 9999)
        now = datetime.now(UTC)
        _set_job_timestamp(store, older['job_id'], now - timedelta(minutes=1))
        _set_job_timestamp(store, newer['job_id'], now)
        _set_job_timestamp(store, foreign['job_id'], now + timedelta(minutes=1))

        response = csrf_client.get('/api/v1/office-tools/jobs')
        assert response.status_code == 200
        body = response.json()
        job_ids = [job['job_id'] for job in body['jobs']]
        assert job_ids == [newer['job_id'], older['job_id']]
        assert foreign['job_id'] not in job_ids
        usage = body['usage']
        assert usage['job_count'] == 2
        assert usage['total_bytes'] == 0
        assert usage['max_jobs_per_owner'] == 100
        assert usage['max_bytes_per_owner'] == 1024 * 1024

        repeated = csrf_client.get('/api/v1/office-tools/jobs')
        assert [job['job_id'] for job in repeated.json()['jobs']] == job_ids
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)


def test_owner_job_list_exposes_only_safe_completed_display_metadata(
    app,
    csrf_client: TestClient,
    tmp_path: Path,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        owner_id = _admin_id(app)
        other_client = _office_user_client(app, 'job-list-display-other')
        other_owner_id = _user_id(app, 'job-list-display-other')
        completed = store.create(
            'diagram',
            owner_id=owner_id,
            request_summary={
                'request_body': {'description': 'private diagram request'},
                'request_provenance': {'ip_address': '127.0.0.1'},
            },
        )
        store.complete(
            completed['job_id'],
            extra={
                'title': '승인 다이어그램',
                'llm_used': True,
                'filesystem_path': 'C:/private/diagram',
                'management_token': 'private-token',
                'description_sha256': 'a' * 64,
                'private_receipt': {'actor_id': owner_id},
            },
        )
        legacy = store.create('report', owner_id=owner_id)
        store.complete(legacy['job_id'])
        running = store.create(
            'chart',
            owner_id=owner_id,
            request_summary={'title': '요청 제목', 'llm_used': True},
        )
        foreign = store.create('diagram', owner_id=other_owner_id)
        store.complete(
            foreign['job_id'],
            extra={'title': '다른 소유자 다이어그램', 'llm_used': False},
        )

        response = csrf_client.get('/api/v1/office-tools/jobs')
        assert response.status_code == 200
        jobs_by_id = {job['job_id']: job for job in response.json()['jobs']}
        assert set(jobs_by_id) == {completed['job_id'], legacy['job_id'], running['job_id']}
        assert jobs_by_id[completed['job_id']]['title'] == '승인 다이어그램'
        assert jobs_by_id[completed['job_id']]['llm_used'] is True
        assert jobs_by_id[legacy['job_id']]['title'] is None
        assert jobs_by_id[legacy['job_id']]['llm_used'] is None
        assert jobs_by_id[running['job_id']]['title'] is None
        assert jobs_by_id[running['job_id']]['llm_used'] is None

        allowed_keys = {
            'job_id',
            'service',
            'status',
            'created_at',
            'updated_at',
            'warnings',
            'artifacts',
            'title',
            'llm_used',
        }
        sensitive_keys = {
            'owner_id',
            'request_body',
            'request_provenance',
            'filesystem_path',
            'management_token',
            'description_sha256',
            'private_receipt',
        }
        for job in jobs_by_id.values():
            assert set(job) == allowed_keys
            assert sensitive_keys.isdisjoint(job)

        other_response = other_client.get('/api/v1/office-tools/jobs')
        assert other_response.status_code == 200
        other_jobs = other_response.json()['jobs']
        assert [job['job_id'] for job in other_jobs] == [foreign['job_id']]
        assert other_jobs[0]['title'] == '다른 소유자 다이어그램'
        assert other_jobs[0]['llm_used'] is False
        assert set(other_jobs[0]) == allowed_keys
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)


def test_owner_deletes_job_with_valid_csrf(app, csrf_client: TestClient, tmp_path: Path) -> None:
    store = _store(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        owner_id = _admin_id(app)
        record = store.create('report', owner_id=owner_id)
        job_id = record['job_id']
        physical_bytes = store._physical_size_no_follow(store.job_dir(job_id))

        response = csrf_client.delete(f'/api/v1/office-tools/jobs/{job_id}')

        expected_outcome = {
            'operation': 'owner_delete',
            'job_id': job_id,
            'owner_id': owner_id,
            'logical_bytes': 0,
            'physical_bytes': physical_bytes,
            'partial_bytes_removed': physical_bytes,
            'removed': True,
            **_completed_owner_durability_fields(),
            'owner_identity_removed': True,
        }
        assert response.status_code == 200
        assert response.json() == {'outcome': expected_outcome}
        assert csrf_client.get(f'/api/v1/office-tools/jobs/{job_id}').status_code == 404
        assert store.list_for_owner(owner_id) == []
        assert not store._owner_identity_path(job_id).exists()
        with app.state.db.session() as session:
            events = session.scalars(
                select(AdminAuditEvent)
                .where(
                    AdminAuditEvent.target_id == job_id,
                    AdminAuditEvent.action.in_(
                        ['office_jobs.owner_delete.intent', 'office_jobs.owner_delete']
                    ),
                )
                .order_by(AdminAuditEvent.id)
            ).all()
        assert [(event.action, event.status, event.actor_user_id) for event in events] == [
            ('office_jobs.owner_delete.intent', 'intent', owner_id),
            ('office_jobs.owner_delete', 'success', owner_id),
        ]
        assert json.loads(events[0].metadata_json or '{}') == {
            'job_id': job_id,
            'owner_id': owner_id,
            'retrying_sidecar_cleanup': False,
        }
        assert json.loads(events[1].metadata_json or '{}') == {'outcome': expected_outcome}
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)


def test_owner_delete_returns_typed_partial_outcome_and_retries_sidecar_cleanup(
    app,
    csrf_client: TestClient,
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        owner_id = _admin_id(app)
        record = store.create('report', owner_id=owner_id)
        job_id = record['job_id']
        physical_bytes = store._physical_size_no_follow(store.job_dir(job_id))
        original_cleanup = store._remove_owner_identity_after_resolution
        attempts = 0

        def fail_cleanup_once(resolved_job_id: str) -> None:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise OSError('injected owner sidecar cleanup failure')
            original_cleanup(resolved_job_id)

        monkeypatch.setattr(store, '_remove_owner_identity_after_resolution', fail_cleanup_once)
        partial = csrf_client.delete(f'/api/v1/office-tools/jobs/{job_id}')

        expected_partial_outcome = {
            'operation': 'owner_delete',
            'job_id': job_id,
            'owner_id': owner_id,
            'logical_bytes': 0,
            'physical_bytes': physical_bytes,
            'partial_bytes_removed': physical_bytes,
            'removed': True,
            **_completed_durability_fields(),
            'owner_identity_removed': False,
            'owner_identity_durably_synced': False,
            'owner_identity_durability': 'pending',
            'retry_required': True,
        }
        assert partial.status_code == 500
        assert partial.json() == {
            'detail': {
                'error': 'office job deletion partially failed',
                'outcome': expected_partial_outcome,
            }
        }
        assert not (store.root / job_id).exists()
        assert store._owner_identity_path(job_id).exists()

        retry = csrf_client.delete(f'/api/v1/office-tools/jobs/{job_id}')
        expected_retry_outcome = {
            **expected_partial_outcome,
            **_completed_owner_durability_fields(),
            'owner_identity_removed': True,
        }
        assert retry.status_code == 200
        assert retry.json() == {'outcome': expected_retry_outcome}
        assert not store._owner_identity_path(job_id).exists()
        with app.state.db.session() as session:
            events = session.scalars(
                select(AdminAuditEvent)
                .where(
                    AdminAuditEvent.target_id == job_id,
                    AdminAuditEvent.action.in_(
                        ['office_jobs.owner_delete.intent', 'office_jobs.owner_delete']
                    ),
                )
                .order_by(AdminAuditEvent.id)
            ).all()
        assert [(event.action, event.status) for event in events] == [
            ('office_jobs.owner_delete.intent', 'intent'),
            ('office_jobs.owner_delete', 'partial_failure'),
            ('office_jobs.owner_delete.intent', 'intent'),
            ('office_jobs.owner_delete', 'success'),
        ]
        retry_metadata = json.loads(events[2].metadata_json or '{}')
        assert retry_metadata['job_id'] == job_id
        assert retry_metadata['owner_id'] == owner_id
        assert retry_metadata['retrying_sidecar_cleanup'] is False
        assert retry_metadata['stored_outcome'] == expected_partial_outcome
        assert json.loads(events[1].metadata_json or '{}')['outcome'] == expected_partial_outcome
        assert json.loads(events[3].metadata_json or '{}') == {
            'outcome': expected_retry_outcome,
        }
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)

def test_owner_delete_reports_removed_job_when_root_fsync_fails_then_retries(
    app,
    csrf_client: TestClient,
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        owner_id = _admin_id(app)
        record = store.create('report', owner_id=owner_id)
        job_id = record['job_id']
        physical_bytes = store._physical_size_no_follow(store.job_dir(job_id))
        original_fsync_directory = store._fsync_directory
        root_fsync_calls = 0

        def fail_job_removal_fsync(path: Path) -> None:
            nonlocal root_fsync_calls
            if Path(path) == store.root and not (store.root / job_id).exists():
                root_fsync_calls += 1
                if root_fsync_calls == 1:
                    raise OSError('injected owner deletion root fsync failure')
            original_fsync_directory(path)

        monkeypatch.setattr(store, '_fsync_directory', fail_job_removal_fsync)
        partial = csrf_client.delete(f'/api/v1/office-tools/jobs/{job_id}')
        expected_partial_outcome = {
            'operation': 'owner_delete',
            'job_id': job_id,
            'owner_id': owner_id,
            'logical_bytes': 0,
            'physical_bytes': physical_bytes,
            'partial_bytes_removed': physical_bytes,
            'removed': True,
            'durably_synced': False,
            'durability': 'pending',
            'owner_identity_removed': False,
            'owner_identity_durably_synced': False,
            'owner_identity_durability': 'pending',
            'retry_required': True,
        }
        assert partial.status_code == 500
        assert partial.json()['detail']['outcome'] == expected_partial_outcome
        assert not (store.root / job_id).exists()
        assert store._owner_identity_path(job_id).exists()

        monkeypatch.setattr(store, '_fsync_directory', original_fsync_directory)
        retry = csrf_client.delete(f'/api/v1/office-tools/jobs/{job_id}')
        assert retry.status_code == 200
        assert retry.json()['outcome'] == {
            **expected_partial_outcome,
            **_completed_owner_durability_fields(),
            'owner_identity_removed': True,
        }
        assert not store._owner_identity_path(job_id).exists()
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)

def test_cross_owner_delete_is_forbidden_and_preserves_job(app, csrf_client: TestClient, tmp_path: Path) -> None:
    store = _store(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        foreign = store.create('report', owner_id=_admin_id(app) + 9999)

        response = csrf_client.delete(f"/api/v1/office-tools/jobs/{foreign['job_id']}")
        assert response.status_code == 403
        assert store.get(foreign['job_id'])['owner_id'] == _admin_id(app) + 9999
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)


def test_other_owner_forbidden(app, csrf_client: TestClient, tmp_path: Path) -> None:
    store = _store(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        foreign = store.create('report', owner_id=_admin_id(app) + 9999)
        resp = csrf_client.get(f"/api/v1/office-tools/jobs/{foreign['job_id']}")
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)


def test_expired_purge_requires_manage_permission_and_csrf_and_records_audit(
    app,
    tmp_path: Path,
) -> None:
    store = _store(tmp_path / 'office_jobs', retention_days=1)
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        expired = store.create('report', owner_id=_admin_id(app))
        store.write_bytes(expired['job_id'], 'expired.txt', b'old', 'text/plain')
        _set_job_timestamp(store, expired['job_id'], datetime.now(UTC) - timedelta(days=2))
        expired_quarantine_job = store.create('chart', owner_id=_admin_id(app))
        expired_quarantine_payload = b'expired quarantine evidence'
        store.write_bytes(
            expired_quarantine_job['job_id'],
            'expired-quarantine.txt',
            expired_quarantine_payload,
            'text/plain',
        )
        expired_quarantine_item = store._quarantine_corrupt_job(
            store.job_dir(expired_quarantine_job['job_id']),
            'expired quarantine purge fixture',
        )
        assert expired_quarantine_item is not None
        expired_quarantine_entry = store._quarantine_root / expired_quarantine_item['quarantine_id']
        expired_quarantine_metadata_path = expired_quarantine_entry / 'metadata.json'
        expired_quarantine_metadata = json.loads(expired_quarantine_metadata_path.read_text(encoding='utf-8'))
        expired_quarantine_metadata['quarantined_at'] = (
            datetime.now(UTC) - timedelta(days=31)
        ).isoformat()
        expired_quarantine_metadata_path.write_text(
            json.dumps(expired_quarantine_metadata),
            encoding='utf-8',
        )
        expired_quarantine_physical_deleted_bytes = sum(
            path.stat().st_size
            for path in expired_quarantine_entry.rglob('*')
            if path.is_file()
        )

        stale_bundle = store._bundles_root / f'bundle-{"d" * 32}.zip'
        stale_bundle_payload = b'stale bundle purge evidence'
        stale_bundle.write_bytes(stale_bundle_payload)
        stale_bundle_timestamp = datetime.now(UTC) - timedelta(hours=2)
        os.utime(stale_bundle, (stale_bundle_timestamp.timestamp(), stale_bundle_timestamp.timestamp()))
        corrupt_id = 'e' * 32
        corrupt_dir = store.root / corrupt_id
        corrupt_dir.mkdir()
        corrupt_job_metadata = corrupt_dir / 'job.json'
        corrupt_payload_file = corrupt_dir / 'orphan.bin'
        corrupt_job_metadata.write_text('{invalid', encoding='utf-8')
        corrupt_payload_file.write_bytes(b'bad')
        corrupt_payload_bytes = (
            corrupt_job_metadata.stat().st_size + corrupt_payload_file.stat().st_size
        )
        store_before_unauthorized_purges = _filesystem_snapshot(store.root)

        office_only_client = _office_user_client(app, 'office-only')
        assert office_only_client.post('/api/v1/office-tools/jobs/admin/purge').status_code == 403
        manage_only_client = _office_user_client(
            app,
            'purge-manage-only',
            permissions=('admin.office.manage',),
        )
        assert manage_only_client.post('/api/v1/office-tools/jobs/admin/purge').status_code == 403

        no_csrf_client = TestClient(app)
        login = no_csrf_client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'})
        assert login.status_code == 200
        assert no_csrf_client.post('/api/v1/office-tools/jobs/admin/purge').status_code == 403
        assert _filesystem_snapshot(store.root) == store_before_unauthorized_purges
        with app.state.db.session() as session:
            unauthorized_purge_audits = session.scalars(
                select(AdminAuditEvent).where(
                    AdminAuditEvent.action.in_(
                        ['office_jobs.purge_expired.intent', 'office_jobs.purge_expired']
                    )
                )
            ).all()
        assert unauthorized_purge_audits == []

        manager_client = _office_user_client(
            app,
            'office-manager',
            permissions=('office.use', 'admin.office.manage'),
        )
        response = manager_client.post('/api/v1/office-tools/jobs/admin/purge')
        assert response.status_code == 200
        purge_result = response.json()
        quarantined_entry = store._quarantine_root / purge_result['quarantined_quarantine_ids'][0]
        quarantined_physical_bytes = store._physical_size_no_follow(quarantined_entry)
        assert set(purge_result) == {
            'deleted_jobs',
            'deleted_job_ids',
            'freed_bytes',
            'logical_artifact_freed_bytes',
            'physical_deleted_bytes',
            'quarantined_job_ids',
            'quarantined_quarantine_ids',
            'quarantined_bytes',
            'logical_artifact_quarantined_bytes',
            'physical_quarantined_bytes',
            'failed_job_ids',
            'failed_quarantine_ids',
            'quarantine_bytes',
            'temporary_bundle_bytes',
            'expired_quarantine_entries',
            'expired_quarantine_bytes',
            'expired_quarantine_ids',
            'stale_bundles',
            'stale_bundle_bytes',
            'orphan_stage_dirs',
            'orphan_stage_bytes',
            'maintenance',
            'partial_deletion_outcomes',
        }
        assert purge_result['deleted_jobs'] == 1
        assert purge_result['deleted_job_ids'] == [expired['job_id']]
        assert purge_result['freed_bytes'] == 3
        assert purge_result['logical_artifact_freed_bytes'] == 3
        assert purge_result['physical_deleted_bytes'] > 3
        assert purge_result['quarantined_job_ids'] == [corrupt_id]
        assert len(purge_result['quarantined_quarantine_ids']) == 1
        assert purge_result['quarantined_bytes'] == corrupt_payload_bytes
        assert purge_result['logical_artifact_quarantined_bytes'] == 0
        assert purge_result['physical_quarantined_bytes'] == corrupt_payload_bytes
        assert purge_result['failed_job_ids'] == []
        assert purge_result['failed_quarantine_ids'] == []
        assert purge_result['quarantine_bytes'] == quarantined_physical_bytes
        assert purge_result['temporary_bundle_bytes'] == 0
        assert purge_result['expired_quarantine_entries'] == 1
        assert purge_result['expired_quarantine_bytes'] == expired_quarantine_physical_deleted_bytes
        assert purge_result['expired_quarantine_ids'] == [expired_quarantine_item['quarantine_id']]
        assert purge_result['partial_deletion_outcomes'] == []
        assert purge_result['stale_bundles'] == 1
        assert purge_result['stale_bundle_bytes'] == len(stale_bundle_payload)
        assert purge_result['orphan_stage_dirs'] == 0
        assert purge_result['orphan_stage_bytes'] == 0
        assert purge_result['maintenance'] == {
            'recovered_transactions': 0,
            'rolled_back_transactions': 0,
            'unresolved_recovery_transactions': 0,
            'unresolved_recovery_ids': [],
            'malformed_recovery_evidence': 0,
            'owner_deletion_tombstone_failures': [],
            'orphan_stage_dirs': 0,
            'orphan_stage_bytes': 0,
            'stale_bundles': 1,
            'stale_bundle_bytes': len(stale_bundle_payload),
            'expired_quarantine_entries': 1,
            'expired_quarantine_bytes': expired_quarantine_physical_deleted_bytes,
        }
        assert not corrupt_dir.exists()
        assert not (store.root / expired['job_id']).exists()
        assert not expired_quarantine_entry.exists()
        assert not stale_bundle.exists()

        with app.state.db.session() as session:
            audit = session.scalar(
                select(AdminAuditEvent).where(AdminAuditEvent.action == 'office_jobs.purge_expired')
            )
        assert audit is not None
        assert audit.actor_user_id == _user_id(app, 'office-manager')
        assert audit.target_type == 'office_job'
        audit_metadata = json.loads(audit.metadata_json or '{}')
        assert audit_metadata == purge_result

        quarantine_inventory = store.list_quarantine()
        assert quarantine_inventory['total_bytes'] == quarantined_physical_bytes
        assert len(quarantine_inventory['items']) == 1
        assert quarantine_inventory['items'][0]['kind'] == 'corrupt'
        assert quarantine_inventory['items'][0]['job_id'] is None
        assert quarantine_inventory['items'][0]['owner_id'] is None
        assert quarantine_inventory['items'][0]['size_bytes'] == quarantined_physical_bytes
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)
def test_mid_purge_failure_returns_and_audits_exact_partial_result(
    app,
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = _store(tmp_path / 'office_jobs', retention_days=1)
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        first = store.create('report', owner_id=_admin_id(app))
        second = store.create('chart', owner_id=_admin_id(app))
        payloads = {
            first['job_id']: b'first expired artifact',
            second['job_id']: b'second expired artifact',
        }
        for job_id, payload in payloads.items():
            store.write_bytes(job_id, 'expired.txt', payload, 'text/plain')
            _set_job_timestamp(store, job_id, datetime.now(UTC) - timedelta(days=2))

        original_delete_job_dir = store._safe_delete_job_dir
        completed_job_ids: list[str] = []

        def fail_after_first_delete(job_dir: Path):
            if completed_job_ids:
                raise OSError('injected mid-purge delete failure')
            outcome = original_delete_job_dir(job_dir)
            completed_job_ids.append(job_dir.name)
            return outcome

        monkeypatch.setattr(store, '_safe_delete_job_dir', fail_after_first_delete)
        manager_client = _office_user_client(
            app,
            'partial-purge-manager',
            permissions=('office.use', 'admin.office.manage'),
        )
        response = manager_client.post('/api/v1/office-tools/jobs/admin/purge')

        assert response.status_code == 500
        detail = response.json()['detail']
        assert detail['error'] == 'office job purge partially failed'
        partial_result = detail['partial_result']
        assert set(partial_result) == {
            'deleted_jobs',
            'deleted_job_ids',
            'freed_bytes',
            'logical_artifact_freed_bytes',
            'physical_deleted_bytes',
            'quarantined_job_ids',
            'quarantined_quarantine_ids',
            'quarantined_bytes',
            'logical_artifact_quarantined_bytes',
            'physical_quarantined_bytes',
            'failed_job_ids',
            'failed_quarantine_ids',
            'quarantine_bytes',
            'temporary_bundle_bytes',
            'expired_quarantine_entries',
            'expired_quarantine_bytes',
            'expired_quarantine_ids',
            'stale_bundles',
            'stale_bundle_bytes',
            'orphan_stage_dirs',
            'orphan_stage_bytes',
            'maintenance',
            'partial_deletion_outcomes',
        }
        assert completed_job_ids == partial_result['deleted_job_ids']
        assert partial_result['deleted_jobs'] == 1
        assert partial_result['freed_bytes'] == len(payloads[completed_job_ids[0]])
        assert partial_result['logical_artifact_freed_bytes'] == len(payloads[completed_job_ids[0]])
        assert partial_result['physical_deleted_bytes'] > partial_result['freed_bytes']
        remaining_job_id = next(job_id for job_id in payloads if job_id not in completed_job_ids)
        assert partial_result['failed_job_ids'] == [remaining_job_id]
        assert partial_result['failed_quarantine_ids'] == []
        assert partial_result['quarantined_job_ids'] == []
        assert partial_result['quarantined_quarantine_ids'] == []
        assert partial_result['partial_deletion_outcomes'] == []
        assert partial_result['maintenance']['unresolved_recovery_transactions'] == 0
        with pytest.raises(FileNotFoundError):
            store.get(completed_job_ids[0])
        assert store.get(remaining_job_id)['job_id'] == remaining_job_id

        with app.state.db.session() as session:
            audit = session.scalar(
                select(AdminAuditEvent).where(
                    AdminAuditEvent.action == 'office_jobs.purge_expired',
                    AdminAuditEvent.status == 'partial_failure',
                )
            )
        assert audit is not None
        audit_metadata = json.loads(audit.metadata_json or '{}')
        assert audit_metadata['partial_result'] == partial_result
        assert audit_metadata['error'] == 'office job purge partially failed'
        response_schema = app.openapi()['paths']['/api/v1/office-tools/jobs/admin/purge']['post'][
            'responses'
        ]['500']['content']['application/json']['schema']
        assert response_schema['$ref'].endswith('/OfficeJobPurgeFailureResponse')
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)


def test_purge_exposes_removed_but_not_durably_synced_deletion_outcome(
    app,
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = _store(tmp_path / 'office_jobs', retention_days=1)
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        expired = store.create('report', owner_id=_admin_id(app))
        store.write_bytes(expired['job_id'], 'expired.txt', b'old', 'text/plain')
        _set_job_timestamp(store, expired['job_id'], datetime.now(UTC) - timedelta(days=2))
        physical_bytes = store._physical_size_no_follow(store.job_dir(expired['job_id']))
        original_fsync_directory = store._fsync_directory
        root_fsync_calls = 0

        def fail_removed_job_directory_sync(path: Path) -> None:
            nonlocal root_fsync_calls
            if Path(path) == store.root and not (store.root / expired['job_id']).exists():
                root_fsync_calls += 1
                if root_fsync_calls == 1:
                    raise OSError('injected post-delete root fsync failure')
            original_fsync_directory(path)

        monkeypatch.setattr(store, '_fsync_directory', fail_removed_job_directory_sync)
        manager_client = _office_user_client(
            app,
            'purge-durability-manager',
            permissions=('office.use', 'admin.office.manage'),
        )
        response = manager_client.post('/api/v1/office-tools/jobs/admin/purge')

        expected_outcome = {
            'entry_id': expired['job_id'],
            'entry_kind': 'job',
            'parent_id': expired['job_id'],
            'physical_bytes': physical_bytes,
            'partial_bytes_removed': physical_bytes,
            'removed': True,
            'durably_synced': False,
            'durability': 'pending',
            'retry_required': True,
        }
        assert response.status_code == 500
        partial_result = response.json()['detail']['partial_result']
        assert partial_result['deleted_job_ids'] == [expired['job_id']]
        assert partial_result['partial_deletion_outcomes'] == [expected_outcome]
        assert not (store.root / expired['job_id']).exists()
        assert store._owner_identity_path(expired['job_id']).exists()
        with app.state.db.session() as session:
            audit = session.scalar(
                select(AdminAuditEvent).where(
                    AdminAuditEvent.action == 'office_jobs.purge_expired',
                    AdminAuditEvent.status == 'partial_failure',
                )
            )
        assert audit is not None
        assert json.loads(audit.metadata_json or '{}')['partial_result'] == partial_result
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)

def test_quarantine_mutation_failure_after_payload_move_returns_exact_partial_result(
    app,
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = _store(tmp_path / 'office_jobs', retention_days=1)
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        deleted = store.create('report', owner_id=_admin_id(app))
        deleted_payload = b'expired artifact removed before quarantine failure'
        store.write_bytes(deleted['job_id'], 'expired.txt', deleted_payload, 'text/plain')
        _set_job_timestamp(store, deleted['job_id'], datetime.now(UTC) - timedelta(days=2))
        deleted_dir = store.job_dir(deleted['job_id'])
        deleted_physical_bytes = store._path_size(deleted_dir)

        corrupt_id = 'f' * 32
        corrupt_dir = store.root / corrupt_id
        corrupt_dir.mkdir()
        corrupt_metadata = corrupt_dir / 'job.json'
        corrupt_payload = corrupt_dir / 'unrecoverable.bin'
        corrupt_metadata.write_text('{invalid', encoding='utf-8')
        corrupt_payload.write_bytes(b'corrupt quarantine evidence')
        corrupt_physical_bytes = store._path_size(corrupt_dir)

        original_remove_owner_identity = store._remove_owner_identity_after_resolution
        created_quarantine_ids: list[str] = []

        def fail_after_payload_move(job_id: str) -> None:
            if job_id != corrupt_id:
                original_remove_owner_identity(job_id)
                return
            entries = [entry for entry in store._quarantine_root.iterdir() if entry.is_dir()]
            assert len(entries) == 1
            quarantine_entry = entries[0]
            assert (quarantine_entry / 'payload').is_dir()
            assert not corrupt_dir.exists()
            created_quarantine_ids.append(quarantine_entry.name)
            raise OSError('injected quarantine mutation failure after payload movement')

        monkeypatch.setattr(store, '_job_entries', lambda: [deleted_dir, corrupt_dir])
        monkeypatch.setattr(
            store,
            '_remove_owner_identity_after_resolution',
            fail_after_payload_move,
        )
        manager_client = _office_user_client(
            app,
            'quarantine-partial-purge-manager',
            permissions=('office.use', 'admin.office.manage'),
        )
        response = manager_client.post('/api/v1/office-tools/jobs/admin/purge')

        assert response.status_code == 500
        detail = response.json()['detail']
        assert detail['error'] == 'office job purge partially failed'
        partial_result = detail['partial_result']
        assert len(created_quarantine_ids) == 1
        failed_quarantine_id = created_quarantine_ids[0]
        assert partial_result['failed_quarantine_ids'] == [failed_quarantine_id]
        assert partial_result['deleted_jobs'] == 1
        assert partial_result['deleted_job_ids'] == [deleted['job_id']]
        assert partial_result['freed_bytes'] == len(deleted_payload)
        assert partial_result['logical_artifact_freed_bytes'] == len(deleted_payload)
        assert partial_result['physical_deleted_bytes'] == deleted_physical_bytes
        assert partial_result['failed_job_ids'] == []
        assert partial_result['quarantined_job_ids'] == [corrupt_id]
        assert partial_result['quarantined_quarantine_ids'] == [failed_quarantine_id]
        assert partial_result['quarantined_bytes'] == corrupt_physical_bytes
        assert partial_result['logical_artifact_quarantined_bytes'] == 0
        assert partial_result['physical_quarantined_bytes'] == corrupt_physical_bytes
        assert partial_result['expired_quarantine_entries'] == 0
        assert partial_result['expired_quarantine_bytes'] == 0
        assert partial_result['expired_quarantine_ids'] == []
        assert partial_result['temporary_bundle_bytes'] == 0
        assert partial_result['maintenance']['expired_quarantine_entries'] == 0
        assert partial_result['maintenance']['expired_quarantine_bytes'] == 0
        assert not deleted_dir.exists()
        assert not corrupt_dir.exists()

        quarantine_entry = store._quarantine_root / failed_quarantine_id
        quarantined_physical_bytes = store._physical_size_no_follow(quarantine_entry)
        assert partial_result['quarantine_bytes'] == quarantined_physical_bytes
        quarantine_metadata = json.loads((quarantine_entry / 'metadata.json').read_text(encoding='utf-8'))
        assert set(quarantine_metadata) == {
            'quarantine_id',
            'job_id',
            'size_bytes',
            'quarantined_at',
            'reason',
        }
        assert quarantine_metadata['quarantine_id'] == failed_quarantine_id
        assert quarantine_metadata['job_id'] == corrupt_id
        assert quarantine_metadata['size_bytes'] == corrupt_physical_bytes
        assert isinstance(quarantine_metadata['quarantined_at'], str)
        assert quarantine_metadata['reason'] == 'invalid job metadata or artifacts'
        preserved_payload = quarantine_entry / 'payload'
        assert (preserved_payload / 'job.json').read_bytes() == b'{invalid'
        assert (preserved_payload / 'unrecoverable.bin').read_bytes() == b'corrupt quarantine evidence'

        with app.state.db.session() as session:
            audit = session.scalar(
                select(AdminAuditEvent).where(
                    AdminAuditEvent.action == 'office_jobs.purge_expired',
                    AdminAuditEvent.status == 'partial_failure',
                )
            )
        assert audit is not None
        audit_metadata = json.loads(audit.metadata_json or '{}')
        assert audit_metadata['partial_result'] == partial_result
        assert audit_metadata['partial_result']['failed_job_ids'] == []
        assert audit_metadata['partial_result']['failed_quarantine_ids'] == [failed_quarantine_id]
        assert audit_metadata['partial_result']['quarantined_quarantine_ids'] == [failed_quarantine_id]
        assert audit_metadata['partial_result']['physical_quarantined_bytes'] == corrupt_physical_bytes
        assert audit_metadata['error'] == 'office job purge partially failed'
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)


def test_retention_purge_deletes_only_jobs_just_outside_boundary(tmp_path: Path) -> None:
    store = _store(tmp_path / 'office_jobs', retention_days=1)
    owner = 1
    expired = store.create('report', owner_id=owner)
    retained = store.create('chart', owner_id=owner)
    now = datetime.now(UTC)
    _set_job_timestamp(store, expired['job_id'], now - timedelta(days=1, minutes=1))
    _set_job_timestamp(store, retained['job_id'], now - timedelta(days=1) + timedelta(minutes=1))

    result = store.purge_expired()

    assert result['deleted_jobs'] == 1
    assert result['freed_bytes'] == 0
    with pytest.raises(FileNotFoundError):
        store.get(expired['job_id'])
    assert store.get(retained['job_id'])['job_id'] == retained['job_id']


def test_owner_job_quota_rejects_the_next_job(tmp_path: Path) -> None:
    store = _store(tmp_path / 'office_jobs', max_jobs_per_owner=1)
    owner = 1
    first = store.create('report', owner_id=owner)

    with pytest.raises(OfficeJobCapacityError):
        store.create('chart', owner_id=owner)

    assert [record['job_id'] for record in store.list_for_owner(owner)] == [first['job_id']]


def test_owner_byte_quota_counts_overwrites_by_delta(tmp_path: Path) -> None:
    store = _store(tmp_path / 'office_jobs', max_bytes_per_owner=5)
    record = store.create('report', owner_id=1)
    job_id = record['job_id']

    store.write_bytes(job_id, 'result.txt', b'1234', 'text/plain')
    store.write_bytes(job_id, 'result.txt', b'abcde', 'text/plain')
    assert store.usage_for_owner(1)['total_bytes'] == 5

    with pytest.raises(OfficeJobCapacityError):
        store.write_bytes(job_id, 'result.txt', b'123456', 'text/plain')
    assert store.artifact_path(job_id, 'result.txt').read_bytes() == b'abcde'

    store.write_bytes(job_id, 'result.txt', b'x', 'text/plain')
    store.write_bytes(job_id, 'second.txt', b'1234', 'text/plain')
    assert store.usage_for_owner(1)['total_bytes'] == 5
    with pytest.raises(OfficeJobCapacityError):
        store.write_bytes(job_id, 'third.txt', b'!', 'text/plain')


def test_minimum_free_space_rejects_temporary_artifact_write(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(job_store_module.shutil, 'disk_usage', lambda _path: SimpleNamespace(free=100))
    store = _store(tmp_path / 'office_jobs', min_free_bytes=100)
    record = store.create('report', owner_id=1)

    with pytest.raises(OfficeJobCapacityError):
        store.write_bytes(record['job_id'], 'result.txt', b'x', 'text/plain')

    usage = store.usage_for_owner(1)
    assert usage['job_count'] == 1
    assert usage['total_bytes'] == 0
    with pytest.raises(FileNotFoundError):
        store.artifact_path(record['job_id'], 'result.txt')


def test_invalid_job_id_is_blocked(app, csrf_client: TestClient) -> None:
    assert csrf_client.get('/api/v1/office-tools/jobs/not-a-valid-id').status_code == 404


@pytest.mark.parametrize(
    ('route_filename', 'store_filename'),
    [
        ('..%5Cjob.json', r'..\job.json'),
        ('..%2F..%5Cjob.json', r'../..\job.json'),
        ('C%3A%5Coffice%5Cjob.json', r'C:\office\job.json'),
        ('%5C%5Cserver%5Cshare%5Cjob.json', r'\\server\share\job.json'),
    ],
    ids=['encoded-backslash', 'mixed-separators', 'drive-path', 'unc-like'],
)
def test_artifact_traversal_forms_never_serve_metadata_or_unregistered_files(
    app,
    csrf_client: TestClient,
    tmp_path: Path,
    route_filename: str,
    store_filename: str,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        record = store.create('report', owner_id=_admin_id(app))
        job_dir = store.job_dir(record['job_id'])
        store.write_bytes(record['job_id'], 'registered.txt', b'ok', 'text/plain')
        job_metadata = (job_dir / 'job.json').read_bytes()
        (job_dir / 'unregistered.txt').write_bytes(b'private')

        response = csrf_client.get(
            f"/api/v1/office-tools/jobs/{record['job_id']}/artifacts/{route_filename}"
        )

        assert response.status_code == 404
        assert response.content != job_metadata
        assert response.content != b'private'
        with pytest.raises(FileNotFoundError):
            store.artifact_path(record['job_id'], store_filename)
        with pytest.raises(FileNotFoundError):
            store.artifact_path(record['job_id'], 'job.json')
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)


def test_store_sanitizes_artifact_paths_and_protects_job_metadata(tmp_path: Path) -> None:
    store = _store(tmp_path / 'office_jobs')
    record = store.create('report', owner_id=1)
    job_id = record['job_id']

    artifact = store.write_text(job_id, '../../outside.txt', 'safe', 'text/plain')
    assert artifact == store.job_dir(job_id) / 'outside.txt'
    assert artifact.read_text(encoding='utf-8') == 'safe'
    assert not (tmp_path / 'outside.txt').exists()

    with pytest.raises(ValueError):
        store.write_text(job_id, '../job.json', 'replace', 'application/json')
    assert store.get(job_id)['job_id'] == job_id
def test_create_does_not_implicitly_purge_expired_jobs(tmp_path: Path) -> None:
    store = _store(tmp_path / 'office_jobs', retention_days=1)
    expired = store.create('report', owner_id=1)
    _set_job_timestamp(store, expired['job_id'], datetime.now(UTC) - timedelta(days=2))

    store.create('chart', owner_id=1)

    assert store.get(expired['job_id'])['job_id'] == expired['job_id']
    assert store.purge_expired()['deleted_jobs'] == 1


def test_owner_capacity_lock_blocks_a_second_process_before_quota_check(tmp_path: Path) -> None:
    store = _store(tmp_path / 'office_jobs', max_jobs_per_owner=1)
    first = store.create('report', owner_id=1)
    context = multiprocessing.get_context('spawn')
    ready = context.Event()
    finished = context.Event()
    result = context.Queue()
    process = context.Process(target=_create_job_in_process, args=(str(store.root), ready, finished, result))
    try:
        with store._owner_capacity_lock(1):
            process.start()
            assert ready.wait(20)
            assert not finished.wait(0.25)
        process.join(5)
        assert process.exitcode == 0
        assert finished.is_set()
        assert result.get(timeout=1) == ('capacity', None)
        assert [record['job_id'] for record in store.list_for_owner(1)] == [first['job_id']]
    finally:
        if process.is_alive():
            process.terminate()
            process.join(5)


def test_owner_quotas_and_usage_are_independent(tmp_path: Path) -> None:
    store = _store(tmp_path / 'office_jobs', max_jobs_per_owner=1, max_bytes_per_owner=3)
    owner_a = store.create('report', owner_id=1)
    store.write_bytes(owner_a['job_id'], 'a.txt', b'abc', 'text/plain')

    with pytest.raises(OfficeJobCapacityError):
        store.create('chart', owner_id=1)
    with pytest.raises(OfficeJobCapacityError):
        store.write_bytes(owner_a['job_id'], 'more.txt', b'x', 'text/plain')

    owner_b = store.create('report', owner_id=2)
    store.write_bytes(owner_b['job_id'], 'b.txt', b'xyz', 'text/plain')

    assert store.usage_for_owner(1) == {'job_count': 1, 'total_bytes': 3}
    assert store.usage_for_owner(2) == {'job_count': 1, 'total_bytes': 3}


def test_unknown_owner_corruption_does_not_block_healthy_owner_and_is_quarantined(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    healthy = store.create('report', owner_id=1)
    healthy_payload = b'healthy'
    store.write_bytes(healthy['job_id'], 'healthy.txt', healthy_payload, 'text/plain')

    corrupt_id = 'f' * 32
    corrupt_dir = store.root / corrupt_id
    corrupt_dir.mkdir()
    corrupt_job_metadata = corrupt_dir / 'job.json'
    corrupt_payload_file = corrupt_dir / 'unrecoverable.bin'
    corrupt_job_metadata.write_text('{bad json', encoding='utf-8')
    corrupt_payload_file.write_bytes(b'bad')
    corrupt_payload_bytes = (
        corrupt_job_metadata.stat().st_size + corrupt_payload_file.stat().st_size
    )

    assert [record['job_id'] for record in store.list_for_owner(1)] == [healthy['job_id']]
    assert store.usage_for_owner(1) == {'job_count': 1, 'total_bytes': len(healthy_payload)}

    result = store.purge_expired()

    assert result['deleted_jobs'] == 0
    assert result['quarantined_job_ids'] == [corrupt_id]
    assert result['quarantined_bytes'] == corrupt_payload_bytes
    assert result['logical_artifact_quarantined_bytes'] == 0
    assert result['physical_quarantined_bytes'] == corrupt_payload_bytes
    assert not corrupt_dir.exists()

    quarantine_id = result['quarantined_quarantine_ids'][0]
    entry = store._quarantine_root / quarantine_id
    quarantined_physical_bytes = store._physical_size_no_follow(entry)
    inventory = store.list_quarantine()
    assert inventory['total_bytes'] == quarantined_physical_bytes
    assert len(inventory['items']) == 1
    item = inventory['items'][0]
    assert item['kind'] == 'corrupt'
    assert item['quarantine_id'] is None
    assert item['job_id'] is None
    assert item['owner_id'] is None
    assert item['size_bytes'] == quarantined_physical_bytes
    assert result['quarantine_bytes'] == quarantined_physical_bytes
    assert UUID(quarantine_id).hex == quarantine_id
    assert entry.is_dir()
    metadata = json.loads((entry / 'metadata.json').read_text(encoding='utf-8'))
    assert metadata['quarantine_id'] == quarantine_id
    assert metadata['job_id'] == corrupt_id
    assert metadata['size_bytes'] == corrupt_payload_bytes
    payload = entry / 'payload'
    assert payload.is_dir()
    assert (payload / 'job.json').read_text(encoding='utf-8') == '{bad json'
    assert (payload / 'unrecoverable.bin').read_bytes() == b'bad'


def test_attributable_corruption_fails_closed_only_for_affected_owner(tmp_path: Path) -> None:
    store = _store(tmp_path / 'office_jobs', max_jobs_per_owner=1)
    owner_a = store.create('report', owner_id=1)
    owner_a_payload = b'alpha'
    owner_a_artifact = store.write_bytes(
        owner_a['job_id'],
        'owner-a.txt',
        owner_a_payload,
        'text/plain',
    )

    owner_a_artifact.write_bytes(b'omega')
    corrupt_dir = store.job_dir(owner_a['job_id'])
    owner_a_physical_reserved_bytes = sum(
        path.stat().st_size for path in corrupt_dir.rglob('*') if path.is_file()
    )

    with pytest.raises(OfficeJobCorruptionError) as listing_error:
        store.list_for_owner(1)
    assert listing_error.value.job_ids == (owner_a['job_id'],)
    assert store.usage_for_owner(1) == {
        'job_count': 1,
        'total_bytes': owner_a_physical_reserved_bytes,
    }

    with pytest.raises(OfficeJobCapacityError):
        store.create('chart', owner_id=1)

    owner_b = store.create('report', owner_id=2)
    owner_b_payload = b'beta'
    store.write_bytes(owner_b['job_id'], 'owner-b.txt', owner_b_payload, 'text/plain')
    assert [record['job_id'] for record in store.list_for_owner(2)] == [owner_b['job_id']]
    assert store.usage_for_owner(2) == {'job_count': 1, 'total_bytes': len(owner_b_payload)}

    result = store.purge_expired()

    assert result['deleted_jobs'] == 0
    assert result['quarantined_job_ids'] == [owner_a['job_id']]
    assert result['quarantined_bytes'] == owner_a_physical_reserved_bytes
    assert result['logical_artifact_quarantined_bytes'] == len(owner_a_payload)
    assert result['physical_quarantined_bytes'] == owner_a_physical_reserved_bytes
    assert not corrupt_dir.exists()

    quarantine_id = result['quarantined_quarantine_ids'][0]
    quarantined_physical_bytes = store._physical_size_no_follow(store._quarantine_root / quarantine_id)
    inventory = store.list_quarantine()
    assert [item['kind'] for item in inventory['items']] == ['quarantine']
    assert [item['job_id'] for item in inventory['items']] == [owner_a['job_id']]
    assert [item['owner_id'] for item in inventory['items']] == [1]
    assert inventory['total_bytes'] == owner_a_physical_reserved_bytes
    assert inventory['physical_total_bytes'] == quarantined_physical_bytes
    assert result['quarantine_bytes'] == inventory['total_bytes']
    assert [record['job_id'] for record in store.list_for_owner(2)] == [owner_b['job_id']]
    assert store.usage_for_owner(2) == {'job_count': 1, 'total_bytes': len(owner_b_payload)}


@pytest.mark.parametrize(
    ('field', 'value'),
    [
        ('owner_id', 2),
        ('job_id', '0' * 32),
        ('status', 'failed'),
        ('artifacts', []),
        ('created_at', datetime.now(UTC).isoformat()),
    ],
)
def test_complete_cannot_overwrite_identity_or_lifecycle_fields(tmp_path: Path, field: str, value: object) -> None:
    store = _store(tmp_path / 'office_jobs')
    record = store.create('report', owner_id=1)

    with pytest.raises(ValueError, match='reserved fields'):
        store.complete(record['job_id'], extra={field: value})

    persisted = store.get(record['job_id'])
    assert persisted['owner_id'] == 1
    assert persisted['status'] == 'running'
    assert persisted['artifacts'] == []


def test_artifact_download_serves_only_manifest_registered_files(
    app,
    csrf_client: TestClient,
    tmp_path: Path,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        record = store.create('report', owner_id=_admin_id(app))
        store.write_bytes(record['job_id'], 'registered.txt', b'ok', 'text/plain')
        job_metadata = (store.job_dir(record['job_id']) / 'job.json').read_bytes()
        (store.job_dir(record['job_id']) / 'unregistered.txt').write_bytes(b'private')

        registered = csrf_client.get(
            f"/api/v1/office-tools/jobs/{record['job_id']}/artifacts/registered.txt"
        )
        metadata = csrf_client.get(
            f"/api/v1/office-tools/jobs/{record['job_id']}/artifacts/job.json"
        )
        unregistered = csrf_client.get(
            f"/api/v1/office-tools/jobs/{record['job_id']}/artifacts/unregistered.txt"
        )

        assert registered.status_code == 200
        assert registered.content == b'ok'
        assert metadata.status_code == 404
        assert metadata.content != job_metadata
        assert unregistered.status_code == 404
        assert unregistered.content != b'private'
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)


@pytest.mark.parametrize('operation', ['owner_delete', 'purge_expired'])
def test_artifact_read_lease_blocks_concurrent_destructive_lifecycle_operation(
    tmp_path: Path,
    operation: str,
) -> None:
    store = _store(tmp_path / 'office_jobs', retention_days=1)
    record = store.create('report', owner_id=1)
    payload = b'leased artifact bytes'
    store.write_bytes(record['job_id'], 'leased.txt', payload, 'text/plain')
    if operation == 'purge_expired':
        _set_job_timestamp(store, record['job_id'], datetime.now(UTC) - timedelta(days=2))
    lease = store.open_artifact_read_lease(record['job_id'], 'leased.txt', owner_id=1)
    started = threading.Event()
    completed = threading.Event()
    errors: list[BaseException] = []
    result: dict[str, object] = {}

    def destructive_operation() -> None:
        started.set()
        try:
            if operation == 'owner_delete':
                result['outcome'] = store.delete_for_owner_outcome(record['job_id'], 1)
            else:
                result['purge'] = store.purge_expired()
        except BaseException as exc:
            errors.append(exc)
        finally:
            completed.set()

    worker = threading.Thread(target=destructive_operation)
    worker.start()
    try:
        assert started.wait(1)
        assert not completed.wait(0.1)
        assert lease.handle.read() == payload
    finally:
        lease.close()
    worker.join(2)

    assert not worker.is_alive()
    assert errors == []
    if operation == 'owner_delete':
        outcome = result['outcome']
        assert isinstance(outcome, dict)
        assert outcome['removed'] is True
    else:
        purge = result['purge']
        assert isinstance(purge, dict)
        assert purge['deleted_job_ids'] == [record['job_id']]
    assert not (store.root / record['job_id']).exists()

def test_artifact_write_rolls_back_when_manifest_write_fails(tmp_path: Path, monkeypatch) -> None:
    store = _store(tmp_path / 'office_jobs')
    record = store.create('report', owner_id=1)

    def fail_metadata_write(_job_dir: Path, _record: dict[str, object]) -> None:
        raise OSError('metadata write failed')

    monkeypatch.setattr(store, '_write_record', fail_metadata_write)
    with pytest.raises(OSError, match='metadata write failed'):
        store.write_bytes(record['job_id'], 'result.txt', b'payload', 'text/plain')

    assert not (store.job_dir(record['job_id']) / 'result.txt').exists()
    assert store.get(record['job_id'])['artifacts'] == []


def test_bundle_is_temporary_and_deleted_after_response(app, csrf_client: TestClient, tmp_path: Path, monkeypatch) -> None:
    store = _store(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    removed_paths: list[Path] = []
    original_cleanup = store.delete_temporary_bundle_with_replay_evidence

    def record_cleanup(
        bundle_id: str,
        replay_evidence: object,
    ) -> OfficeJobDeletionOutcome:
        removed_paths.append(store._bundles_root / f'bundle-{bundle_id}.zip')
        return original_cleanup(bundle_id, replay_evidence)

    monkeypatch.setattr(store, 'delete_temporary_bundle_with_replay_evidence', record_cleanup)
    try:
        record = store.create('report', owner_id=_admin_id(app))
        store.write_bytes(record['job_id'], 'report.txt', b'contents', 'text/plain')

        response = csrf_client.get(f"/api/v1/office-tools/jobs/{record['job_id']}/bundle")

        assert response.status_code == 200
        assert removed_paths
        assert not removed_paths[0].exists()
        assert not list(store.job_dir(record['job_id']).glob('*.zip'))
        assert store.usage_for_owner(_admin_id(app))['total_bytes'] == len(b'contents')
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)

def test_temporary_bundle_fsyncs_with_writable_binary_handle(tmp_path: Path, monkeypatch) -> None:
    store = _store(tmp_path / 'office_jobs')
    record = store.create('report', owner_id=1)
    store.write_bytes(record['job_id'], 'report.txt', b'contents', 'text/plain')
    opened_bundle_modes: list[str] = []
    fsynced_bundle_descriptors: list[int] = []
    active_bundle_descriptors: set[int] = set()
    original_open = Path.open
    original_fsync = job_store_module.os.fsync

    class TrackedBundleHandle:
        def __init__(self, handle) -> None:
            self._handle = handle
            self._descriptor = handle.fileno()

        def __enter__(self):
            active_bundle_descriptors.add(self._descriptor)
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            try:
                return self._handle.__exit__(exc_type, exc_value, traceback)
            finally:
                active_bundle_descriptors.discard(self._descriptor)

        def fileno(self) -> int:
            return self._descriptor

    def track_fsync(descriptor: int) -> None:
        if descriptor in active_bundle_descriptors:
            fsynced_bundle_descriptors.append(descriptor)
        original_fsync(descriptor)

    def track_bundle_open(
        path: Path,
        mode: str = 'r',
        buffering: int = -1,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ):
        handle = original_open(path, mode, buffering, encoding, errors, newline)
        if path.parent == store._bundles_root and path.suffix == '.zip':
            opened_bundle_modes.append(mode)
            return TrackedBundleHandle(handle)
        return handle

    monkeypatch.setattr(job_store_module.os, 'fsync', track_fsync)
    monkeypatch.setattr(Path, 'open', track_bundle_open)
    bundle = store.create_temporary_bundle(record['job_id'])
    try:
        assert bundle.is_file()
        assert opened_bundle_modes == ['r+b']
        assert fsynced_bundle_descriptors
    finally:
        store.delete_temporary_bundle(bundle)


@pytest.mark.parametrize(
    ('field', 'value'),
    [
        ('office_job_retention_days', 3651),
        ('office_job_max_jobs_per_owner', -1),
        ('office_job_max_bytes_per_owner', 1024**4 + 1),
        ('office_job_min_free_disk_bytes', -1),
    ],
)
def test_settings_bound_office_job_limits_at_construction(field: str, value: int) -> None:
    with pytest.raises(ValidationError):
        Settings(**{field: value})
@pytest.mark.parametrize('owner_id', [0, -1, True, '1'])
def test_store_requires_strict_positive_integer_owner_ids(tmp_path: Path, owner_id: object) -> None:
    store = _store(tmp_path / 'office_jobs')

    with pytest.raises(ValueError, match='positive integer'):
        store.create('report', owner_id=owner_id)  # type: ignore[arg-type]
def test_corrupt_inventory_placeholders_are_sanitized_and_degrade_recovery_health(
    app,
    tmp_path: Path,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    original_app_store = app.state.office_job_store
    app.state.office_job_store = store
    app.dependency_overrides[get_office_job_store] = lambda: store
    leaked_names = (
        'quarantine-private-evidence',
        'recovery-private-evidence',
        'owner-private-evidence.json',
    )
    try:
        quarantine_evidence = store._quarantine_root / leaked_names[0]
        recovery_evidence = store._recovery_quarantine_root / leaked_names[1]
        owner_identity_evidence = store._owner_identities_root / leaked_names[2]
        quarantine_evidence.mkdir()
        (quarantine_evidence / 'payload.bin').write_bytes(b'quarantine corrupt evidence')
        recovery_evidence.mkdir()
        (recovery_evidence / 'journal.bin').write_bytes(b'recovery corrupt evidence')
        owner_identity_evidence.write_bytes(b'{invalid owner identity')

        manager_client = _office_user_client(
            app,
            'corrupt-inventory-manager',
            permissions=('office.use', 'admin.office.manage'),
        )
        quarantine = manager_client.get('/api/v1/office-tools/jobs/quarantine')
        recovery = manager_client.get('/api/v1/office-tools/jobs/recovery')

        assert quarantine.status_code == 200
        assert recovery.status_code == 200
        quarantine_item = quarantine.json()['items'][0]
        recovery_item = recovery.json()['items'][0]
        owner_item = store.list_owner_identities()['items'][0]
        for item, identifier in [
            (quarantine_item, 'quarantine_id'),
            (recovery_item, 'recovery_id'),
            (owner_item, 'job_id'),
        ]:
            assert item['kind'] == 'corrupt'
            assert item[identifier] is None
            assert item['management_token']
            assert item['physical_bytes'] >= item.get('size_bytes', 0)
            assert item['reason']
        assert recovery.json()['recovery_ids'] == []
        assert recovery.json()['management_tokens'] == [recovery_item['management_token']]
        assert recovery.json()['corrupt_entries'] == 1
        assert all(name not in json.dumps(quarantine.json()) for name in leaked_names)
        assert all(name not in json.dumps(recovery.json()) for name in leaked_names)
        assert all(name not in json.dumps(owner_item) for name in leaked_names)

        health = manager_client.get('/api/v1/health')
        assert health.status_code == 200
        assert health.json()['status'] == 'degraded'
        assert health.json()['office_job_recovery_ok'] is False
        assert (
            health.json()['office_job_unresolved_recovery_transactions'] == 1
        )
        assert 'office_recovery_ok' not in health.json()
        assert 'office_recovery_unresolved_count' not in health.json()
        assert store.recover()['malformed_recovery_evidence'] == 1
    finally:
        app.state.office_job_store = original_app_store
        app.dependency_overrides.pop(get_office_job_store, None)


@pytest.mark.parametrize(
    'kind',
    ['quarantine', 'recovery', 'owner_identity'],
)
def test_corrupt_evidence_disposition_removes_only_target_and_preserves_sibling(
    app,
    tmp_path: Path,
    kind: str,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        evidence_root = {
            'quarantine': store._quarantine_root,
            'recovery': store._recovery_quarantine_root,
            'owner_identity': store._owner_identities_root,
        }[kind]
        target = evidence_root / f'{kind}-disposition-target-private'
        sibling = evidence_root / f'{kind}-disposition-sibling-private'
        target_payload = b'target corrupt evidence with distinct byte count'
        sibling_payload = b'sibling corrupt evidence must remain byte-for-byte intact'
        if kind == 'owner_identity':
            target.write_bytes(target_payload)
            sibling.write_bytes(sibling_payload)
        else:
            target.mkdir()
            (target / 'evidence.bin').write_bytes(target_payload)
            sibling.mkdir()
            (sibling / 'evidence.bin').write_bytes(sibling_payload)

        inventory = {
            'quarantine': store.list_quarantine,
            'recovery': store.list_recovery,
            'owner_identity': store.list_owner_identities,
        }[kind]
        items_before = inventory()['items']
        assert len(items_before) == 2
        assert all(item['kind'] == 'corrupt' for item in items_before)
        target_physical_bytes = store._physical_size_no_follow(target)
        sibling_physical_bytes = store._physical_size_no_follow(sibling)
        target_item = next(
            item for item in items_before if item['physical_bytes'] == target_physical_bytes
        )
        sibling_item = next(
            item for item in items_before if item['physical_bytes'] == sibling_physical_bytes
        )
        target_token = str(target_item['management_token'])
        sibling_token = str(sibling_item['management_token'])
        sibling_snapshot = _filesystem_snapshot(sibling)
        evidence_snapshot_before = _filesystem_snapshot(evidence_root)
        expected_evidence_snapshot = {
            path: content
            for path, content in evidence_snapshot_before.items()
            if path != target.name and not path.startswith(f'{target.name}/')
        }
        evidence_root_bytes_before = store._directory_size(evidence_root)
        assert target.name in evidence_snapshot_before
        assert target_item['physical_bytes'] == target_physical_bytes
        assert sibling_item['physical_bytes'] == sibling_physical_bytes

        office_only_client = _office_user_client(app, f'{kind}-evidence-office-only')
        manage_only_client = _office_user_client(
            app,
            f'{kind}-evidence-manage-only',
            permissions=('admin.office.manage',),
        )
        manager_client = _office_user_client(
            app,
            f'{kind}-evidence-manager',
            permissions=('office.use', 'admin.office.manage'),
        )
        manager_id = _user_id(app, f'{kind}-evidence-manager')
        no_csrf_client = TestClient(app)
        login = no_csrf_client.post(
            '/api/v1/auth/login',
            json={'username': f'{kind}-evidence-manager', 'password': 'password123'},
        )
        assert login.status_code == 200

        filesystem_before_guards = _filesystem_snapshot(store.root)
        responses = [
            office_only_client.delete(f'/api/v1/office-tools/jobs/evidence/{target_token}'),
            manage_only_client.delete(f'/api/v1/office-tools/jobs/evidence/{target_token}'),
            no_csrf_client.delete(f'/api/v1/office-tools/jobs/evidence/{target_token}'),
        ]
        assert [response.status_code for response in responses] == [403, 403, 403]
        assert _filesystem_snapshot(store.root) == filesystem_before_guards
        assert inventory()['items'] == items_before
        with app.state.db.session() as session:
            guard_audits = session.scalars(
                select(AdminAuditEvent).where(
                    AdminAuditEvent.action.in_(
                        ['office_jobs.evidence.dispose.intent', 'office_jobs.evidence.dispose']
                    )
                )
            ).all()
        assert guard_audits == []

        disposed = manager_client.delete(f'/api/v1/office-tools/jobs/evidence/{target_token}')

        expected_outcome = {
            'operation': f'{kind}_corrupt_disposition',
            'target_id': target_token,
            'management_token': target_token,
            'job_id': None,
            'owner_id': None,
            'logical_bytes': 0,
            'physical_bytes': target_physical_bytes,
            'partial_bytes_removed': target_physical_bytes,
            'published': False,
            'removed': True,
            'durably_synced': True,
            **_completed_durability_fields(),
        }
        assert disposed.status_code == 200
        assert disposed.json() == {'outcome': expected_outcome}
        assert not target.exists()
        assert evidence_root_bytes_before - store._directory_size(evidence_root) == target_physical_bytes
        assert _filesystem_snapshot(evidence_root) == expected_evidence_snapshot
        assert _filesystem_snapshot(sibling) == sibling_snapshot
        items_after = inventory()['items']
        assert len(items_after) == 1
        assert items_after[0]['management_token'] == sibling_token

        with app.state.db.session() as session:
            events = session.scalars(
                select(AdminAuditEvent)
                .where(
                    AdminAuditEvent.target_id == target_token,
                    AdminAuditEvent.action.in_(
                        ['office_jobs.evidence.dispose.intent', 'office_jobs.evidence.dispose']
                    ),
                )
                .order_by(AdminAuditEvent.id)
            ).all()
        assert [(event.action, event.status, event.actor_user_id) for event in events] == [
            ('office_jobs.evidence.dispose.intent', 'intent', manager_id),
            ('office_jobs.evidence.dispose', 'success', manager_id),
        ]
        assert json.loads(events[0].metadata_json or '{}') == {'management_token': '[REDACTED]'}
        assert json.loads(events[1].metadata_json or '{}') == {
            'outcome': {**expected_outcome, 'management_token': '[REDACTED]'}
        }
        assert target.name not in disposed.text
        assert all(
            target.name not in json.dumps(json.loads(event.metadata_json or '{}'))
            for event in events
        )
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)


def test_corrupt_recovery_evidence_disposition_partial_failure_preserves_target(
    app,
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        recovery_evidence = store._recovery_quarantine_root / 'recovery-disposition-partial-private'
        recovery_evidence.mkdir()
        (recovery_evidence / 'journal.bin').write_bytes(b'recovery corrupt evidence')
        recovery_item = store.list_recovery()['items'][0]
        recovery_token = str(recovery_item['management_token'])
        recovery_snapshot = _filesystem_snapshot(recovery_evidence)
        manager_client = _office_user_client(
            app,
            'recovery-evidence-partial-manager',
            permissions=('office.use', 'admin.office.manage'),
        )
        manager_id = _user_id(app, 'recovery-evidence-partial-manager')
        partial_outcome = {
            'operation': 'recovery_corrupt_disposition',
            'target_id': recovery_token,
            'management_token': recovery_token,
            'job_id': None,
            'owner_id': None,
            'logical_bytes': 0,
            'physical_bytes': recovery_item['physical_bytes'],
            'partial_bytes_removed': 0,
            'published': False,
            'removed': False,
            'durably_synced': False,
            'durability': 'pending',
            'retry_required': True,
        }

        def fail_after_committed_intent(token: str) -> dict[str, object]:
            with app.state.db.session() as session:
                intent = session.scalar(
                    select(AdminAuditEvent).where(
                        AdminAuditEvent.target_id == token,
                        AdminAuditEvent.action == 'office_jobs.evidence.dispose.intent',
                    )
                )
            assert intent is not None
            assert intent.status == 'intent'
            assert intent.actor_user_id == manager_id
            raise OfficeJobDirectMutationError(partial_outcome, OSError('late evidence failure'))

        monkeypatch.setattr(store, 'dispose_corrupt_evidence_outcome', fail_after_committed_intent)
        partial = manager_client.delete(f'/api/v1/office-tools/jobs/evidence/{recovery_token}')

        assert partial.status_code == 500
        assert partial.json() == {
            'detail': {
                'error': 'corrupt evidence disposition partially failed',
                'outcome': {
                    key: value
                    for key, value in partial_outcome.items()
                    if value is not None
                },
            }
        }
        assert _filesystem_snapshot(recovery_evidence) == recovery_snapshot
        assert store.list_recovery()['items'] == [recovery_item]
        with app.state.db.session() as session:
            events = session.scalars(
                select(AdminAuditEvent)
                .where(
                    AdminAuditEvent.target_id == recovery_token,
                    AdminAuditEvent.action.in_(
                        ['office_jobs.evidence.dispose.intent', 'office_jobs.evidence.dispose']
                    ),
                )
                .order_by(AdminAuditEvent.id)
            ).all()
        assert [(event.action, event.status, event.actor_user_id) for event in events] == [
            ('office_jobs.evidence.dispose.intent', 'intent', manager_id),
            ('office_jobs.evidence.dispose', 'partial_failure', manager_id),
        ]
        assert json.loads(events[-1].metadata_json or '{}')['outcome'] == {
            **partial_outcome,
            'management_token': '[REDACTED]',
        }
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)


@pytest.mark.parametrize(
    ('route_token', 'store_token'),
    [
        ('not-a-valid-token', 'not-a-valid-token'),
        ('%2Foutside', '/outside'),
        ('%5Coutside', r'\outside'),
        ('..%2F..%5Coutside', r'../..\outside'),
        ('C%3A%5Coutside', r'C:\outside'),
        ('%5C%5Cserver%5Cshare', r'\\server\share'),
    ],
    ids=[
        'malformed-token',
        'encoded-separator',
        'encoded-backslash',
        'mixed-separators',
        'drive-path',
        'unc-path',
    ],
)
def test_evidence_tokens_reject_path_forms_without_audit_or_filesystem_mutation(
    app,
    tmp_path: Path,
    route_token: str,
    store_token: str,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        quarantine_evidence = store._quarantine_root / 'evidence-token-quarantine-private'
        recovery_evidence = store._recovery_quarantine_root / 'evidence-token-recovery-private'
        owner_identity_evidence = store._owner_identities_root / 'evidence-token-owner-private'
        quarantine_evidence.mkdir()
        (quarantine_evidence / 'payload.bin').write_bytes(b'quarantine evidence')
        recovery_evidence.mkdir()
        (recovery_evidence / 'journal.bin').write_bytes(b'recovery evidence')
        owner_identity_evidence.write_bytes(b'{invalid owner identity')
        inventories_before = {
            'quarantine': store.list_quarantine(),
            'recovery': store.list_recovery(),
            'owner_identity': store.list_owner_identities(),
        }
        filesystem_before = _filesystem_snapshot(store.root)
        manager_client = _office_user_client(
            app,
            'evidence-token-identifier-manager',
            permissions=('office.use', 'admin.office.manage'),
        )

        response = manager_client.delete(f'/api/v1/office-tools/jobs/evidence/{route_token}')
        assert response.status_code in {404, 422}
        with pytest.raises(FileNotFoundError):
            store.dispose_corrupt_evidence_outcome(store_token)

        assert store.list_quarantine() == inventories_before['quarantine']
        assert store.list_recovery() == inventories_before['recovery']
        assert store.list_owner_identities() == inventories_before['owner_identity']
        assert _filesystem_snapshot(store.root) == filesystem_before
        with app.state.db.session() as session:
            audits = session.scalars(
                select(AdminAuditEvent).where(
                    AdminAuditEvent.action.in_(
                        ['office_jobs.evidence.dispose.intent', 'office_jobs.evidence.dispose']
                    )
                )
            ).all()
        assert audits == []
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)


def test_direct_quarantine_late_failures_preserve_exact_outcome_in_response_and_audit(
    app,
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        manager_client = _office_user_client(
            app,
            'direct-outcome-manager',
            permissions=('office.use', 'admin.office.manage'),
        )
        owner_id = _admin_id(app)
        restore_record = store.create('report', owner_id=owner_id)
        store.write_bytes(restore_record['job_id'], 'restore.txt', b'restore payload', 'text/plain')
        restore_item = store._quarantine_corrupt_job(
            store.job_dir(restore_record['job_id']),
            'direct outcome restore fixture',
        )
        assert restore_item is not None
        delete_record = store.create('report', owner_id=owner_id)
        store.write_bytes(delete_record['job_id'], 'delete.txt', b'delete payload', 'text/plain')
        delete_item = store._quarantine_corrupt_job(
            store.job_dir(delete_record['job_id']),
            'direct outcome delete fixture',
        )
        assert delete_item is not None

        def fail_after_direct_work(entry: Path) -> None:
            raise OfficeJobDeletionError(
                {
                    'entry_id': entry.name,
                    'entry_kind': 'quarantine',
                    'parent_id': 'quarantine',
                    'physical_bytes': store._physical_size_no_follow(entry),
                    'partial_bytes_removed': 0,
                    'removed': False,
                    'durably_synced': False,
                    'durability': 'pending',
                    'retry_required': True,
                },
                OSError('late deletion durability failure'),
            )

        monkeypatch.setattr(store, '_safe_delete_quarantine_entry', fail_after_direct_work)
        restore_response = manager_client.post(
            f"/api/v1/office-tools/jobs/quarantine/{restore_item['quarantine_id']}/restore"
        )
        delete_response = manager_client.delete(
            f"/api/v1/office-tools/jobs/quarantine/{delete_item['quarantine_id']}"
        )

        assert restore_response.status_code == 500
        assert delete_response.status_code == 500
        restore_outcome = restore_response.json()['detail']['outcome']
        delete_outcome = delete_response.json()['detail']['outcome']
        assert restore_outcome['published'] is True
        assert restore_outcome['removed'] is False
        assert restore_outcome['durably_synced'] is False
        assert delete_outcome['published'] is False
        assert delete_outcome['removed'] is False
        assert delete_outcome['durably_synced'] is False
        assert delete_outcome['owner_id'] == owner_id
        assert store.get(restore_record['job_id'])['job_id'] == restore_record['job_id']

        with app.state.db.session() as session:
            events = session.scalars(
                select(AdminAuditEvent)
                .where(
                    AdminAuditEvent.action.in_(
                        ['office_jobs.quarantine.restore', 'office_jobs.quarantine.delete']
                    ),
                    AdminAuditEvent.status == 'partial_failure',
                )
                .order_by(AdminAuditEvent.id)
            ).all()
        assert [event.action for event in events] == [
            'office_jobs.quarantine.restore',
            'office_jobs.quarantine.delete',
        ]
        assert json.loads(events[0].metadata_json or '{}')['outcome'] == {
            **restore_outcome,
            'management_token': '[REDACTED]',
        }
        assert json.loads(events[1].metadata_json or '{}')['outcome'] == {
            **delete_outcome,
            'management_token': '[REDACTED]',
        }
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)
def test_worker_thread_stream_disconnect_and_read_error_release_per_job_lease(tmp_path: Path) -> None:
    store = _store(tmp_path / 'office_jobs')
    record = store.create('report', owner_id=1)
    payload = b'worker thread stream payload'
    store.write_bytes(record['job_id'], 'report.txt', payload, 'text/plain')

    lease = store.open_artifact_read_lease(record['job_id'], 'report.txt', owner_id=1)
    streamed: list[bytes] = []
    errors: list[BaseException] = []

    def disconnecting_worker() -> None:
        try:
            stream = _stream_artifact(lease)
            streamed.append(next(stream))
            stream.close()
        except BaseException as exc:
            errors.append(exc)

    worker = threading.Thread(target=disconnecting_worker)
    worker.start()
    worker.join(2)

    assert not worker.is_alive()
    assert errors == []
    assert streamed == [payload]
    assert store.delete_for_owner_outcome(record['job_id'], 1) is not None

    failed_read = store.create('report', owner_id=1)
    store.write_bytes(failed_read['job_id'], 'report.txt', payload, 'text/plain')
    failed_lease = store.open_artifact_read_lease(failed_read['job_id'], 'report.txt', owner_id=1)
    failed_lease.handle.close()
    worker_errors: list[BaseException] = []

    def failing_worker() -> None:
        try:
            list(_stream_artifact(failed_lease))
        except BaseException as exc:
            worker_errors.append(exc)

    worker = threading.Thread(target=failing_worker)
    worker.start()
    worker.join(2)

    assert not worker.is_alive()
    assert len(worker_errors) == 1
    assert isinstance(worker_errors[0], ValueError)
    assert store.delete_for_owner_outcome(failed_read['job_id'], 1) is not None


def test_stream_lease_unlock_error_is_retryable_after_worker_disconnect(tmp_path: Path, monkeypatch) -> None:
    store = _store(tmp_path / 'office_jobs')
    record = store.create('report', owner_id=1)
    store.write_bytes(record['job_id'], 'report.txt', b'lease payload', 'text/plain')
    lease = store.open_artifact_read_lease(record['job_id'], 'report.txt', owner_id=1)
    original_unlock = OfficeJobStore._unlock_file
    unlock_attempts = 0
    worker_errors: list[BaseException] = []

    def fail_first_unlock(handle) -> None:
        nonlocal unlock_attempts
        unlock_attempts += 1
        if unlock_attempts == 1:
            raise OSError('injected stream lease unlock failure')
        original_unlock(handle)

    monkeypatch.setattr(OfficeJobStore, '_unlock_file', staticmethod(fail_first_unlock))

    def disconnecting_worker() -> None:
        try:
            stream = _stream_artifact(lease)
            next(stream)
            stream.close()
        except BaseException as exc:
            worker_errors.append(exc)

    worker = threading.Thread(target=disconnecting_worker)
    worker.start()
    worker.join(2)

    assert not worker.is_alive()
    assert len(worker_errors) == 1
    assert isinstance(worker_errors[0], OSError)
    assert len(lease.teardown_errors) == 1
    assert unlock_attempts == 1
    assert store.delete_for_owner_outcome(record['job_id'], 1) is not None


def test_owner_delete_retries_sidecar_cleanup_after_unlink_directory_fsync_failure(
    app,
    csrf_client: TestClient,
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        owner_id = _admin_id(app)
        record = store.create('report', owner_id=owner_id)
        job_id = record['job_id']
        original_fsync_directory = store._fsync_directory
        failed_once = False

        def fail_sidecar_fsync(path: Path) -> None:
            nonlocal failed_once
            if Path(path) == store._owner_identities_root and not failed_once:
                failed_once = True
                raise OSError('injected sidecar fsync failure after unlink')
            original_fsync_directory(path)

        monkeypatch.setattr(store, '_fsync_directory', fail_sidecar_fsync)
        partial = csrf_client.delete(f'/api/v1/office-tools/jobs/{job_id}')

        assert partial.status_code == 500
        assert partial.json()['detail']['outcome']['owner_identity_removed'] is True
        assert partial.json()['detail']['outcome']['owner_identity_durably_synced'] is False
        assert partial.json()['detail']['outcome']['owner_identity_durability'] == 'pending'
        assert partial.json()['detail']['outcome']['retry_required'] is True
        assert not store._owner_identity_path(job_id).exists()
        assert store._owner_deletion_tombstone_path(job_id).exists()

        monkeypatch.setattr(store, '_fsync_directory', original_fsync_directory)
        retry = csrf_client.delete(f'/api/v1/office-tools/jobs/{job_id}')

        assert retry.status_code == 200
        assert retry.json()['outcome']['retry_required'] is False
        tombstone = json.loads(store._owner_deletion_tombstone_path(job_id).read_text(encoding='utf-8'))
        assert tombstone['state'] == 'completed'
        assert tombstone['outcome'] == retry.json()['outcome']
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)


def test_owner_and_purge_lock_teardown_failures_preserve_typed_retryable_results(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    owner_record = store.create('report', owner_id=1)
    original_unlock = store._unlock_file
    unlock_attempts = 0

    def fail_owner_lock_teardown(handle) -> None:
        nonlocal unlock_attempts
        unlock_attempts += 1
        if unlock_attempts == 2:
            raise OSError('injected owner lock teardown failure')
        original_unlock(handle)

    monkeypatch.setattr(store, '_unlock_file', fail_owner_lock_teardown)
    with pytest.raises(OfficeJobOwnerDeletionError) as owner_error:
        store.delete_for_owner_outcome(owner_record['job_id'], 1)

    assert owner_error.value.outcome['removed'] is True
    assert owner_error.value.outcome['owner_identity_durably_synced'] is _completed_durability_fields()['durably_synced']
    assert owner_error.value.outcome['retry_required'] is True
    monkeypatch.setattr(store, '_unlock_file', original_unlock)
    assert store.delete_for_owner_outcome(owner_record['job_id'], 1) is not None

    purge_record = store.create('report', owner_id=1)
    _set_job_timestamp(store, purge_record['job_id'], datetime.now(UTC) - timedelta(days=366))
    unlock_attempts = 0

    def fail_maintenance_lock_teardown(handle) -> None:
        nonlocal unlock_attempts
        unlock_attempts += 1
        if unlock_attempts == 3:
            raise OSError('injected maintenance lock teardown failure')
        original_unlock(handle)

    monkeypatch.setattr(store, '_unlock_file', fail_maintenance_lock_teardown)
    with pytest.raises(OfficeJobPurgeError) as purge_error:
        store.purge_expired()

    assert purge_error.value.partial_result['deleted_job_ids'] == [purge_record['job_id']]


@pytest.mark.parametrize('entry_kind', ['stale_bundle', 'orphan_temp'])
def test_purge_records_typed_file_deletion_outcome_when_cleanup_fsync_fails(
    tmp_path: Path,
    monkeypatch,
    entry_kind: str,
) -> None:
    store = _store(tmp_path / 'office_jobs', retention_days=365)
    record = store.create('report', owner_id=1)
    original_fsync_directory = store._fsync_directory
    if entry_kind == 'stale_bundle':
        entry = store._bundles_root / f'bundle-{"f" * 32}.zip'
        entry.write_bytes(b'stale bundle')
        old = datetime.now(UTC) - timedelta(hours=2)
        os.utime(entry, (old.timestamp(), old.timestamp()))
        expected_parent = store._bundles_root
    else:
        entry = store.job_dir(record['job_id']) / '.office_tmp_orphan'
        entry.write_bytes(b'orphan temporary artifact')
        expected_parent = store.job_dir(record['job_id'])

    def fail_entry_parent_fsync(path: Path) -> None:
        if Path(path) == expected_parent:
            raise OSError('injected cleanup fsync failure')
        original_fsync_directory(path)

    monkeypatch.setattr(store, '_fsync_directory', fail_entry_parent_fsync)
    with pytest.raises(OfficeJobPurgeError) as purge_error:
        store.purge_expired()

    partial = purge_error.value.partial_result
    outcome = next(item for item in partial['partial_deletion_outcomes'] if item['entry_id'] == entry.name)
    assert outcome['entry_kind'] == entry_kind
    assert outcome['parent_id'] == (
        'bundles' if entry_kind == 'stale_bundle' else record['job_id']
    )
    assert outcome['removed'] is True
    assert outcome['durably_synced'] is False
    assert outcome['physical_bytes'] == len(
        b'stale bundle' if entry_kind == 'stale_bundle' else b'orphan temporary artifact'
    )


def test_owner_delete_audit_commit_failure_keeps_outbox_and_reconciles_on_retry(
    app,
    csrf_client: TestClient,
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        owner_id = _admin_id(app)
        record = store.create('report', owner_id=owner_id)
        job_id = record['job_id']
        original_record_admin_audit = jobs_api.record_admin_audit

        def fail_result_audit(db, **kwargs):
            if kwargs['action'] == 'office_jobs.owner_delete':
                raise OSError('injected owner result audit commit failure')
            return original_record_admin_audit(db, **kwargs)

        monkeypatch.setattr(jobs_api, 'record_admin_audit', fail_result_audit)
        failed = csrf_client.delete(f'/api/v1/office-tools/jobs/{job_id}')

        assert failed.status_code == 500
        persistence = failed.json()['detail']['audit_persistence']
        assert persistence['state'] == 'result_ready'
        pending_paths = list(store._pending_results_root.glob('*.json'))
        assert len(pending_paths) == 1
        pending_result_id = json.loads(pending_paths[0].read_text(encoding='utf-8'))['pending_result_id']
        assert not (store.root / job_id).exists()

        monkeypatch.setattr(jobs_api, 'record_admin_audit', original_record_admin_audit)
        retry = csrf_client.delete(f'/api/v1/office-tools/jobs/{job_id}')

        assert retry.status_code == 200
        assert retry.json()['outcome']['retry_required'] is False
        assert not list(store._pending_results_root.glob('*.json'))
        with app.state.db.session() as session:
            result_events = session.scalars(
                select(AdminAuditEvent)
                .where(
                    AdminAuditEvent.action == 'office_jobs.owner_delete',
                    AdminAuditEvent.target_id == job_id,
                )
                .order_by(AdminAuditEvent.id)
            ).all()
        assert [(event.status, event.actor_user_id) for event in result_events] == [
            ('success', owner_id),
            ('success', owner_id),
        ]
        reconciled_events = [
            event
            for event in result_events
            if event.idempotency_key == f'{pending_result_id}:result'
        ]
        assert [(event.status, event.actor_user_id) for event in reconciled_events] == [
            ('success', owner_id),
        ]
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)


def test_owner_delete_requires_office_use_permission_before_audit_or_mutation(app, tmp_path: Path) -> None:
    store = _store(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        client = _office_user_client(app, 'delete-without-office-use', permissions=())
        owner_id = _user_id(app, 'delete-without-office-use')
        record = store.create('report', owner_id=owner_id)

        response = client.delete(f"/api/v1/office-tools/jobs/{record['job_id']}")

        assert response.status_code == 403
        assert store.get(record['job_id'])['job_id'] == record['job_id']
        with app.state.db.session() as session:
            audits = session.scalars(
                select(AdminAuditEvent).where(AdminAuditEvent.target_id == record['job_id'])
            ).all()
        assert audits == []
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)
def test_owner_final_marker_fsync_failure_retains_completed_result_for_concurrent_retries(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    record = store.create('report', owner_id=1)
    job_id = record['job_id']
    original_fsync_directory = store._fsync_directory
    marker_path = store._owner_deletion_tombstone_path(job_id)
    final_marker_fsync_failed = False

    def fail_final_marker_fsync(path: Path) -> None:
        nonlocal final_marker_fsync_failed
        if Path(path) == store._owner_deletion_tombstones_root:
            marker = store._read_owner_deletion_tombstone_record(job_id)
            if marker is not None and marker['state'] == 'completed' and not final_marker_fsync_failed:
                final_marker_fsync_failed = True
                raise OSError('injected completed tombstone fsync failure')
        original_fsync_directory(path)

    monkeypatch.setattr(store, '_fsync_directory', fail_final_marker_fsync)
    with pytest.raises(OfficeJobOwnerDeletionError) as partial_error:
        store.delete_for_owner_outcome(job_id, 1)

    assert partial_error.value.outcome['removed'] is True
    assert final_marker_fsync_failed
    marker = json.loads(marker_path.read_text(encoding='utf-8'))
    assert marker['state'] == 'completed'
    assert marker['gc_pending'] is False
    assert marker['audit_acknowledged_at'] is None
    assert marker['outcome']['retry_required'] is False
    accounting = store.storage_accounting()
    assert accounting['owner_deletion_tombstone_entries'] == 1
    assert accounting['owner_deletion_tombstone_physical_bytes'] == marker_path.stat().st_size

    monkeypatch.setattr(store, '_fsync_directory', original_fsync_directory)
    barrier = threading.Barrier(2)
    results: list[dict[str, object]] = []
    errors: list[BaseException] = []

    def retry() -> None:
        try:
            barrier.wait()
            outcome = store.delete_for_owner_outcome(job_id, 1)
            assert outcome is not None
            results.append(outcome)
        except BaseException as exc:
            errors.append(exc)

    first = threading.Thread(target=retry)
    second = threading.Thread(target=retry)
    first.start()
    second.start()
    first.join(2)
    second.join(2)

    assert not first.is_alive()
    assert not second.is_alive()
    assert errors == []
    assert results == [marker['outcome'], marker['outcome']]
    assert not (store.root / job_id).exists()


def test_pending_result_chunks_large_purge_receipt_and_preserves_provenance(tmp_path: Path) -> None:
    store = _store(tmp_path / 'office_jobs')
    pending_result_id = store.prepare_pending_result(
        actor_id=1,
        action='office_jobs.purge_expired',
        target_type='office_job',
        target_id='retention',
        intent={'retention_days': 365},
        request_provenance={'request_id': 'purge-receipt-test', 'source': 'unit-test'},
    )
    store.begin_pending_result_mutation(
        pending_result_id,
        action='office_jobs.purge_expired',
        target_type='office_job',
        target_id='retention',
    )
    metadata = {
        'partial_result': {
            'deleted_job_ids': [f'{index:032x}' for index in range(10_000)],
            'failed_job_ids': [],
        }
    }

    recorded = store.record_pending_result(
        pending_result_id,
        metadata=metadata,
        audit_status='success',
    )
    stored = json.loads(store._pending_result_path(pending_result_id).read_text(encoding='utf-8'))

    assert recorded['audit_metadata'] == metadata
    assert recorded['request_provenance'] == {
        'request_id': 'purge-receipt-test',
        'source': 'unit-test',
    }
    assert recorded['phase'] == 2
    assert recorded['mutation_boundary'] == 'result_durable'
    assert stored['result_chunk_count'] > 0
    assert len(store._pending_result_path(pending_result_id).read_bytes()) <= (
        job_store_module._PENDING_RESULT_MAX_BYTES
    )
    assert store.list_pending_results_for_actor(1)[0]['audit_metadata'] == metadata
    accounting = store.storage_accounting()
    assert accounting['pending_result_entries'] == stored['result_chunk_count'] + 1
    assert accounting['pending_result_physical_bytes'] > 0


def test_pending_result_chunk_write_failure_is_typed_and_leaves_unresolved_receipt(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    pending_result_id = store.prepare_pending_result(
        actor_id=1,
        action='office_jobs.purge_expired',
        target_type='office_job',
        target_id='retention',
        intent={'retention_days': 365},
    )
    store.begin_pending_result_mutation(
        pending_result_id,
        action='office_jobs.purge_expired',
        target_type='office_job',
        target_id='retention',
    )
    metadata = {'deleted_job_ids': [f'{index:032x}' for index in range(10_000)]}

    def fail_chunk_write(_target: Path, _data: bytes) -> None:
        raise OSError('injected pending result chunk write failure')

    monkeypatch.setattr(store, '_write_bytes_durable', fail_chunk_write)
    with pytest.raises(OfficeJobPendingResultError) as receipt_error:
        store.record_pending_result(
            pending_result_id,
            metadata=metadata,
            audit_status='success',
        )

    assert receipt_error.value.pending_result_id == pending_result_id
    assert receipt_error.value.outcome == metadata
    unresolved = store._read_pending_result(pending_result_id)
    assert unresolved['state'] == 'prepared'
    assert unresolved['phase'] == 1
    assert unresolved['outcome_state'] == 'unresolved'
    assert unresolved['mutation_boundary'] == 'mutation_started'
@pytest.mark.parametrize(
    ('operation', 'expected_field'),
    [
        ('recovery_delete', 'removed'),
        ('quarantine_restore', 'published'),
        ('quarantine_delete', 'removed'),
        ('evidence_disposition', 'removed'),
    ],
)
def test_direct_mutation_maintenance_teardown_preserves_actual_outcome(
    tmp_path: Path,
    monkeypatch,
    operation: str,
    expected_field: str,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    if operation == 'recovery_delete':
        store._preserve_unresolved_recovery(None, f'create-{"a" * 32}', 'teardown fixture')
        recovery_id = str(store.list_recovery()['items'][0]['recovery_id'])
        mutate = lambda: store.delete_recovery_outcome(recovery_id)
    elif operation in {'quarantine_restore', 'quarantine_delete'}:
        record = store.create('report', owner_id=1)
        store.write_bytes(record['job_id'], 'result.txt', b'payload', 'text/plain')
        metadata = store._quarantine_corrupt_job(store.job_dir(record['job_id']), 'teardown fixture')
        assert metadata is not None
        quarantine_id = str(metadata['quarantine_id'])
        if operation == 'quarantine_restore':
            mutate = lambda: store.restore_quarantine_outcome(quarantine_id)
        else:
            mutate = lambda: store.delete_quarantine_outcome(quarantine_id)
    else:
        evidence = store._recovery_quarantine_root / 'teardown-private-evidence'
        evidence.mkdir()
        (evidence / 'journal.bin').write_bytes(b'corrupt evidence')
        token = str(store.list_recovery()['items'][0]['management_token'])
        mutate = lambda: store.dispose_corrupt_evidence_outcome(token)

    original_unlock = store._unlock_file

    def fail_maintenance_unlock(handle) -> None:
        if Path(handle.name).name == 'maintenance.lock':
            raise OSError('injected maintenance lock teardown failure')
        original_unlock(handle)

    monkeypatch.setattr(store, '_unlock_file', fail_maintenance_unlock)
    with pytest.raises(OfficeJobDirectMutationError) as mutation_error:
        mutate()

    assert mutation_error.value.outcome[expected_field] is True
def test_chunked_pending_receipt_acknowledgement_retains_header_and_retries_removed_chunks(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    pending_result_id = store.prepare_pending_result(
        actor_id=1,
        action='office_jobs.purge_expired',
        target_type='office_job',
        target_id='retention',
        intent={'retention_days': 365},
    )
    store.begin_pending_result_mutation(
        pending_result_id,
        action='office_jobs.purge_expired',
        target_type='office_job',
        target_id='retention',
    )
    store.record_pending_result(
        pending_result_id,
        metadata={'deleted_job_ids': [f'{index:032x}' for index in range(10_000)]},
        audit_status='success',
    )
    store.mark_pending_result_audited(pending_result_id)
    original_fsync_directory = store._fsync_directory
    failed_once = False
    first_chunk = store._pending_result_chunk_path(pending_result_id, 0)

    def fail_after_chunk_unlink_before_parent_fsync(path: Path) -> None:
        nonlocal failed_once
        if (
            Path(path) == store._pending_results_root
            and not first_chunk.exists()
            and not failed_once
        ):
            failed_once = True
            raise OSError('injected chunk parent fsync failure after unlink')
        original_fsync_directory(path)

    monkeypatch.setattr(store, '_fsync_directory', fail_after_chunk_unlink_before_parent_fsync)
    with pytest.raises(OfficeJobDeletionError):
        store.acknowledge_pending_result(pending_result_id)

    stored = json.loads(store._pending_result_path(pending_result_id).read_text(encoding='utf-8'))
    assert stored['state'] == 'audit_persisted'
    assert stored['cleanup_phase'] == 'chunks_pending'
    assert not store._pending_result_chunk_path(pending_result_id, 0).exists()

    assert failed_once
    monkeypatch.setattr(store, '_fsync_directory', original_fsync_directory)
    restarted = _store(store.root)
    restarted.acknowledge_pending_result(pending_result_id)

    assert store.storage_accounting()['pending_result_entries'] == 0
    assert store.storage_accounting()['pending_result_physical_bytes'] == 0


def test_chunked_pending_receipt_header_unlink_fsync_failure_leaves_zero_accounting(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    pending_result_id = store.prepare_pending_result(
        actor_id=1,
        action='office_jobs.purge_expired',
        target_type='office_job',
        target_id='retention',
        intent={'retention_days': 365},
    )
    store.begin_pending_result_mutation(
        pending_result_id,
        action='office_jobs.purge_expired',
        target_type='office_job',
        target_id='retention',
    )
    store.record_pending_result(
        pending_result_id,
        metadata={'deleted_job_ids': [f'{index:032x}' for index in range(10_000)]},
        audit_status='success',
    )
    store.mark_pending_result_audited(pending_result_id)
    original_fsync_directory = store._fsync_directory
    failed_once = False
    header = store._pending_result_path(pending_result_id)

    def fail_after_header_unlink_before_parent_fsync(path: Path) -> None:
        nonlocal failed_once
        if (
            Path(path) == store._pending_results_root
            and not header.exists()
            and not failed_once
        ):
            failed_once = True
            raise OSError('injected receipt header parent fsync failure after unlink')
        original_fsync_directory(path)

    monkeypatch.setattr(store, '_fsync_directory', fail_after_header_unlink_before_parent_fsync)
    with pytest.raises(OfficeJobDeletionError):
        store.acknowledge_pending_result(pending_result_id)

    assert failed_once
    restarted = _store(store.root)
    assert not restarted._pending_result_path(pending_result_id).exists()
    assert not any(restarted._pending_results_root.glob(f'{pending_result_id}.chunk-*'))
    assert restarted.storage_accounting()['pending_result_entries'] == 0


def test_pending_receipt_rejects_incoherent_acknowledgement_before_mutation(tmp_path: Path) -> None:
    store = _store(tmp_path / 'office_jobs')
    pending_result_id = store.prepare_pending_result(
        actor_id=1,
        action='office_jobs.purge_expired',
        target_type='office_job',
        target_id='retention',
        intent={'retention_days': 365},
    )

    with pytest.raises(ValueError, match='not durably audit acknowledged'):
        store.acknowledge_pending_result(pending_result_id)

    assert store._pending_result_path(pending_result_id).exists()


def test_owner_delete_persists_baseline_and_retries_after_damaged_partial_rmtree(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    record = store.create('report', owner_id=1)
    store.write_bytes(record['job_id'], 'result.txt', b'owner deletion payload', 'text/plain')
    job_id = record['job_id']
    job_dir = store.job_dir(job_id)
    physical_bytes = store._physical_size_no_follow(job_dir)
    job_json = job_dir / 'job.json'
    job_json_bytes = job_json.stat().st_size
    original_delete = store._safe_delete_job_dir

    def damage_metadata_after_baseline(path: Path):
        tombstone = store._read_owner_deletion_tombstone_record(job_id)
        assert tombstone is not None
        assert tombstone['state'] == 'deletion_pending'
        assert tombstone['outcome']['logical_bytes'] == len(b'owner deletion payload')
        assert tombstone['outcome']['physical_bytes'] == physical_bytes
        job_json.unlink()
        raise OfficeJobDeletionError(
            {
                'entry_id': job_id,
                'entry_kind': 'job',
                'parent_id': job_id,
                'physical_bytes': physical_bytes,
                'partial_bytes_removed': job_json_bytes,
                'removed': False,
                'durably_synced': False,
                'durability': 'pending',
                'retry_required': True,
            },
            OSError('injected partial rmtree failure'),
        )

    monkeypatch.setattr(store, '_safe_delete_job_dir', damage_metadata_after_baseline)
    with pytest.raises(OfficeJobOwnerDeletionError) as partial_error:
        store.delete_for_owner_outcome(job_id, 1)

    assert partial_error.value.outcome['removed'] is False
    assert partial_error.value.outcome['partial_bytes_removed'] >= job_json_bytes
    tombstone = store._read_owner_deletion_tombstone_record(job_id)
    assert tombstone is not None
    assert tombstone['state'] == 'deletion_pending'

    monkeypatch.setattr(store, '_safe_delete_job_dir', original_delete)
    retried = store.delete_for_owner_outcome(job_id, 1)
    assert retried is not None
    assert retried['physical_bytes'] == physical_bytes
    assert retried['partial_bytes_removed'] == physical_bytes
    assert retried['removed'] is True
    assert retried['retry_required'] is False


def test_quarantine_hash_mismatch_cannot_restore_but_has_attributed_delete_outcome(tmp_path: Path) -> None:
    store = _store(tmp_path / 'office_jobs')
    record = store.create('report', owner_id=1)
    store.write_bytes(record['job_id'], 'result.txt', b'payload', 'text/plain')
    quarantined = store._quarantine_corrupt_job(store.job_dir(record['job_id']), 'hash mismatch fixture')
    assert quarantined is not None
    quarantine_id = str(quarantined['quarantine_id'])
    entry = store._quarantine_root / quarantine_id
    (entry / 'payload' / 'result.txt').write_bytes(b'changed')

    with pytest.raises(OfficeJobCorruptionError):
        store.restore_quarantine_outcome(quarantine_id)

    physical_bytes = store._physical_size_no_follow(entry)
    deleted = store.delete_quarantine_outcome(quarantine_id)
    assert deleted == {
        'operation': 'quarantine_delete',
        'target_id': quarantine_id,
        'management_token': None,
        'job_id': record['job_id'],
        'owner_id': 1,
        'logical_bytes': len(b'payload'),
        'physical_bytes': physical_bytes,
        'partial_bytes_removed': physical_bytes,
        'published': False,
        'removed': True,
        'durably_synced': True,
        **_completed_durability_fields(),
    }


def test_restore_owner_capacity_lock_teardown_preserves_published_removal_outcome(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    record = store.create('report', owner_id=1)
    store.write_bytes(record['job_id'], 'result.txt', b'payload', 'text/plain')
    quarantined = store._quarantine_corrupt_job(store.job_dir(record['job_id']), 'owner lock teardown')
    assert quarantined is not None
    quarantine_id = str(quarantined['quarantine_id'])
    original_unlock = store._unlock_file

    def fail_owner_lock_teardown(handle) -> None:
        if Path(handle.name).name == 'owner-1.lock':
            raise OSError('injected owner capacity lock teardown failure')
        original_unlock(handle)

    monkeypatch.setattr(store, '_unlock_file', fail_owner_lock_teardown)
    with pytest.raises(OfficeJobDirectMutationError) as mutation_error:
        store.restore_quarantine_outcome(quarantine_id)

    monkeypatch.setattr(store, '_unlock_file', original_unlock)
    assert mutation_error.value.outcome['published'] is True
    assert mutation_error.value.outcome['removed'] is True
    for field, expected in _completed_durability_fields().items():
        assert mutation_error.value.outcome[field] == expected
    assert store.get(record['job_id'])['job_id'] == record['job_id']


def test_artifact_lease_acquisition_unwind_closes_handles_after_double_teardown_faults(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class FailingCloseHandle:
        def __init__(self, name: str) -> None:
            self.name = name
            self.closed = False

        def close(self) -> None:
            self.closed = True
            raise OSError(f'injected close failure: {self.name}')

    store = _store(tmp_path / 'office_jobs')
    record = store.create('report', owner_id=1)
    store.write_bytes(record['job_id'], 'result.txt', b'payload', 'text/plain')
    artifact_handle = FailingCloseHandle('artifact')
    lease_lock_handle = FailingCloseHandle('lease')
    original_unlock = store._unlock_file

    def fail_owner_and_lease_unlock(handle) -> None:
        if handle is lease_lock_handle:
            raise OSError('injected lease unlock failure')
        if Path(handle.name).name == 'owner-1.lock':
            raise OSError('injected owner lock teardown failure')
        original_unlock(handle)

    monkeypatch.setattr(store, '_open_file_no_follow', lambda _path: artifact_handle)
    monkeypatch.setattr(store, '_artifact_handle_matches', lambda _handle, _artifact: True)
    monkeypatch.setattr(store, '_acquire_job_read_lease_lock', lambda _job_id: lease_lock_handle)
    monkeypatch.setattr(store, '_unlock_file', fail_owner_and_lease_unlock)
    with pytest.raises(OSError) as acquisition_error:
        store.open_artifact_read_lease(record['job_id'], 'result.txt', owner_id=1)

    assert artifact_handle.closed is True
    assert lease_lock_handle.closed is True
    assert len(getattr(acquisition_error.value, '__notes__', ())) == 3


class _WindowsLockFailure(OSError):
    def __init__(self, winerror: int) -> None:
        super().__init__(job_store_module.errno.EACCES, 'injected windows lock failure')
        self._test_winerror = winerror

    @property
    def winerror(self) -> int:
        return self._test_winerror


class _WindowsLockHandle:
    def __init__(self) -> None:
        self.position = 0
        self.written = b''

    def seek(self, offset: int, whence: int = 0) -> None:
        self.position = offset

    def tell(self) -> int:
        return len(self.written)

    def write(self, value: bytes) -> None:
        self.written += value

    def flush(self) -> None:
        pass

    def fileno(self) -> int:
        return 123


def test_windows_lock_retries_only_contention_and_succeeds_deterministically(monkeypatch) -> None:
    attempts: list[int] = []
    sleeps: list[float] = []
    outcomes: list[BaseException | None] = [
        _WindowsLockFailure(32),
        _WindowsLockFailure(33),
        None,
    ]

    def locking(_fd: int, _operation: int, _length: int) -> None:
        attempts.append(1)
        outcome = outcomes.pop(0)
        if outcome is not None:
            raise outcome

    monkeypatch.setattr(job_store_module.os, 'name', 'nt')
    monkeypatch.setitem(
        sys.modules,
        'msvcrt',
        SimpleNamespace(LK_NBLCK=1, LK_UNLCK=2, locking=locking),
    )
    monkeypatch.setattr(job_store_module, '_WINDOWS_LOCK_RETRY_ATTEMPTS', 3)
    monkeypatch.setattr(job_store_module, '_WINDOWS_LOCK_RETRY_SECONDS', 0.25)
    monkeypatch.setattr(job_store_module.time, 'sleep', sleeps.append)

    OfficeJobStore._lock_file(_WindowsLockHandle())

    assert len(attempts) == 3
    assert sleeps == [0.25, 0.25]


def test_windows_lock_contention_timeout_is_deterministic(monkeypatch) -> None:
    attempts: list[int] = []
    sleeps: list[float] = []

    def locking(_fd: int, _operation: int, _length: int) -> None:
        attempts.append(1)
        raise _WindowsLockFailure(32)

    monkeypatch.setattr(job_store_module.os, 'name', 'nt')
    monkeypatch.setitem(
        sys.modules,
        'msvcrt',
        SimpleNamespace(LK_NBLCK=1, LK_UNLCK=2, locking=locking),
    )
    monkeypatch.setattr(job_store_module, '_WINDOWS_LOCK_RETRY_ATTEMPTS', 3)
    monkeypatch.setattr(job_store_module, '_WINDOWS_LOCK_RETRY_SECONDS', 0.25)
    monkeypatch.setattr(job_store_module.time, 'sleep', sleeps.append)

    with pytest.raises(TimeoutError) as timeout_error:
        OfficeJobStore._lock_file(_WindowsLockHandle())

    assert isinstance(timeout_error.value.__cause__, _WindowsLockFailure)
    assert len(attempts) == 3
    assert sleeps == [0.25, 0.25]


def test_windows_lock_permanent_error_is_not_retried(monkeypatch) -> None:
    attempts: list[int] = []
    sleeps: list[float] = []

    def locking(_fd: int, _operation: int, _length: int) -> None:
        attempts.append(1)
        raise _WindowsLockFailure(5)

    monkeypatch.setattr(job_store_module.os, 'name', 'nt')
    monkeypatch.setitem(
        sys.modules,
        'msvcrt',
        SimpleNamespace(LK_NBLCK=1, LK_UNLCK=2, locking=locking),
    )
    monkeypatch.setattr(job_store_module, '_WINDOWS_LOCK_RETRY_ATTEMPTS', 3)
    monkeypatch.setattr(job_store_module, '_WINDOWS_LOCK_RETRY_SECONDS', 0.25)
    monkeypatch.setattr(job_store_module.time, 'sleep', sleeps.append)

    with pytest.raises(_WindowsLockFailure):
        OfficeJobStore._lock_file(_WindowsLockHandle())

    assert len(attempts) == 1
    assert sleeps == []


def test_owner_tombstone_collection_requires_audited_receipt_and_retention(tmp_path: Path) -> None:
    store = _store(tmp_path / 'office_jobs', retention_days=0)
    record = store.create('report', owner_id=1)
    job_id = record['job_id']
    assert store.delete_for_owner_outcome(job_id, 1) is not None
    tombstone_path = store._owner_deletion_tombstone_path(job_id)
    tombstone = store._read_owner_deletion_tombstone_record(job_id)
    assert tombstone is not None
    assert tombstone['gc_pending'] is False

    pending_result_id = store.prepare_pending_result(
        actor_id=1,
        action='office_jobs.owner_delete',
        target_type='office_job',
        target_id=job_id,
        intent={'job_id': job_id, 'owner_id': 1},
    )
    store.begin_pending_result_mutation(
        pending_result_id,
        action='office_jobs.owner_delete',
        target_type='office_job',
        target_id=job_id,
    )
    store.record_pending_result(
        pending_result_id,
        metadata={'outcome': {'operation': 'owner_delete', 'job_id': job_id}},
        audit_status='success',
    )
    store.mark_pending_result_audited(pending_result_id)
    store.acknowledge_pending_result(pending_result_id)

    tombstone = store._read_owner_deletion_tombstone_record(job_id)
    assert tombstone is not None
    assert tombstone['gc_pending'] is True
    assert isinstance(tombstone['audit_acknowledged_at'], str)
    tombstone['audit_acknowledged_at'] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    store._write_owner_deletion_tombstone(job_id, tombstone)

    store.recover()

    assert not tombstone_path.exists()
def test_pending_receipt_and_owner_tombstone_reject_malformed_state_tuples(tmp_path: Path) -> None:
    store = _store(tmp_path / 'office_jobs')
    pending_result_id = store.prepare_pending_result(
        actor_id=1,
        action='office_jobs.purge_expired',
        target_type='office_job',
        target_id='retention',
        intent={'retention_days': 365},
    )
    receipt_path = store._pending_result_path(pending_result_id)
    malformed_receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    malformed_receipt['phase'] = 2
    receipt_path.write_text(json.dumps(malformed_receipt), encoding='utf-8')

    with pytest.raises(OfficeJobCorruptionError):
        store._read_pending_result(pending_result_id)

    record = store.create('report', owner_id=1)
    assert store.delete_for_owner_outcome(record['job_id'], 1) is not None
    tombstone_path = store._owner_deletion_tombstone_path(record['job_id'])
    malformed_tombstone = json.loads(tombstone_path.read_text(encoding='utf-8'))
    malformed_tombstone['gc_pending'] = True
    tombstone_path.write_text(json.dumps(malformed_tombstone), encoding='utf-8')

    with pytest.raises(OfficeJobCorruptionError):
        store.recover()
def test_legacy_pending_receipt_upgrades_to_phase_one_v2_before_reconciliation(
    app,
    tmp_path: Path,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    owner_id = _admin_id(app)
    pending_result_id = store.prepare_pending_result(
        actor_id=owner_id,
        action='office_jobs.purge_expired',
        target_type='office_job',
        target_id='retention',
        intent={'retention_days': 365},
    )
    receipt_path = store._pending_result_path(pending_result_id)
    legacy = json.loads(receipt_path.read_text(encoding='utf-8'))
    legacy.update({'version': 1, 'updated_at': legacy['created_at']})
    for field in (
        'request_provenance',
        'outcome_state',
        'mutation_boundary',
        'phase',
        'cleanup_phase',
        'result_chunk_count',
        'result_sha256',
    ):
        legacy.pop(field)
    receipt_path.write_text(json.dumps(legacy), encoding='utf-8')

    upgraded = store._read_pending_result(pending_result_id)

    assert upgraded['version'] == 2
    assert upgraded['phase'] == 1
    assert upgraded['mutation_boundary'] == 'mutation_started'
    assert upgraded['request_provenance'] == {
        'actor_id': owner_id,
        'actor_username': None,
        'actor_role': None,
        'method': None,
        'path': None,
        'ip_address': None,
        'user_agent': None,
        'request_id': None,
        'request_available': False,
    }
    persisted = json.loads(receipt_path.read_text(encoding='utf-8'))
    assert persisted['version'] == 2
    assert persisted['phase'] == 1
    with app.state.db.session() as session:
        actor = session.get(User, owner_id)
        assert actor is not None
        with pytest.raises(jobs_api.OfficeJobAuditPersistenceError):
            jobs_api._reconcile_pending_result_audits(store, session, actor=actor)
    assert store._read_pending_result(pending_result_id)['state'] == 'prepared'


def test_phase_one_owner_delete_receipt_restarts_from_tombstone_and_acks_once(
    app,
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    owner_id = _admin_id(app)
    record = store.create('report', owner_id=owner_id)
    pending_result_id = store.prepare_pending_result(
        actor_id=owner_id,
        action='office_jobs.owner_delete',
        target_type='office_job',
        target_id=record['job_id'],
        intent={'job_id': record['job_id'], 'owner_id': owner_id},
    )
    store.begin_pending_result_mutation(
        pending_result_id,
        action='office_jobs.owner_delete',
        target_type='office_job',
        target_id=record['job_id'],
    )
    outcome = store.delete_for_owner_outcome(record['job_id'], owner_id)
    assert outcome is not None
    assert outcome['retry_required'] is False
    def fail_result_write(_pending_result_id: str, _record: dict[str, object]) -> None:
        raise OSError('injected phase-one result write failure')

    monkeypatch.setattr(store, '_write_pending_result_durable', fail_result_write)
    with pytest.raises(OfficeJobPendingResultError):
        store.record_pending_result(
            pending_result_id,
            metadata={'intent': {'job_id': record['job_id'], 'owner_id': owner_id}, 'outcome': outcome},
            audit_status='success',
        )
    assert store._pending_result_path(pending_result_id).exists()

    restarted = _store(store.root)
    with app.state.db.session() as session:
        actor = session.get(User, owner_id)
        assert actor is not None
        jobs_api._reconcile_pending_result_audits(restarted, session, actor=actor)
        events = session.scalars(
            select(AdminAuditEvent)
            .where(AdminAuditEvent.idempotency_key == f'{pending_result_id}:result')
            .order_by(AdminAuditEvent.id)
        ).all()

    assert not restarted._pending_result_path(pending_result_id).exists()
    assert [(event.action, event.status) for event in events] == [
        ('office_jobs.owner_delete', 'success'),
    ]
    assert not (restarted.root / record['job_id']).exists()


def test_bundle_cleanup_replaces_stale_result_ready_receipt_with_later_deletion(
    app,
    tmp_path: Path,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    owner_id = _admin_id(app)
    record = store.create('report', owner_id=owner_id)
    store.write_bytes(record['job_id'], 'report.txt', b'contents', 'text/plain')
    bundle_id = 'b' * 32
    target_id = f'bundle-{bundle_id}.zip'
    intent = {'job_id': record['job_id'], 'bundle_id': bundle_id, 'bundle_name': target_id}
    pending_result_id = store.prepare_pending_result(
        actor_id=owner_id,
        action='office_jobs.bundle.cleanup',
        target_type='office_job_bundle',
        target_id=target_id,
        intent=intent,
    )
    store.begin_pending_result_mutation(
        pending_result_id,
        action='office_jobs.bundle.cleanup',
        target_type='office_job_bundle',
        target_id=target_id,
    )
    stale_outcome = {
        'entry_id': target_id,
        'entry_kind': 'temporary_bundle',
        'parent_id': 'bundles',
        'physical_bytes': 4096,
        'partial_bytes_removed': 128,
        'removed': False,
        'durably_synced': False,
        'durability': 'pending',
        'retry_required': True,
    }
    store.record_pending_result(
        pending_result_id,
        metadata={'intent': intent, 'outcome': stale_outcome},
        audit_status='partial_failure',
    )
    bundle = store.create_temporary_bundle(record['job_id'], bundle_id=bundle_id)
    pending = store.list_pending_results_for_actor(owner_id)[0]

    with app.state.db.session() as session:
        jobs_api._replay_temporary_bundle_cleanup(
            store,
            session,
            pending=pending,
            receipt_state=jobs_api._receipt_state_from_record(pending),
            provenance=dict(pending['request_provenance']),
            metadata=dict(pending['audit_metadata']),
            action=str(pending['action']),
            target_type=str(pending['target_type']),
            target_id=str(pending['target_id']),
            intent=dict(pending['intent']),
        )
        event = session.scalar(
            select(AdminAuditEvent).where(
                AdminAuditEvent.idempotency_key == f'{pending_result_id}:result'
            )
        )

    assert not bundle.exists()
    assert not store._pending_result_path(pending_result_id).exists()
    assert event is not None
    merged_outcome = json.loads(event.metadata_json or '{}')['outcome']
    assert merged_outcome['removed'] is True
    for field, expected in _completed_durability_fields().items():
        assert merged_outcome[field] == expected
    assert merged_outcome['physical_bytes'] >= stale_outcome['physical_bytes']
    assert merged_outcome['partial_bytes_removed'] == merged_outcome['physical_bytes']


def test_purge_root_fsync_failure_retains_sidecar_evidence_until_restart_recovery(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = _store(tmp_path / 'office_jobs', retention_days=1)
    record = store.create('report', owner_id=1)
    _set_job_timestamp(store, record['job_id'], datetime.now(UTC) - timedelta(days=2))
    original_fsync_directory = store._fsync_directory
    failed_once = False

    def fail_deleted_job_root_sync(path: Path) -> None:
        nonlocal failed_once
        if Path(path) == store.root and not (store.root / record['job_id']).exists() and not failed_once:
            failed_once = True
            raise OSError('injected purge root fsync failure')
        original_fsync_directory(path)

    monkeypatch.setattr(store, '_fsync_directory', fail_deleted_job_root_sync)
    with pytest.raises(OfficeJobPurgeError) as purge_error:
        store.purge_expired()

    assert purge_error.value.partial_result['partial_deletion_outcomes'][0]['removed'] is True
    assert store._owner_identity_path(record['job_id']).exists()
    assert store._owner_deletion_tombstone_path(record['job_id']).exists()

    monkeypatch.setattr(store, '_fsync_directory', original_fsync_directory)
    restarted = _store(store.root)
    restarted.recover()

    assert not restarted._owner_identity_path(record['job_id']).exists()
    assert not restarted._owner_deletion_tombstone_path(record['job_id']).exists()
@pytest.mark.parametrize('failure_boundary', ['mark_pending_result_audited', 'acknowledge_pending_result'])
def test_owner_delete_audit_commit_before_receipt_ack_replays_idempotently(
    app,
    csrf_client: TestClient,
    tmp_path: Path,
    monkeypatch,
    failure_boundary: str,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        owner_id = _admin_id(app)
        record = store.create('report', owner_id=owner_id)
        original = getattr(store, failure_boundary)

        def fail_after_audit_commit(_pending_result_id: str):
            raise OSError(f'injected {failure_boundary} failure after audit commit')

        monkeypatch.setattr(store, failure_boundary, fail_after_audit_commit)
        failed = csrf_client.delete(f"/api/v1/office-tools/jobs/{record['job_id']}")

        assert failed.status_code == 500
        detail = failed.json()['detail']
        assert detail['unresolved'] is False
        assert detail['audit_persistence']['state'] == 'audit_persisted'
        assert detail['audit_persistence']['retry_required'] is True
        assert detail['audit_persistence']['outcome_known'] is True
        assert detail['outcome']['removed'] is True
        pending_result_id = detail['audit_persistence']['pending_result_id']
        with app.state.db.session() as session:
            committed = session.scalars(
                select(AdminAuditEvent).where(
                    AdminAuditEvent.idempotency_key == f'{pending_result_id}:result'
                )
            ).all()
        assert len(committed) == 1

        monkeypatch.setattr(store, failure_boundary, original)
        restarted = _store(store.root)
        with app.state.db.session() as session:
            actor = session.get(User, owner_id)
            assert actor is not None
            jobs_api._reconcile_pending_result_audits(restarted, session, actor=actor)
            replayed = session.scalars(
                select(AdminAuditEvent).where(
                    AdminAuditEvent.idempotency_key == f'{pending_result_id}:result'
                )
            ).all()

        assert not restarted._pending_result_path(pending_result_id).exists()
        assert len(replayed) == 1
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)


@pytest.mark.parametrize(
    'operation',
    ['quarantine_restore', 'quarantine_delete', 'recovery_delete', 'evidence_disposition'],
)
def test_direct_removed_unsynced_receipts_reconcile_after_restart(
    app,
    tmp_path: Path,
    monkeypatch,
    operation: str,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        manager = _office_user_client(
            app,
            f'direct-durability-{operation}',
            permissions=('office.use', 'admin.office.manage'),
        )
        manager_id = _user_id(app, f'direct-durability-{operation}')
        job_id: str | None = None
        if operation in {'quarantine_restore', 'quarantine_delete'}:
            record = store.create('report', owner_id=manager_id)
            job_id = record['job_id']
            store.write_bytes(job_id, 'result.txt', b'direct durability payload', 'text/plain')
            quarantined = store._quarantine_corrupt_job(
                store.job_dir(job_id),
                f'{operation} durability fixture',
            )
            assert quarantined is not None
            target_id = str(quarantined['quarantine_id'])
            entry = store._quarantine_root / target_id
            parent = store._quarantine_root
            if operation == 'quarantine_restore':
                response = lambda: manager.post(
                    f'/api/v1/office-tools/jobs/quarantine/{target_id}/restore'
                )
            else:
                response = lambda: manager.delete(
                    f'/api/v1/office-tools/jobs/quarantine/{target_id}'
                )
        elif operation == 'recovery_delete':
            recovery = _preserve_recovery_entry(store, 'd')
            target_id = str(recovery['recovery_id'])
            entry = store._recovery_quarantine_root / target_id
            parent = store._recovery_quarantine_root
            response = lambda: manager.delete(f'/api/v1/office-tools/jobs/recovery/{target_id}')
        else:
            entry = store._recovery_quarantine_root / 'restart-corrupt-evidence'
            entry.mkdir()
            (entry / 'journal.bin').write_bytes(b'corrupt evidence payload')
            evidence = next(
                item
                for item in store.list_recovery()['items']
                if item['kind'] == 'corrupt' and item['reason'] is not None
            )
            target_id = str(evidence['management_token'])
            parent = store._recovery_quarantine_root
            response = lambda: manager.delete(f'/api/v1/office-tools/jobs/evidence/{target_id}')

        original_fsync_directory = store._fsync_directory
        failed_once = False

        def fail_after_removal_before_parent_fsync(path: Path) -> None:
            nonlocal failed_once
            if Path(path) == parent and not entry.exists() and not failed_once:
                failed_once = True
                raise OSError('injected direct parent fsync failure after removal')
            original_fsync_directory(path)

        monkeypatch.setattr(store, '_fsync_directory', fail_after_removal_before_parent_fsync)
        failed = response()

        assert failed.status_code == 500
        outcome = failed.json()['detail']['outcome']
        assert outcome['removed'] is True
        assert outcome['durably_synced'] is False
        assert failed_once
        pending_paths = list(store._pending_results_root.glob('*.json'))
        assert len(pending_paths) == 1
        pending_result_id = json.loads(pending_paths[0].read_text(encoding='utf-8'))['pending_result_id']
        assert store._read_pending_result(pending_result_id)['state'] == 'audit_persisted'

        monkeypatch.setattr(store, '_fsync_directory', original_fsync_directory)
        restarted = _store(store.root)
        with app.state.db.session() as session:
            actor = session.get(User, manager_id)
            assert actor is not None
            jobs_api._reconcile_pending_result_audits(restarted, session, actor=actor)
            events = session.scalars(
                select(AdminAuditEvent).where(
                    AdminAuditEvent.idempotency_key == f'{pending_result_id}:result'
                )
            ).all()

        assert not entry.exists()
        assert not restarted._pending_result_path(pending_result_id).exists()
        assert len(events) == 1
        if operation == 'quarantine_delete':
            assert job_id is not None
            assert not restarted._owner_identity_path(job_id).exists()
            assert not restarted._owner_deletion_tombstone_path(job_id).exists()
        if operation == 'quarantine_restore':
            assert job_id is not None
            assert restarted._owner_identity_path(job_id).exists()
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)
@pytest.mark.parametrize(
    ('action', 'operation'),
    [
        ('office_jobs.recovery.delete', 'recovery_delete'),
        ('office_jobs.quarantine.restore', 'quarantine_restore'),
        ('office_jobs.quarantine.delete', 'quarantine_delete'),
        ('office_jobs.evidence.dispose', 'evidence_disposition'),
    ],
)
def test_phase_one_direct_receipts_replay_exact_evidence_after_restart(
    app,
    tmp_path: Path,
    action: str,
    operation: str,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    actor_id = _admin_id(app)
    if operation in {'quarantine_restore', 'quarantine_delete'}:
        record = store.create('report', owner_id=actor_id)
        store.write_bytes(record['job_id'], 'result.txt', b'phase one replay', 'text/plain')
        quarantine = store._quarantine_corrupt_job(store.job_dir(record['job_id']), 'phase one replay')
        assert quarantine is not None
        target_id = str(quarantine['quarantine_id'])
        evidence = store.direct_mutation_replay_evidence(operation, target_id)
        target_type = 'office_job_quarantine'
        if operation == 'quarantine_restore':
            normal_outcome = store.restore_quarantine_outcome(target_id)
        else:
            normal_outcome = store.delete_quarantine_outcome(target_id)
    elif operation == 'recovery_delete':
        recovery = _preserve_recovery_entry(store, 'f')
        target_id = str(recovery['recovery_id'])
        evidence = store.direct_mutation_replay_evidence(operation, target_id)
        target_type = 'office_job_recovery'
        normal_outcome = store.delete_recovery_outcome(target_id)
    else:
        entry = store._recovery_quarantine_root / 'phase-one-corrupt-evidence'
        entry.mkdir()
        (entry / 'journal.bin').write_bytes(b'phase one corrupt replay')
        corrupt = next(item for item in store.list_recovery()['items'] if item['kind'] == 'corrupt')
        target_id = str(corrupt['management_token'])
        evidence = store.corrupt_evidence_replay_evidence(target_id)
        target_type = 'office_job_corrupt_evidence'
        normal_outcome = store.dispose_corrupt_evidence_outcome(target_id)

    pending_result_id = store.prepare_pending_result(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        intent={'_replay_evidence': evidence},
    )
    store.begin_pending_result_mutation(
        pending_result_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
    )
    restarted = _store(store.root)
    pending = restarted.list_pending_results_for_actor(actor_id)[0]
    with app.state.db.session() as session:
        jobs_api._phase_one_nonbundle_recovery(
            restarted,
            session,
            pending=pending,
            receipt_state=jobs_api._receipt_state_from_record(pending),
            provenance=dict(pending['request_provenance']),
            metadata={},
            action=action,
            target_type=target_type,
            target_id=target_id,
            intent=dict(pending['intent']),
        )
        event = session.scalar(
            select(AdminAuditEvent).where(
                AdminAuditEvent.idempotency_key == f'{pending_result_id}:result'
            )
        )

    assert event is not None
    assert event.status == 'success'
    assert not restarted._pending_result_path(pending_result_id).exists()
    metadata = json.loads(event.metadata_json or '{}')
    expected_audit_outcome = {**normal_outcome, 'management_token': '[REDACTED]'}
    assert metadata['outcome'] == expected_audit_outcome


def test_phase_one_quarantine_restore_replacement_stays_unresolved_without_success_audit(
    app,
    tmp_path: Path,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    actor_id = _admin_id(app)
    record = store.create('report', owner_id=actor_id)
    original_payload = b'phase one replay'
    store.write_bytes(record['job_id'], 'result.txt', original_payload, 'text/plain')
    quarantine = store._quarantine_corrupt_job(store.job_dir(record['job_id']), 'phase one replay')
    assert quarantine is not None
    target_id = str(quarantine['quarantine_id'])
    evidence = store.direct_mutation_replay_evidence('quarantine_restore', target_id)
    pending_result_id = store.prepare_pending_result(
        actor_id=actor_id,
        action='office_jobs.quarantine.restore',
        target_type='office_job_quarantine',
        target_id=target_id,
        intent={'_replay_evidence': evidence},
    )
    store.begin_pending_result_mutation(
        pending_result_id,
        action='office_jobs.quarantine.restore',
        target_type='office_job_quarantine',
        target_id=target_id,
    )
    store.restore_quarantine_outcome(target_id)

    job_dir = store.job_dir(record['job_id'])
    replacement_dir = tmp_path / 'replacement-job'
    shutil.copytree(job_dir, replacement_dir)
    shutil.rmtree(job_dir)
    shutil.copytree(replacement_dir, job_dir)
    replacement_payload = b'replaced phase one'
    artifact_path = job_dir / 'result.txt'
    artifact_path.write_bytes(replacement_payload)
    replacement_record_path = job_dir / 'job.json'
    replacement_record = json.loads(replacement_record_path.read_text(encoding='utf-8'))
    replacement_record['artifacts'][0]['size_bytes'] = len(replacement_payload)
    replacement_record['artifacts'][0]['sha256'] = hashlib.sha256(replacement_payload).hexdigest()
    replacement_record_path.write_text(json.dumps(replacement_record), encoding='utf-8')

    restarted = _store(store.root)
    pending = restarted.list_pending_results_for_actor(actor_id)[0]
    with app.state.db.session() as session:
        with pytest.raises(jobs_api.OfficeJobAuditPersistenceError) as persistence_error:
            jobs_api._phase_one_nonbundle_recovery(
                restarted,
                session,
                pending=pending,
                receipt_state=jobs_api._receipt_state_from_record(pending),
                provenance=dict(pending['request_provenance']),
                metadata={},
                action='office_jobs.quarantine.restore',
                target_type='office_job_quarantine',
                target_id=target_id,
                intent=dict(pending['intent']),
            )
        success_events = session.scalars(
            select(AdminAuditEvent).where(
                AdminAuditEvent.idempotency_key == f'{pending_result_id}:result',
                AdminAuditEvent.status == 'success',
            )
        ).all()

    assert persistence_error.value.state.state == 'mutation_started'
    assert persistence_error.value.state.outcome_known is False
    assert success_events == []
    assert restarted._pending_result_path(pending_result_id).exists()
    unresolved = restarted._read_pending_result(pending_result_id)
    assert unresolved['state'] == 'prepared'
    assert unresolved['phase'] == 1
    assert restarted.artifact_path(record['job_id'], 'result.txt').read_bytes() == replacement_payload

def test_windows_unsupported_directory_fsync_is_not_reported_durable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    recovery = _preserve_recovery_entry(store, 'a')
    target_id = str(recovery['recovery_id'])

    def unsupported_directory_open(_path: Path, _flags: int) -> int:
        error = OSError('directory fsync unsupported')
        error.winerror = 5  # type: ignore[attr-defined]
        raise error

    monkeypatch.setattr(job_store_module.os, 'name', 'nt')
    monkeypatch.setattr(job_store_module.os, 'open', unsupported_directory_open)
    outcome = store.delete_recovery_outcome(target_id)

    assert outcome['removed'] is True
    assert outcome['durably_synced'] is False
    assert outcome['durability'] == 'platform_best_effort'
    assert outcome['retry_required'] is False
    assert jobs_api._outcome_requires_durability_replay(outcome) is False


def test_phase_one_owner_delete_partial_outcome_is_audited_exactly(
    app,
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    owner_id = _admin_id(app)
    record = store.create('report', owner_id=owner_id)
    pending_result_id = store.prepare_pending_result(
        actor_id=owner_id,
        action='office_jobs.owner_delete',
        target_type='office_job',
        target_id=record['job_id'],
        intent={'job_id': record['job_id'], 'owner_id': owner_id},
    )
    store.begin_pending_result_mutation(
        pending_result_id,
        action='office_jobs.owner_delete',
        target_type='office_job',
        target_id=record['job_id'],
    )
    store._ensure_owner_deletion_tombstone(record['job_id'], owner_id)
    outcome = store._owner_deletion_baseline(
        record['job_id'],
        owner_id,
        logical_bytes=0,
        physical_bytes=0,
    )

    def fail_with_known_partial(_job_id: str, _owner_id: int):
        raise OfficeJobOwnerDeletionError(outcome, OSError('injected phase-one owner partial'))

    monkeypatch.setattr(store, 'delete_for_owner_outcome', fail_with_known_partial)
    pending = store.list_pending_results_for_actor(owner_id)[0]
    with app.state.db.session() as session:
        actor = session.get(User, owner_id)
        assert actor is not None
        jobs_api._phase_one_nonbundle_recovery(
            store,
            session,
            pending=pending,
            receipt_state=jobs_api._receipt_state_from_record(pending),
            provenance=dict(pending['request_provenance']),
            metadata={},
            action=str(pending['action']),
            target_type=str(pending['target_type']),
            target_id=str(pending['target_id']),
            intent=dict(pending['intent']),
        )
        event = session.scalar(
            select(AdminAuditEvent).where(
                AdminAuditEvent.idempotency_key == f'{pending_result_id}:result'
            )
        )

    assert event is not None
    assert event.status == 'partial_failure'
    assert json.loads(event.metadata_json or '{}')['outcome'] == outcome
    assert not store._pending_result_path(pending_result_id).exists()


def test_phase_one_owner_partial_result_write_failure_stays_mutation_started(
    app,
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    owner_id = _admin_id(app)
    record = store.create('report', owner_id=owner_id)
    pending_result_id = store.prepare_pending_result(
        actor_id=owner_id,
        action='office_jobs.owner_delete',
        target_type='office_job',
        target_id=record['job_id'],
        intent={'job_id': record['job_id'], 'owner_id': owner_id},
    )
    store.begin_pending_result_mutation(
        pending_result_id,
        action='office_jobs.owner_delete',
        target_type='office_job',
        target_id=record['job_id'],
    )
    store._ensure_owner_deletion_tombstone(record['job_id'], owner_id)
    outcome = store._owner_deletion_baseline(
        record['job_id'],
        owner_id,
        logical_bytes=0,
        physical_bytes=0,
    )

    def fail_with_known_partial(_job_id: str, _owner_id: int):
        raise OfficeJobOwnerDeletionError(outcome, OSError('injected phase-one owner partial'))

    def fail_result_write(_pending_result_id: str, _record: dict[str, object]) -> None:
        raise OSError('injected phase-one owner result write failure')

    monkeypatch.setattr(store, 'delete_for_owner_outcome', fail_with_known_partial)
    monkeypatch.setattr(store, '_write_pending_result_durable', fail_result_write)
    pending = store.list_pending_results_for_actor(owner_id)[0]
    with app.state.db.session() as session:
        actor = session.get(User, owner_id)
        assert actor is not None
        with pytest.raises(jobs_api.OfficeJobAuditPersistenceError) as persistence_error:
            jobs_api._phase_one_nonbundle_recovery(
                store,
                session,
                pending=pending,
                receipt_state=jobs_api._receipt_state_from_record(pending),
                provenance=dict(pending['request_provenance']),
                metadata={},
                action=str(pending['action']),
                target_type=str(pending['target_type']),
                target_id=str(pending['target_id']),
                intent=dict(pending['intent']),
            )

    assert persistence_error.value.state.state == 'mutation_started'
    assert persistence_error.value.state.outcome_known is True
    assert persistence_error.value.metadata == {
        'error': 'office job deletion partially failed',
        'intent': {'job_id': record['job_id'], 'owner_id': owner_id},
        'outcome': outcome,
    }
    unresolved = store._read_pending_result(pending_result_id)
    assert unresolved['state'] == 'prepared'
    assert unresolved['phase'] == 1
    assert unresolved['mutation_boundary'] == 'mutation_started'
@pytest.mark.parametrize(
    'operation',
    ['quarantine_restore', 'quarantine_delete', 'recovery_delete', 'evidence_disposition'],
)
def test_direct_replay_redeletes_only_exact_resurrected_evidence(
    tmp_path: Path,
    monkeypatch,
    operation: str,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    if operation in {'quarantine_restore', 'quarantine_delete'}:
        record = store.create('report', owner_id=1)
        store.write_bytes(record['job_id'], 'result.txt', b'replay payload', 'text/plain')
        quarantine = store._quarantine_corrupt_job(store.job_dir(record['job_id']), 'replay fixture')
        assert quarantine is not None
        target_id = str(quarantine['quarantine_id'])
        entry = store._quarantine_root / target_id
        evidence = store.direct_mutation_replay_evidence(operation, target_id)
        if operation == 'quarantine_restore':
            mutate = lambda: store.restore_quarantine_outcome(target_id)
        else:
            mutate = lambda: store.delete_quarantine_outcome(target_id)
    elif operation == 'recovery_delete':
        recovery = _preserve_recovery_entry(store, 'e')
        target_id = str(recovery['recovery_id'])
        entry = store._recovery_quarantine_root / target_id
        evidence = store.direct_mutation_replay_evidence(operation, target_id)
        mutate = lambda: store.delete_recovery_outcome(target_id)
    else:
        entry = store._recovery_quarantine_root / 'replay-corrupt-evidence'
        entry.mkdir()
        (entry / 'journal.bin').write_bytes(b'corrupt replay payload')
        token = str(store.list_recovery()['items'][0]['management_token'])
        evidence = store.corrupt_evidence_replay_evidence(token)
        mutate = lambda: store.dispose_corrupt_evidence_outcome(token)

    backup = tmp_path / f'{operation}-backup'
    shutil.copytree(entry, backup)
    original_fsync_directory = store._fsync_directory
    failed_once = False

    def fail_after_unlink_before_parent_fsync(path: Path) -> None:
        nonlocal failed_once
        if Path(path) == entry.parent and not entry.exists() and not failed_once:
            failed_once = True
            raise OSError('injected direct replay parent fsync failure')
        original_fsync_directory(path)

    monkeypatch.setattr(store, '_fsync_directory', fail_after_unlink_before_parent_fsync)
    with pytest.raises(OfficeJobDirectMutationError) as mutation_error:
        mutate()
    monkeypatch.setattr(store, '_fsync_directory', original_fsync_directory)

    outcome = mutation_error.value.outcome
    assert failed_once
    assert outcome['removed'] is True
    assert outcome['durably_synced'] is False

    shutil.copytree(backup, entry)
    restarted = _store(store.root)
    restarted.reconcile_direct_mutation_durability(outcome, evidence)
    assert not entry.exists()

    shutil.copytree(backup, entry)
    changed = next(path for path in entry.rglob('*') if path.is_file())
    changed.write_bytes(changed.read_bytes() + b'-replacement')
    with pytest.raises(OfficeJobCorruptionError):
        restarted.reconcile_direct_mutation_durability(outcome, evidence)
    assert entry.exists()


def test_purge_orphan_temp_replay_accepts_absence_with_valid_job_parent(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    record = store.create('report', owner_id=1)
    store.write_bytes(record['job_id'], 'result.txt', b'payload', 'text/plain')
    job_dir = store.job_dir(record['job_id'])
    entry = job_dir / '.office_tmp_absent_replay'
    entry.write_bytes(b'temporary replay payload')
    identity = store._replay_entry_identity(entry)
    evidence = {
        'scope': 'job_temp',
        'name': entry.name,
        'operation': 'purge_orphan_temp',
        'identity': identity,
        'signature': identity,
        'parent_identity': store._job_parent_replay_identity(job_dir),
        'job_id': record['job_id'],
        'entry_kind': 'orphan_temp',
        'parent_id': record['job_id'],
    }
    outcome = store._safe_delete_managed_file(
        entry,
        job_dir,
        entry.name,
        entry_kind='orphan_temp',
        parent_id=record['job_id'],
    )

    restarted = _store(store.root)
    restarted.reconcile_purge_partial_durability(
        {
            'partial_deletion_outcomes': [
                {**outcome, 'durably_synced': False, 'durability': 'pending', 'retry_required': True},
            ]
        },
        [evidence],
    )

    assert not entry.exists()
    assert restarted.get(record['job_id'])['job_id'] == record['job_id']


def test_purge_orphan_temp_replay_rejects_replaced_job_parent(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    record = store.create('report', owner_id=1)
    store.write_bytes(record['job_id'], 'result.txt', b'payload', 'text/plain')
    job_dir = store.job_dir(record['job_id'])
    entry = job_dir / '.office_tmp_replaced_parent'
    entry.write_bytes(b'temporary replay payload')
    identity = store._replay_entry_identity(entry)
    evidence = {
        'scope': 'job_temp',
        'name': entry.name,
        'operation': 'purge_orphan_temp',
        'identity': identity,
        'signature': identity,
        'parent_identity': store._job_parent_replay_identity(job_dir),
        'job_id': record['job_id'],
        'entry_kind': 'orphan_temp',
        'parent_id': record['job_id'],
    }
    outcome = store._safe_delete_managed_file(
        entry,
        job_dir,
        entry.name,
        entry_kind='orphan_temp',
        parent_id=record['job_id'],
    )
    replacement = store.create('report', owner_id=1)
    replacement_dir = store.job_dir(replacement['job_id'])
    replacement_record = dict(replacement)
    shutil.rmtree(replacement_dir)
    shutil.rmtree(job_dir)
    job_dir.mkdir()
    (job_dir / 'job.json').write_text(
        json.dumps({**replacement_record, 'job_id': record['job_id']}),
        encoding='utf-8',
    )
    (job_dir / 'result.txt').write_bytes(b'replacement payload')

    with pytest.raises(OfficeJobCorruptionError):
        store.reconcile_purge_partial_durability(
            {'partial_deletion_outcomes': [{**outcome, 'durably_synced': False, 'durability': 'pending', 'retry_required': True}]},
            [evidence],
        )

@pytest.mark.parametrize('target_kind', ['job', 'quarantine', 'bundle', 'bundle_temp', 'temporary'])
def test_purge_replay_redeletes_only_exact_resurrected_target(
    tmp_path: Path,
    target_kind: str,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    record = store.create('report', owner_id=1)
    store.write_bytes(record['job_id'], 'result.txt', b'purge replay payload', 'text/plain')
    job_dir = store.job_dir(record['job_id'])
    if target_kind == 'job':
        entry = job_dir
        evidence = store._replay_evidence(
            scope='job',
            entry=entry,
            operation='purge_expired',
            job_id=record['job_id'],
            owner_id=1,
        )
        delete = lambda: store._safe_delete_job_dir(entry)
    elif target_kind == 'quarantine':
        quarantine = store._quarantine_corrupt_job(job_dir, 'purge replay fixture')
        assert quarantine is not None
        entry = store._quarantine_root / str(quarantine['quarantine_id'])
        evidence = store._replay_evidence(
            scope='quarantine',
            entry=entry,
            operation='purge_expired_quarantine',
            job_id=record['job_id'],
            owner_id=1,
        )
        delete = lambda: store._safe_delete_quarantine_entry(entry)
    elif target_kind == 'bundle':
        entry = store.create_temporary_bundle(record['job_id'], bundle_id='a' * 32)
        evidence = store._replay_evidence(
            scope='bundles',
            entry=entry,
            operation='purge_stale_bundle',
        )
        delete = lambda: store._safe_delete_managed_file(
            entry,
            store._bundles_root,
            entry.name,
            entry_kind='stale_bundle',
            parent_id='bundles',
        )
    elif target_kind == 'bundle_temp':
        entry = store._bundles_root / '.office_tmp_bundle_replay'
        entry.write_bytes(b'temporary bundle replay payload')
        evidence = store._replay_evidence(
            scope='bundles',
            entry=entry,
            operation='purge_orphan_temp',
        )
        delete = lambda: store._safe_delete_managed_file(
            entry,
            store._bundles_root,
            entry.name,
            entry_kind='orphan_temp',
            parent_id='bundles',
        )
    else:
        entry = job_dir / '.office_tmp_replay'
        entry.write_bytes(b'temporary replay payload')
        identity = store._replay_entry_identity(entry)
        evidence = {
            'scope': 'job_temp',
            'name': entry.name,
            'operation': 'purge_orphan_temp',
            'identity': identity,
            'signature': identity,
            'parent_identity': store._job_parent_replay_identity(job_dir),
            'job_id': record['job_id'],
        }
        delete = lambda: store._safe_delete_managed_file(
            entry,
            job_dir,
            entry.name,
            entry_kind='orphan_temp',
            parent_id=record['job_id'],
        )

    backup = tmp_path / f'{target_kind}-backup'
    if entry.is_dir():
        shutil.copytree(entry, backup)
    else:
        shutil.copy2(entry, backup)
    outcome = delete()
    replay_outcome = {**outcome, 'durably_synced': False, 'durability': 'pending', 'retry_required': True}
    replay_item = {
        **evidence,
        'entry_kind': outcome['entry_kind'],
        'parent_id': outcome['parent_id'],
    }
    if target_kind == 'job':
        replay_item.update(
            {
                'source_parent': 'root',
                'source_id': outcome['entry_id'],
                'source_operation': 'purge_expired',
            }
        )
    elif target_kind == 'quarantine':
        replay_item.update(
            {
                'source_parent': 'quarantine',
                'source_id': outcome['entry_id'],
                'source_operation': 'purge_expired_quarantine',
            }
        )
    replay_evidence = [replay_item]

    if backup.is_dir():
        shutil.copytree(backup, entry)
    else:
        entry.write_bytes(backup.read_bytes())
    restarted = _store(store.root)
    wrong_operation = 'purge_orphan_temp' if target_kind == 'job' else 'purge_expired'
    with pytest.raises(ValueError):
        restarted.reconcile_purge_partial_durability(
            {'partial_deletion_outcomes': [replay_outcome]},
            [{**replay_item, 'operation': wrong_operation}],
        )
    assert entry.exists()
    restarted.reconcile_purge_partial_durability(
        {'partial_deletion_outcomes': [replay_outcome]},
        replay_evidence,
    )
    assert not entry.exists()

    if backup.is_dir():
        shutil.copytree(backup, entry)
        changed = next(path for path in entry.rglob('*') if path.is_file())
        changed.write_bytes(changed.read_bytes() + b'-replacement')
    else:
        entry.write_bytes(backup.read_bytes() + b'-replacement')
    with pytest.raises(OfficeJobCorruptionError):
        _store(store.root).reconcile_purge_partial_durability(
            {'partial_deletion_outcomes': [replay_outcome]},
            replay_evidence,
        )
    assert entry.exists()
def test_direct_replay_rejects_swapped_target_and_scope_before_cleanup(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    first = _preserve_recovery_entry(store, 'f')
    second = _preserve_recovery_entry(store, 'e')
    first_id = str(first['recovery_id'])
    second_id = str(second['recovery_id'])
    first_entry = store._recovery_quarantine_root / first_id
    second_entry = store._recovery_quarantine_root / second_id
    first_evidence = store.direct_mutation_replay_evidence('recovery_delete', first_id)
    second_evidence = store.direct_mutation_replay_evidence('recovery_delete', second_id)
    outcome = {
        'operation': 'recovery_delete',
        'target_id': first_id,
        'removed': True,
        'durably_synced': False,
        'durability': 'pending',
        'retry_required': True,
    }

    restarted = _store(store.root)
    with pytest.raises(ValueError):
        restarted.reconcile_direct_mutation_durability(outcome, second_evidence)
    assert first_entry.exists()
    assert second_entry.exists()
    with pytest.raises(ValueError):
        restarted.reconcile_direct_mutation_durability(
            outcome,
            first_evidence,
            receipt_target_id=second_id,
        )
    assert first_entry.exists()

    wrong_scope = {**first_evidence, 'scope': 'quarantine'}
    with pytest.raises(ValueError):
        restarted.reconcile_direct_mutation_durability(outcome, wrong_scope)
    assert first_entry.exists()


def test_bundle_cleanup_replay_redeletes_only_matching_resurrected_bundle(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    record = store.create('report', owner_id=1)
    store.write_bytes(record['job_id'], 'report.txt', b'bundle replay payload', 'text/plain')
    bundle_id = 'c' * 32
    target_id = f'bundle-{bundle_id}.zip'
    intent = {
        'job_id': record['job_id'],
        'bundle_id': bundle_id,
        'bundle_name': target_id,
    }
    pending_result_id = store.prepare_pending_result(
        actor_id=1,
        action='office_jobs.bundle.cleanup',
        target_type='office_job_bundle',
        target_id=target_id,
        intent=intent,
    )
    store.begin_pending_result_mutation(
        pending_result_id,
        action='office_jobs.bundle.cleanup',
        target_type='office_job_bundle',
        target_id=target_id,
    )
    bundle = store.create_temporary_bundle(record['job_id'], bundle_id=bundle_id)
    original_payload = bundle.read_bytes()
    intent, evidence = jobs_api._bind_temporary_bundle_cleanup_evidence(
        store,
        pending_result_id=pending_result_id,
        bundle_id=bundle_id,
        intent=intent,
    )
    original_fsync_directory = store._fsync_directory
    failed_once = False

    def fail_after_bundle_unlink(path: Path) -> None:
        nonlocal failed_once
        if Path(path) == store._bundles_root and not bundle.exists() and not failed_once:
            failed_once = True
            raise OSError('injected bundle parent fsync failure')
        original_fsync_directory(path)

    monkeypatch.setattr(store, '_fsync_directory', fail_after_bundle_unlink)
    with pytest.raises(OfficeJobDeletionError) as deletion_error:
        store.delete_temporary_bundle_with_replay_evidence(bundle_id, evidence)
    monkeypatch.setattr(store, '_fsync_directory', original_fsync_directory)

    outcome = deletion_error.value.outcome
    assert failed_once
    assert outcome['removed'] is True
    assert outcome['durably_synced'] is False
    store.record_pending_result(
        pending_result_id,
        metadata={'intent': intent, 'outcome': outcome},
        audit_status='partial_failure',
    )
    receipt = store._read_pending_result(pending_result_id)
    assert receipt['intent']['_replay_evidence'] == evidence
    assert receipt['audit_metadata']['outcome']['durably_synced'] is False

    bundle.write_bytes(original_payload)
    restarted = _store(store.root)
    restarted_receipt = restarted._read_pending_result(pending_result_id)
    stored_outcome = dict(restarted_receipt['audit_metadata']['outcome'])
    stored_evidence = restarted_receipt['intent']['_replay_evidence']
    confirmed = restarted.reconcile_temporary_bundle_durability(
        stored_outcome,
        stored_evidence,
    )
    assert confirmed['removed'] is True
    assert confirmed['durably_synced'] is True
    assert not bundle.exists()

    bundle.write_bytes(original_payload + b'-replacement')
    mismatching_restart = _store(store.root)
    with pytest.raises(OfficeJobCorruptionError):
        mismatching_restart.reconcile_temporary_bundle_durability(
            stored_outcome,
            stored_evidence,
        )
    assert bundle.exists()


def test_purge_replay_missing_job_binding_retains_owner_sidecar(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    record = store.create('report', owner_id=1)
    store.write_bytes(record['job_id'], 'report.txt', b'purge replay payload', 'text/plain')
    job_dir = store.job_dir(record['job_id'])
    evidence = store._replay_evidence(
        scope='job',
        entry=job_dir,
        operation='purge_expired',
        job_id=record['job_id'],
        owner_id=1,
    )
    outcome = store._safe_delete_job_dir(job_dir)
    replay_evidence = {
        **evidence,
        'entry_kind': outcome['entry_kind'],
        'parent_id': outcome['parent_id'],
        'source_parent': 'root',
        'source_id': outcome['entry_id'],
        'source_operation': 'purge_expired',
    }
    replay_evidence.pop('job_id')

    restarted = _store(store.root)
    with pytest.raises(ValueError):
        restarted.reconcile_purge_partial_durability(
            {
                'partial_deletion_outcomes': [
                    {**outcome, 'durably_synced': False, 'durability': 'pending', 'retry_required': True},
                ]
            },
            [replay_evidence],
        )

    assert not job_dir.exists()
    assert restarted._owner_identity_path(record['job_id']).exists()
def test_bundle_phase_zero_receipt_replays_not_started_without_materialization(
    app,
    tmp_path: Path,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    owner_id = _admin_id(app)
    bundle_id = 'd' * 32
    target_id = f'bundle-{bundle_id}.zip'
    pending_result_id = store.prepare_pending_result(
        actor_id=owner_id,
        action='office_jobs.bundle.cleanup',
        target_type='office_job_bundle',
        target_id=target_id,
        intent={'bundle_id': bundle_id, 'bundle_name': target_id},
    )

    restarted = _store(store.root)
    with app.state.db.session() as session:
        actor = session.get(User, owner_id)
        assert actor is not None
        jobs_api._reconcile_pending_result_audits(restarted, session, actor=actor)
        events = session.scalars(
            select(AdminAuditEvent).where(
                AdminAuditEvent.idempotency_key == f'{pending_result_id}:result'
            )
        ).all()

    assert not restarted._pending_result_path(pending_result_id).exists()
    assert not (restarted._bundles_root / target_id).exists()
    assert len(events) == 1
    metadata = json.loads(events[0].metadata_json or '{}')
    assert metadata['outcome'] == {
        'operation': 'office_jobs.bundle.cleanup',
        'result': 'not_started',
    }


def test_bundle_terminal_not_materialized_receipt_restarts_after_mark_failure(
    app,
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    owner_id = _admin_id(app)
    bundle_id = 'e' * 32
    target_id = f'bundle-{bundle_id}.zip'
    intent = {'bundle_id': bundle_id, 'bundle_name': target_id}
    pending_result_id = store.prepare_pending_result(
        actor_id=owner_id,
        action='office_jobs.bundle.cleanup',
        target_type='office_job_bundle',
        target_id=target_id,
        intent=intent,
    )
    store.begin_pending_result_mutation(
        pending_result_id,
        action='office_jobs.bundle.cleanup',
        target_type='office_job_bundle',
        target_id=target_id,
    )
    store.record_pending_result(
        pending_result_id,
        metadata={
            'intent': intent,
            'outcome': {
                'operation': 'office_jobs.bundle.cleanup',
                'result': 'not_materialized',
            },
        },
        audit_status='partial_failure',
    )

    def fail_mark(_pending_result_id: str) -> None:
        raise OSError('injected bundle result acknowledgement failure')

    monkeypatch.setattr(store, 'mark_pending_result_audited', fail_mark)
    with app.state.db.session() as session:
        actor = session.get(User, owner_id)
        assert actor is not None
        with pytest.raises(jobs_api.OfficeJobAuditPersistenceError) as failure:
            jobs_api._reconcile_pending_result_audits(store, session, actor=actor)
        events = session.scalars(
            select(AdminAuditEvent).where(
                AdminAuditEvent.idempotency_key == f'{pending_result_id}:result'
            )
        ).all()

    assert failure.value.state.state == 'audit_persisted'
    assert len(events) == 1
    assert store._read_pending_result(pending_result_id)['state'] == 'result_ready'
    assert '_replay_evidence' not in store._read_pending_result(pending_result_id)['intent']

    restarted = _store(store.root)
    with app.state.db.session() as session:
        actor = session.get(User, owner_id)
        assert actor is not None
        jobs_api._reconcile_pending_result_audits(restarted, session, actor=actor)
        replayed = session.scalars(
            select(AdminAuditEvent).where(
                AdminAuditEvent.idempotency_key == f'{pending_result_id}:result'
            )
        ).all()

    assert not restarted._pending_result_path(pending_result_id).exists()
    assert len(replayed) == 1
def test_api_purge_replays_orphan_bundle_temp_with_private_exact_evidence(
    app,
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        manager = _office_user_client(
            app,
            'orphan-bundle-replay-manager',
            permissions=('office.use', 'admin.office.manage'),
        )
        manager_id = _user_id(app, 'orphan-bundle-replay-manager')
        temp = store._bundles_root / '.office_tmp_api_replay'
        payload = b'orphan bundle replay payload'
        temp.write_bytes(payload)
        original_fsync_directory = store._fsync_directory
        failed_once = False

        def fail_after_temp_unlink(path: Path) -> None:
            nonlocal failed_once
            if Path(path) == store._bundles_root and not temp.exists() and not failed_once:
                failed_once = True
                raise OSError('injected orphan bundle temp fsync failure')
            original_fsync_directory(path)

        monkeypatch.setattr(store, '_fsync_directory', fail_after_temp_unlink)
        failed = manager.post('/api/v1/office-tools/jobs/admin/purge')

        assert failed.status_code == 500
        assert failed_once
        partial_result = failed.json()['detail']['partial_result']
        assert partial_result['partial_deletion_outcomes'] == [
            {
                'entry_id': temp.name,
                'entry_kind': 'orphan_temp',
                'parent_id': 'bundles',
                'physical_bytes': len(payload),
                'partial_bytes_removed': len(payload),
                'removed': True,
                'durably_synced': False,
                'durability': 'pending',
                'retry_required': True,
            }
        ]
        assert not temp.exists()
        pending = store.list_pending_results_for_actor(manager_id)
        assert len(pending) == 1
        receipt = pending[0]
        pending_result_id = str(receipt['pending_result_id'])
        assert receipt['state'] == 'audit_persisted'
        receipt_evidence = receipt['audit_metadata']['_replay_evidence']
        assert receipt_evidence == [
            {
                'scope': 'bundles',
                'name': temp.name,
                'operation': 'purge_orphan_temp',
                'identity': {
                    'kind': 'file',
                    'size_bytes': len(payload),
                    'sha256': hashlib.sha256(payload).hexdigest(),
                },
                'signature': {
                    'kind': 'file',
                    'size_bytes': len(payload),
                    'sha256': hashlib.sha256(payload).hexdigest(),
                },
                'entry_kind': 'orphan_temp',
                'parent_id': 'bundles',
            }
        ]

        monkeypatch.setattr(store, '_fsync_directory', original_fsync_directory)
        temp.write_bytes(payload)
        restarted = _store(store.root)
        app.dependency_overrides[get_office_job_store] = lambda: restarted
        replayed = manager.post('/api/v1/office-tools/jobs/admin/purge')

        assert replayed.status_code == 200
        assert not temp.exists()
        assert not restarted._pending_result_path(pending_result_id).exists()
        with app.state.db.session() as session:
            events = session.scalars(
                select(AdminAuditEvent).where(
                    AdminAuditEvent.idempotency_key == f'{pending_result_id}:result'
                )
            ).all()
        assert len(events) == 1
        assert '_replay_evidence' not in json.loads(events[0].metadata_json or '{}')
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)

def test_admin_pending_receipt_inventory_is_private_and_replays_orphaned_actors(
    app,
    tmp_path: Path,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        manager = _office_user_client(
            app,
            'pending-receipt-manager',
            permissions=('office.use', 'admin.office.manage'),
        )
        manager_id = _user_id(app, 'pending-receipt-manager')
        _office_user_client(app, 'pending-receipt-disabled')
        disabled_id = _user_id(app, 'pending-receipt-disabled')
        _office_user_client(app, 'pending-receipt-deleted')
        deleted_id = _user_id(app, 'pending-receipt-deleted')
        disabled_receipt_id = store.prepare_pending_result(
            actor_id=disabled_id,
            action='office_jobs.purge_expired',
            target_type='office_job',
            target_id='retention',
            intent={
                'private_intent': 'intentionally-private',
                '_replay_evidence': {'path': '/private/path', 'sha256': 'a' * 64},
            },
            request_provenance={
                'actor_id': disabled_id,
                'actor_username': 'pending-receipt-disabled',
                'actor_role': 'user',
                'ip_address': '192.0.2.1',
                'user_agent': 'private-agent',
                'request_id': 'private-request',
            },
        )
        deleted_receipt_id = store.prepare_pending_result(
            actor_id=deleted_id,
            action='office_jobs.evidence.dispose',
            target_type='office_job_corrupt_evidence',
            target_id='f' * 32,
            intent={'management_token': 'intentionally-private-token'},
            request_provenance={
                'actor_id': deleted_id,
                'actor_username': 'pending-receipt-deleted',
                'actor_role': 'user',
            },
        )
        with app.state.db.session() as session:
            disabled = session.get(User, disabled_id)
            assert disabled is not None
            disabled.is_active = False
            deleted = session.get(User, deleted_id)
            assert deleted is not None
            session.delete(deleted)

        inventory = manager.get('/api/v1/office-tools/jobs/admin/pending-receipts')

        assert inventory.status_code == 200
        items = {item['pending_result_id']: item for item in inventory.json()['items']}
        allowed_fields = {
            'pending_result_id',
            'original_actor_id',
            'action',
            'target_type',
            'target_id',
            'state',
            'phase',
            'outcome_known',
            'retry_required',
            'created_at',
            'updated_at',
        }
        assert set(items[disabled_receipt_id]) == allowed_fields
        assert items[disabled_receipt_id]['original_actor_id'] == disabled_id
        assert items[disabled_receipt_id]['action'] == 'office_jobs.purge_expired'
        assert items[disabled_receipt_id]['state'] == 'prepared'
        assert items[disabled_receipt_id]['phase'] == 0
        assert items[deleted_receipt_id]['original_actor_id'] == deleted_id
        assert items[deleted_receipt_id]['target_id'] is None
        assert 'intentionally-private' not in inventory.text
        assert '/private/path' not in inventory.text
        assert 'private-agent' not in inventory.text
        assert 'private-request' not in inventory.text
        assert 'a' * 64 not in inventory.text

        disabled_replay = manager.post(
            f'/api/v1/office-tools/jobs/admin/pending-receipts/{disabled_receipt_id}/replay'
        )
        deleted_replay = manager.post(
            f'/api/v1/office-tools/jobs/admin/pending-receipts/{deleted_receipt_id}/replay'
        )
        assert disabled_replay.status_code == 200
        assert disabled_replay.json() == {'pending_result_id': disabled_receipt_id, 'replayed': True}
        assert deleted_replay.status_code == 200
        assert deleted_replay.json() == {'pending_result_id': deleted_receipt_id, 'replayed': True}
        assert not store._pending_result_path(disabled_receipt_id).exists()
        assert not store._pending_result_path(deleted_receipt_id).exists()

        with app.state.db.session() as session:
            disabled_result = session.scalar(
                select(AdminAuditEvent).where(
                    AdminAuditEvent.idempotency_key == f'{disabled_receipt_id}:result'
                )
            )
            deleted_result = session.scalar(
                select(AdminAuditEvent).where(
                    AdminAuditEvent.idempotency_key == f'{deleted_receipt_id}:result'
                )
            )
            operator_events = session.scalars(
                select(AdminAuditEvent)
                .where(
                    AdminAuditEvent.target_id.in_([disabled_receipt_id, deleted_receipt_id]),
                    AdminAuditEvent.action.in_(
                        [
                            'office_jobs.pending_receipt.replay.intent',
                            'office_jobs.pending_receipt.replay',
                        ]
                    ),
                )
                .order_by(AdminAuditEvent.id)
            ).all()
        assert disabled_result is not None
        assert (
            disabled_result.actor_user_id,
            disabled_result.actor_username,
            disabled_result.actor_role,
            disabled_result.idempotency_key,
        ) == (
            disabled_id,
            'pending-receipt-disabled',
            'user',
            f'{disabled_receipt_id}:result',
        )
        assert deleted_result is not None
        assert (
            deleted_result.actor_user_id,
            deleted_result.actor_username,
            deleted_result.actor_role,
            deleted_result.idempotency_key,
        ) == (
            None,
            'pending-receipt-deleted',
            'user',
            f'{deleted_receipt_id}:result',
        )
        assert json.loads(deleted_result.metadata_json or '{}')['original_actor_id'] == deleted_id
        assert [(event.action, event.status, event.actor_user_id) for event in operator_events] == [
            ('office_jobs.pending_receipt.replay.intent', 'intent', manager_id),
            ('office_jobs.pending_receipt.replay', 'success', manager_id),
            ('office_jobs.pending_receipt.replay.intent', 'intent', manager_id),
            ('office_jobs.pending_receipt.replay', 'success', manager_id),
        ]
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)


def test_admin_pending_receipt_replay_requires_office_use_manage_and_csrf_without_side_effects(
    app,
    tmp_path: Path,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        pending_result_id = store.prepare_pending_result(
            actor_id=_admin_id(app),
            action='office_jobs.purge_expired',
            target_type='office_job',
            target_id='retention',
            intent={'retention_days': 365},
        )
        office_only = _office_user_client(app, 'pending-receipt-office-only')
        manage_only = _office_user_client(
            app,
            'pending-receipt-manage-only',
            permissions=('admin.office.manage',),
        )
        _office_user_client(
            app,
            'pending-receipt-no-csrf',
            permissions=('office.use', 'admin.office.manage'),
        )
        no_csrf = TestClient(app)
        login = no_csrf.post(
            '/api/v1/auth/login',
            json={'username': 'pending-receipt-no-csrf', 'password': 'password123'},
        )
        assert login.status_code == 200
        endpoint = f'/api/v1/office-tools/jobs/admin/pending-receipts/{pending_result_id}/replay'
        before = _filesystem_snapshot(store.root)

        assert TestClient(app).post(endpoint).status_code == 401
        assert office_only.get('/api/v1/office-tools/jobs/admin/pending-receipts').status_code == 403
        assert office_only.post(endpoint).status_code == 403
        assert manage_only.get('/api/v1/office-tools/jobs/admin/pending-receipts').status_code == 403
        assert manage_only.post(endpoint).status_code == 403
        assert no_csrf.post(endpoint).status_code == 403

        assert _filesystem_snapshot(store.root) == before
        assert store.get_pending_result(pending_result_id)['state'] == 'prepared'
        with app.state.db.session() as session:
            assert session.scalars(
                select(AdminAuditEvent).where(AdminAuditEvent.target_id == pending_result_id)
            ).all() == []
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)


def test_admin_pending_receipt_replay_keeps_malformed_and_replaced_evidence_unresolved(
    app,
    tmp_path: Path,
) -> None:
    store = _store(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        manager = _office_user_client(
            app,
            'pending-receipt-replacement-manager',
            permissions=('office.use', 'admin.office.manage'),
        )
        manager_id = _user_id(app, 'pending-receipt-replacement-manager')
        malformed_receipt_id = store.prepare_pending_result(
            actor_id=_admin_id(app),
            action='office_jobs.purge_expired',
            target_type='office_job',
            target_id='retention',
            intent={'retention_days': 365},
        )
        malformed_path = store._pending_result_path(malformed_receipt_id)
        malformed_path.write_text('{malformed', encoding='utf-8')

        inventory = manager.get('/api/v1/office-tools/jobs/admin/pending-receipts')
        malformed_item = next(
            item
            for item in inventory.json()['items']
            if item['pending_result_id'] == malformed_receipt_id
        )
        assert malformed_item == {
            'pending_result_id': malformed_receipt_id,
            'original_actor_id': None,
            'action': None,
            'target_type': None,
            'target_id': None,
            'state': 'unresolved',
            'phase': None,
            'outcome_known': False,
            'retry_required': True,
            'created_at': None,
            'updated_at': None,
        }
        malformed_replay = manager.post(
            f'/api/v1/office-tools/jobs/admin/pending-receipts/{malformed_receipt_id}/replay'
        )
        assert malformed_replay.status_code == 409
        assert malformed_path.read_text(encoding='utf-8') == '{malformed'

        original_actor_id = _admin_id(app)
        record = store.create('report', owner_id=original_actor_id)
        store.write_bytes(record['job_id'], 'result.txt', b'original receipt evidence', 'text/plain')
        quarantine = store._quarantine_corrupt_job(store.job_dir(record['job_id']), 'receipt replay')
        assert quarantine is not None
        target_id = str(quarantine['quarantine_id'])
        replay_evidence = store.direct_mutation_replay_evidence('quarantine_restore', target_id)
        replaced_receipt_id = store.prepare_pending_result(
            actor_id=original_actor_id,
            action='office_jobs.quarantine.restore',
            target_type='office_job_quarantine',
            target_id=target_id,
            intent={'_replay_evidence': replay_evidence},
            request_provenance={
                'actor_id': original_actor_id,
                'actor_username': 'admin',
                'actor_role': 'admin',
            },
        )
        store.begin_pending_result_mutation(
            replaced_receipt_id,
            action='office_jobs.quarantine.restore',
            target_type='office_job_quarantine',
            target_id=target_id,
        )
        store.restore_quarantine_outcome(target_id)
        job_dir = store.job_dir(record['job_id'])
        replacement_dir = tmp_path / 'replacement-job'
        shutil.copytree(job_dir, replacement_dir)
        shutil.rmtree(job_dir)
        shutil.copytree(replacement_dir, job_dir)
        replacement_payload = b'replaced receipt evidence'
        artifact_path = job_dir / 'result.txt'
        artifact_path.write_bytes(replacement_payload)
        replacement_record_path = job_dir / 'job.json'
        replacement_record = json.loads(replacement_record_path.read_text(encoding='utf-8'))
        replacement_record['artifacts'][0]['size_bytes'] = len(replacement_payload)
        replacement_record['artifacts'][0]['sha256'] = hashlib.sha256(replacement_payload).hexdigest()
        replacement_record_path.write_text(json.dumps(replacement_record), encoding='utf-8')

        replaced_replay = manager.post(
            f'/api/v1/office-tools/jobs/admin/pending-receipts/{replaced_receipt_id}/replay'
        )

        assert replaced_replay.status_code == 409
        unresolved = store.get_pending_result(replaced_receipt_id)
        assert (unresolved['state'], unresolved['phase']) == ('prepared', 1)
        assert artifact_path.read_bytes() == replacement_payload
        with app.state.db.session() as session:
            success_events = session.scalars(
                select(AdminAuditEvent).where(
                    AdminAuditEvent.idempotency_key == f'{replaced_receipt_id}:result',
                    AdminAuditEvent.status == 'success',
                )
            ).all()
            operator_events = session.scalars(
                select(AdminAuditEvent)
                .where(
                    AdminAuditEvent.target_id == replaced_receipt_id,
                    AdminAuditEvent.action.in_(
                        [
                            'office_jobs.pending_receipt.replay.intent',
                            'office_jobs.pending_receipt.replay',
                        ]
                    ),
                )
                .order_by(AdminAuditEvent.id)
            ).all()
        assert success_events == []
        assert [(event.action, event.status, event.actor_user_id) for event in operator_events] == [
            ('office_jobs.pending_receipt.replay.intent', 'intent', manager_id),
            ('office_jobs.pending_receipt.replay', 'failure', manager_id),
        ]
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)
