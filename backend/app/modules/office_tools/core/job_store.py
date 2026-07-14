"""파일 기반 Office 작업 저장소.

작업 메타데이터와 산출물은 ``backend/data/office_jobs`` 아래의 job 디렉터리에
저장한다. DB 모델을 추가하지 않고도 소유자별 보존 기간·용량을 강제하며, 경로와
재귀 삭제는 검증된 job 디렉터리 안으로만 제한한다.
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import stat
import shutil
import tempfile
import threading
import time
import uuid
import zipfile
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, BinaryIO, Iterator, TypedDict

from app.core.config import Settings

_SAFE_NAME = re.compile(r'[^A-Za-z0-9._-]+')
_JOB_ID = re.compile(r'[0-9a-f]{32}')
_SHA256 = re.compile(r'[0-9a-f]{64}')
_TRANSACTION_ID = re.compile(r'[0-9a-f]{32}')
_STAGE_ID = re.compile(r'(?:create|artifact)-[0-9a-f]{32}')
_BUNDLE_NAME = re.compile(r'bundle-[0-9a-f]{32}\.zip')
_TEMP_FILE_PREFIX = '.office_tmp_'
_LOCKS_DIR_NAME = '.locks'
_QUARANTINE_DIR_NAME = '.quarantine'
_STAGING_DIR_NAME = '.staging'
_TRANSACTIONS_DIR_NAME = '.transactions'
_BUNDLES_DIR_NAME = '.bundles'
_RECOVERY_QUARANTINE_DIR_NAME = '.recovery_quarantine'
_OWNER_IDENTITIES_DIR_NAME = '.owner_identities'
_RECOVERY_METADATA_NAME = 'metadata.json'
_RECOVERY_JOURNAL_NAME = 'journal'
_RECOVERY_STAGE_NAME = 'stage'
_QUARANTINE_METADATA_NAME = 'metadata.json'
_QUARANTINE_PAYLOAD_NAME = 'payload'
_OWNER_DELETION_TOMBSTONES_DIR_NAME = '.owner_deletion_tombstones'
_PENDING_RESULTS_DIR_NAME = '.pending_results'
_PENDING_RESULT_ID = re.compile(r'[0-9a-f]{32}')
_PENDING_RESULT_MAX_BYTES = 256 * 1024
_PENDING_RESULT_CHUNK_BYTES = 64 * 1024
_WINDOWS_LOCK_RETRY_ATTEMPTS = 100
_WINDOWS_LOCK_RETRY_SECONDS = 0.05
_RESERVED_COMPLETE_FIELDS = frozenset(
    {
        'job_id',
        'service',
        'owner_id',
        'status',
        'created_at',
        'updated_at',
        'request_summary',
        'warnings',
        'artifacts',
        'error',
    }
)
_PROCESS_LOCKS: dict[str, threading.RLock] = {}
_PROCESS_LOCKS_GUARD = threading.Lock()


def safe_name(value: str, fallback: str = 'artifact') -> str:
    """artifact 파일명을 ``[A-Za-z0-9._-]`` 로 정규화하고 디렉터리 성분을 제거한다."""
    value = Path(value or fallback).name
    cleaned = _SAFE_NAME.sub('_', value).strip('._')
    return cleaned[:160] or fallback


def strict_owner_id(value: object) -> int:
    """사용자/레코드 소유자를 같은 양의 정수 규칙으로 정규화한다."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError('owner_id must be a positive integer')
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class OfficeJobCapacityError(ValueError):
    """용량 한도를 넘겼을 때 생성 라우트가 422로 변환하는 결정적 오류."""


class OfficeJobCorruptionError(ValueError):
    """job 메타데이터 또는 산출물 manifest가 신뢰할 수 없을 때의 명시적 오류."""

    def __init__(self, job_ids: list[str] | tuple[str, ...]) -> None:
        self.job_ids = tuple(job_ids)
        detail = ', '.join(self.job_ids) or 'unknown job directory'
        super().__init__(f'office job storage contains corrupt records: {detail}')
class OfficeJobPurgeResult(TypedDict):
    """만료 정리가 중간에 실패해도 이미 완료한 작업을 감사할 수 있는 결과."""

    deleted_jobs: int
    deleted_job_ids: list[str]
    freed_bytes: int
    logical_artifact_freed_bytes: int
    physical_deleted_bytes: int
    quarantined_job_ids: list[str]
    quarantined_quarantine_ids: list[str]
    quarantined_bytes: int
    logical_artifact_quarantined_bytes: int
    physical_quarantined_bytes: int
    failed_job_ids: list[str]
    failed_quarantine_ids: list[str]
    quarantine_bytes: int
    temporary_bundle_bytes: int
    expired_quarantine_entries: int
    expired_quarantine_bytes: int
    expired_quarantine_ids: list[str]
    stale_bundles: int
    stale_bundle_bytes: int
    orphan_stage_dirs: int
    orphan_stage_bytes: int
    partial_deletion_outcomes: list[OfficeJobDeletionOutcome]
    maintenance: dict[str, int | list[str]]


class OfficeJobPurgeError(RuntimeError):
    """만료 정리의 부분 완료 결과를 보존하는 명시적 오류."""

    def __init__(self, partial_result: OfficeJobPurgeResult, cause: BaseException | None = None) -> None:
        self.partial_result = partial_result
        self.cause = cause
        detail = f': {cause.__class__.__name__}' if cause is not None else ''
        super().__init__(f'office job purge completed only partially{detail}')

class OfficeJobDeletionOutcome(TypedDict):
    """검증된 삭제 시도의 실제 파일시스템 결과."""

    entry_id: str
    entry_kind: str
    parent_id: str
    physical_bytes: int
    partial_bytes_removed: int
    removed: bool
    durably_synced: bool
    durability: str
    retry_required: bool


class OfficeJobDeletionError(OSError):
    """삭제 뒤 durability가 실패해도 실제 삭제 결과를 보존한다."""

    def __init__(self, outcome: OfficeJobDeletionOutcome, cause: BaseException) -> None:
        self.outcome = outcome
        self.cause = cause
        super().__init__('office job storage deletion did not complete')


class OfficeJobOwnerDeletionOutcome(TypedDict):
    """소유자 삭제의 job·durability·sidecar 정리 실제 결과."""

    operation: str
    job_id: str
    owner_id: int
    logical_bytes: int
    physical_bytes: int
    partial_bytes_removed: int
    removed: bool
    durably_synced: bool
    durability: str
    owner_identity_removed: bool
    owner_identity_durably_synced: bool
    owner_identity_durability: str
    retry_required: bool


class OfficeJobOwnerDeletionError(RuntimeError):
    """소유자 삭제가 일부 완료된 뒤에도 재시도 판단 가능한 결과를 보존한다."""

    def __init__(self, outcome: OfficeJobOwnerDeletionOutcome, cause: BaseException) -> None:
        self.outcome = outcome
        self.cause = cause
        super().__init__('office job owner deletion did not complete')


class OfficeJobArtifactReadLease:
    """열린 no-follow artifact handle과 cross-thread-safe per-job lease를 유지한다."""

    def __init__(
        self,
        handle: BinaryIO,
        *,
        filename: str,
        media_type: str,
        size_bytes: int,
        lock_handle: BinaryIO,
    ) -> None:
        self.handle = handle
        self.filename = filename
        self.media_type = media_type
        self.size_bytes = size_bytes
        self._lock_handle = lock_handle
        self._handle_closed = False
        self._lock_released = False
        self._lock_handle_closed = False
        self._teardown_errors: list[BaseException] = []

    @property
    def teardown_errors(self) -> tuple[BaseException, ...]:
        """응답 종료 뒤에도 관찰 가능한 모든 lease teardown 진단."""
        return tuple(self._teardown_errors)

    def close(self) -> None:
        """Iterator finally/background task가 호출하는 idempotent lease 해제."""
        errors: list[BaseException] = []
        if not self._handle_closed:
            try:
                self.handle.close()
            except BaseException as exc:
                errors.append(exc)
            finally:
                self._handle_closed = True

        if not self._lock_handle_closed:
            try:
                if not self._lock_released:
                    OfficeJobStore._unlock_file(self._lock_handle)
                    self._lock_released = True
            except BaseException as exc:
                errors.append(exc)
            finally:
                try:
                    self._lock_handle.close()
                except BaseException as exc:
                    errors.append(exc)
                finally:
                    # Closing the file descriptor releases an OS advisory lock even if
                    # the explicit unlock failed, so a later close must not touch it.
                    self._lock_released = True
                    self._lock_handle_closed = True

        self._teardown_errors.extend(errors)
        if errors:
            raise errors[0]
class OfficeJobQuarantineMutationOutcome(TypedDict):
    """격리 이동의 감사 가능한 실제 결과."""

    metadata: dict[str, Any]
    quarantine_id: str
    logical_artifact_bytes: int
    physical_moved_bytes: int
    payload_remains_moved: bool


class OfficeJobQuarantineMutationError(RuntimeError):
    """격리 이동의 일부 결과와 원인을 함께 보존한다."""

    def __init__(self, outcome: OfficeJobQuarantineMutationOutcome, cause: BaseException) -> None:
        self.outcome = outcome
        self.cause = cause
        super().__init__('office job storage quarantine did not complete')
class OfficeJobDirectMutationOutcome(TypedDict):
    """관리자 직접 mutation의 공개·제거·durability 상태."""

    operation: str
    target_id: str
    management_token: str | None
    job_id: str | None
    owner_id: int | None
    logical_bytes: int
    physical_bytes: int
    partial_bytes_removed: int
    published: bool
    removed: bool
    durably_synced: bool
    durability: str
    retry_required: bool


class OfficeJobDirectMutationError(RuntimeError):
    """직접 mutation이 뒤늦게 실패해도 실제 결과를 보존한다."""

    def __init__(self, outcome: OfficeJobDirectMutationOutcome, cause: BaseException) -> None:
        self.outcome = outcome
        self.cause = cause
        super().__init__('office job direct mutation did not complete')
class OfficeJobPendingResultError(RuntimeError):
    """결과 receipt의 크기·write·fsync 실패에도 메모리 결과를 보존한다."""

    def __init__(
        self,
        pending_result_id: str,
        outcome: dict[str, Any],
        cause: BaseException,
    ) -> None:
        self.pending_result_id = pending_result_id
        self.outcome = outcome
        self.cause = cause
        super().__init__('office job pending result was not durably recorded')






class OfficeJobStore:
    """파일시스템 기반 job 저장소. 생성자 루트 주입은 기존 테스트와 호환된다."""

    def __init__(
        self,
        root: Path,
        *,
        retention_days: int = 30,
        max_jobs_per_owner: int = 100,
        max_bytes_per_owner: int = 1024 * 1024 * 1024,
        min_free_bytes: int = 512 * 1024 * 1024,
        quarantine_retention_days: int = 30,
        max_temporary_bundles: int = 10,
        temporary_bundle_retention_seconds: int = 3600,
    ) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._locks_root = self.root / _LOCKS_DIR_NAME
        self._locks_root.mkdir(parents=True, exist_ok=True)
        self._quarantine_root = self.root / _QUARANTINE_DIR_NAME
        self._quarantine_root.mkdir(parents=True, exist_ok=True)
        self._staging_root = self.root / _STAGING_DIR_NAME
        self._staging_root.mkdir(parents=True, exist_ok=True)
        self._transactions_root = self.root / _TRANSACTIONS_DIR_NAME
        self._transactions_root.mkdir(parents=True, exist_ok=True)
        self._owner_identities_root = self.root / _OWNER_IDENTITIES_DIR_NAME
        self._owner_identities_root.mkdir(parents=True, exist_ok=True)
        self._owner_deletion_tombstones_root = self.root / _OWNER_DELETION_TOMBSTONES_DIR_NAME
        self._owner_deletion_tombstones_root.mkdir(parents=True, exist_ok=True)
        self._pending_results_root = self.root / _PENDING_RESULTS_DIR_NAME
        self._pending_results_root.mkdir(parents=True, exist_ok=True)
        self._recovery_quarantine_root = self.root / _RECOVERY_QUARANTINE_DIR_NAME
        self._recovery_quarantine_root.mkdir(parents=True, exist_ok=True)
        self._bundles_root = self.root / _BUNDLES_DIR_NAME
        self._bundles_root.mkdir(parents=True, exist_ok=True)
        self.retention_days = self._non_negative_setting(retention_days, 'retention_days')
        self.max_jobs_per_owner = self._non_negative_setting(max_jobs_per_owner, 'max_jobs_per_owner')
        self.max_bytes_per_owner = self._non_negative_setting(max_bytes_per_owner, 'max_bytes_per_owner')
        self.min_free_bytes = self._non_negative_setting(min_free_bytes, 'min_free_bytes')
        self.quarantine_retention_days = self._non_negative_setting(
            quarantine_retention_days,
            'quarantine_retention_days',
        )
        self.max_temporary_bundles = self._non_negative_setting(
            max_temporary_bundles,
            'max_temporary_bundles',
        )
        self.temporary_bundle_retention_seconds = self._positive_setting(
            temporary_bundle_retention_seconds,
            'temporary_bundle_retention_seconds',
        )
        self.last_maintenance: dict[str, int | list[str]] = self._empty_maintenance_result()
        self._management_token_key = uuid.uuid4().bytes
        self._management_tokens: dict[str, tuple[str, str, tuple[int, int, int, int] | None]] = {}

    @classmethod
    def from_settings(cls, settings: Settings) -> 'OfficeJobStore':
        return cls(
            settings.project_root / 'backend' / 'data' / 'office_jobs',
            retention_days=settings.office_job_retention_days,
            max_jobs_per_owner=settings.office_job_max_jobs_per_owner,
            max_bytes_per_owner=settings.office_job_max_bytes_per_owner,
            min_free_bytes=settings.office_job_min_free_disk_bytes,
            quarantine_retention_days=settings.office_job_quarantine_retention_days,
            max_temporary_bundles=settings.office_job_max_temporary_bundles,
            temporary_bundle_retention_seconds=settings.office_job_temporary_bundle_retention_seconds,
        )

    @staticmethod
    def _non_negative_setting(value: int, name: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f'{name} must be a non-negative integer')
        return value

    @staticmethod
    def _positive_setting(value: int, name: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f'{name} must be a positive integer')
        return value


    def _owner_identity_path(self, job_id: str) -> Path:
        if not _JOB_ID.fullmatch(job_id):
            raise ValueError('invalid job id')
        return self._owner_identities_root / f'{job_id}.json'

    def _read_owner_identity(self, job_id: str) -> int | None:
        path = self._owner_identity_path(job_id)
        try:
            if not path.exists() and not path.is_symlink():
                return None
            if (
                path.is_symlink()
                or not path.is_file()
                or path.resolve().parent != self._owner_identities_root.resolve()
            ):
                raise ValueError('owner identity is invalid')
            value = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(value, dict) or value.get('job_id') != job_id:
                raise ValueError('owner identity is invalid')
            return strict_owner_id(value.get('owner_id'))
        except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError, TypeError) as exc:
            raise OfficeJobCorruptionError([job_id]) from exc

    def _ensure_owner_identity(self, job_id: str, owner_id: object) -> int:
        owner = strict_owner_id(owner_id)
        tombstone = self._read_owner_deletion_tombstone_record(job_id)
        indexed_owner = self._read_owner_identity(job_id)
        if tombstone is not None:
            if strict_owner_id(tombstone['owner_id']) != owner:
                raise OfficeJobCorruptionError([job_id])
            if indexed_owner is not None:
                if tombstone['state'] == 'completed':
                    raise OfficeJobCorruptionError([job_id])
                return owner
            if tombstone['state'] == 'sidecar_cleanup_pending' and self._is_external_owner_sidecar_cleanup(tombstone):
                intent = tombstone.get('intent')
                if not isinstance(intent, dict):
                    raise OfficeJobCorruptionError([job_id])
                parent_name = intent.get('source_parent')
                source_id = intent.get('source_id')
                parents = {
                    'root': self.root,
                    'quarantine': self._quarantine_root,
                    'recovery_quarantine': self._recovery_quarantine_root,
                }
                parent = parents.get(parent_name)
                valid_source_id = (
                    parent_name == 'root'
                    and isinstance(source_id, str)
                    and _JOB_ID.fullmatch(source_id) is not None
                    or parent_name in {'quarantine', 'recovery_quarantine'}
                    and isinstance(source_id, str)
                    and _TRANSACTION_ID.fullmatch(source_id) is not None
                )
                if parent is None or not valid_source_id or not self._entry_exists_no_follow(parent / source_id):
                    raise OSError(f'owner deletion remains unresolved: {job_id}')
            elif (
                tombstone['state'] != 'completed'
                or not self._is_external_owner_sidecar_cleanup(tombstone)
            ):
                raise OSError(f'owner deletion remains unresolved: {job_id}')
            self._safe_delete_managed_file(
                self._owner_deletion_tombstone_path(job_id),
                self._owner_deletion_tombstones_root,
                job_id,
                entry_kind='owner_deletion_tombstone',
                parent_id='owner_deletion_tombstones',
            )
        if indexed_owner is not None:
            if indexed_owner != owner:
                raise OfficeJobCorruptionError([job_id])
            return owner
        path = self._owner_identity_path(job_id)
        self._write_json_durable(path, {'job_id': job_id, 'owner_id': owner})
        self._fsync_directory(self._owner_identities_root)
        self._fsync_directory(self.root)
        return owner

    def _owner_identity_for_valid_record(self, job_dir: Path, record: dict[str, Any]) -> int:
        if job_dir.parent != self.root or not _JOB_ID.fullmatch(job_dir.name):
            return strict_owner_id(record['owner_id'])
        return self._ensure_owner_identity(job_dir.name, record['owner_id'])

    def _owner_deletion_tombstone_path(self, job_id: str) -> Path:
        if not _JOB_ID.fullmatch(job_id):
            raise ValueError('invalid job id')
        return self._owner_deletion_tombstones_root / f'{job_id}.json'

    @staticmethod
    def _owner_deletion_tombstone_phase(state: str) -> int:
        phases = {
            'sidecar_cleanup_pending': 0,
            'deletion_pending': 1,
            'finalization_pending': 2,
            'completed': 3,
        }
        try:
            return phases[state]
        except KeyError as exc:
            raise ValueError('owner deletion tombstone state is invalid') from exc

    def _read_owner_deletion_tombstone_record(self, job_id: str) -> dict[str, Any] | None:
        path = self._owner_deletion_tombstone_path(job_id)
        try:
            if not path.exists() and not path.is_symlink():
                return None
            if (
                path.is_symlink()
                or not path.is_file()
                or path.resolve().parent != self._owner_deletion_tombstones_root.resolve()
            ):
                raise ValueError('owner deletion tombstone is invalid')
            value = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(value, dict) or value.get('job_id') != job_id:
                raise ValueError('owner deletion tombstone is invalid')
            owner = strict_owner_id(value.get('owner_id'))
            version = value.get('version', 1)
            state = value.get('state')
            phase = value.get('phase', 0)
            gc_pending = value.get('gc_pending', False)
            audit_acknowledged_at = value.get('audit_acknowledged_at')
            intent = value.get('intent')
            if (
                version not in {1, 2, 3, 4}
                or not isinstance(state, str)
                or isinstance(phase, bool)
                or not isinstance(phase, int)
                or not isinstance(gc_pending, bool)
                or audit_acknowledged_at is not None
                and not isinstance(audit_acknowledged_at, str)
                or intent is not None
                and not isinstance(intent, dict)
            ):
                raise ValueError('owner deletion tombstone is invalid')
            if intent is not None:
                self._bounded_json_object(intent, 'owner deletion tombstone intent')
            expected_phase = self._owner_deletion_tombstone_phase(state)
            if phase != expected_phase:
                raise ValueError('owner deletion tombstone phase is invalid')
            for field in ('created_at', 'updated_at'):
                timestamp = value.get(field)
                if not isinstance(timestamp, str) or not timestamp:
                    raise ValueError('owner deletion tombstone timestamp is invalid')
                datetime.fromisoformat(timestamp)
            if audit_acknowledged_at is not None:
                if not audit_acknowledged_at:
                    raise ValueError('owner deletion tombstone audit acknowledgement is invalid')
                datetime.fromisoformat(audit_acknowledged_at)
            outcome = self._owner_deletion_tombstone_outcome(value)
            if state == 'sidecar_cleanup_pending':
                if outcome is not None or audit_acknowledged_at is not None or gc_pending:
                    raise ValueError('owner deletion tombstone state is invalid')
                if version >= 4 and intent is None:
                    raise ValueError('owner deletion tombstone intent is invalid')
            elif state == 'deletion_pending':
                if (
                    outcome is None
                    or outcome['removed']
                    or outcome['durably_synced']
                    or outcome['owner_identity_removed']
                    or outcome['owner_identity_durably_synced']
                    or not outcome['retry_required']
                    or gc_pending
                ):
                    raise ValueError('owner deletion tombstone state is invalid')
            elif state == 'finalization_pending':
                if (
                    outcome is None
                    or not outcome['removed']
                    or outcome['partial_bytes_removed'] != outcome['physical_bytes']
                    or not outcome['retry_required']
                    or gc_pending
                ):
                    raise ValueError('owner deletion tombstone state is invalid')
            else:
                if (
                    outcome is None
                    or not outcome['removed']
                    or outcome['partial_bytes_removed'] != outcome['physical_bytes']
                    or outcome['durability'] == 'pending'
                    or not outcome['owner_identity_removed']
                    or outcome['owner_identity_durability'] == 'pending'
                    or outcome['retry_required']
                ):
                    raise ValueError('owner deletion tombstone state is invalid')
                if gc_pending != (audit_acknowledged_at is not None):
                    raise ValueError('owner deletion tombstone gc state is invalid')
            if outcome is not None and strict_owner_id(outcome['owner_id']) != owner:
                raise ValueError('owner deletion tombstone outcome is invalid')
            return value
        except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError, TypeError) as exc:
            raise OfficeJobCorruptionError([job_id]) from exc

    def _read_owner_deletion_tombstone(self, job_id: str) -> int | None:
        record = self._read_owner_deletion_tombstone_record(job_id)
        return None if record is None else strict_owner_id(record['owner_id'])

    def _owner_deletion_tombstone_outcome(
        self,
        record: dict[str, Any] | None,
    ) -> OfficeJobOwnerDeletionOutcome | None:
        if record is None or not isinstance(record.get('outcome'), dict):
            return None
        outcome = dict(record['outcome'])
        required = {
            'operation': str,
            'job_id': str,
            'owner_id': int,
            'logical_bytes': int,
            'physical_bytes': int,
            'partial_bytes_removed': int,
            'removed': bool,
            'durably_synced': bool,
            'durability': str,
            'owner_identity_removed': bool,
            'owner_identity_durably_synced': bool,
            'owner_identity_durability': str,
            'retry_required': bool,
        }
        if any(
            (
                not isinstance(outcome.get(name), expected)
                or (expected is int and isinstance(outcome.get(name), bool))
            )
            for name, expected in required.items()
        ):
            raise OfficeJobCorruptionError([str(record.get('job_id'))])
        if (
            outcome['operation'] != 'owner_delete'
            or outcome['job_id'] != record['job_id']
            or outcome['owner_id'] != record['owner_id']
            or outcome['partial_bytes_removed'] > outcome['physical_bytes']
            or any(outcome[name] < 0 for name in ('logical_bytes', 'physical_bytes', 'partial_bytes_removed'))
            or outcome['owner_identity_durably_synced'] and not outcome['owner_identity_removed']
            or outcome['durably_synced'] != self._outcome_synced(outcome['durability'])
            or outcome['owner_identity_durably_synced'] != self._outcome_synced(outcome['owner_identity_durability'])
            or outcome['durability'] not in {'pending', 'synced', 'platform_best_effort'}
            or outcome['owner_identity_durability'] not in {'pending', 'synced', 'platform_best_effort'}
        ):
            raise OfficeJobCorruptionError([str(record.get('job_id'))])
        return outcome  # type: ignore[return-value]

    def _write_owner_deletion_tombstone(self, job_id: str, record: dict[str, Any]) -> None:
        self._write_json_durable(self._owner_deletion_tombstone_path(job_id), record)
        self._fsync_directory(self._owner_deletion_tombstones_root)

    def _ensure_owner_deletion_tombstone(self, job_id: str, owner_id: object) -> int:
        owner = strict_owner_id(owner_id)
        existing = self._read_owner_deletion_tombstone_record(job_id)
        if existing is not None:
            if strict_owner_id(existing['owner_id']) != owner:
                raise OfficeJobCorruptionError([job_id])
            return owner
        now = _now_iso()
        self._write_owner_deletion_tombstone(
            job_id,
            {
                'version': 4,
                'job_id': job_id,
                'owner_id': owner,
                'state': 'sidecar_cleanup_pending',
                'phase': 0,
                'intent': {
                    'operation': 'owner_delete',
                    'job_id': job_id,
                    'owner_id': owner,
                    'audit_required': True,
                },
                'outcome': None,
                'audit_acknowledged_at': None,
                'gc_pending': False,
                'created_at': now,
                'updated_at': now,
            },
        )
        return owner
    def _prepare_owner_identity_cleanup_tombstone(
        self,
        job_id: str,
        owner_id: object,
        *,
        source_parent: str,
        source_id: str,
        source_operation: str,
    ) -> int:
        """Persist sidecar cleanup intent before deleting its last durable source."""
        owner = strict_owner_id(owner_id)
        parents = {
            'root': self.root,
            'quarantine': self._quarantine_root,
            'recovery_quarantine': self._recovery_quarantine_root,
        }
        valid_source_id = (
            source_parent == 'root'
            and isinstance(source_id, str)
            and _JOB_ID.fullmatch(source_id) is not None
            or source_parent in {'quarantine', 'recovery_quarantine'}
            and isinstance(source_id, str)
            and _TRANSACTION_ID.fullmatch(source_id) is not None
        )
        if (
            source_parent not in parents
            or not valid_source_id
            or not isinstance(source_operation, str)
            or not source_operation
        ):
            raise ValueError('owner sidecar cleanup intent is invalid')
        existing = self._read_owner_deletion_tombstone_record(job_id)
        if existing is not None:
            if strict_owner_id(existing['owner_id']) != owner:
                raise OfficeJobCorruptionError([job_id])
            if existing['state'] != 'sidecar_cleanup_pending':
                return owner
            record = dict(existing)
        else:
            now = _now_iso()
            record = {
                'version': 4,
                'job_id': job_id,
                'owner_id': owner,
                'state': 'sidecar_cleanup_pending',
                'phase': 0,
                'outcome': None,
                'audit_acknowledged_at': None,
                'gc_pending': False,
                'created_at': now,
                'updated_at': now,
            }
        record.update(
            {
                'version': 4,
                'intent': {
                    'operation': 'owner_identity_cleanup',
                    'job_id': job_id,
                    'owner_id': owner,
                    'source_parent': source_parent,
                    'source_id': source_id,
                    'source_operation': source_operation,
                    'audit_required': False,
                },
                'updated_at': _now_iso(),
            }
        )
        self._read_owner_deletion_tombstone_record(job_id)
        self._write_owner_deletion_tombstone(job_id, record)
        return owner

    @staticmethod
    def _is_external_owner_sidecar_cleanup(record: dict[str, Any]) -> bool:
        intent = record.get('intent')
        return (
            isinstance(intent, dict)
            and intent.get('operation') == 'owner_identity_cleanup'
            and intent.get('audit_required') is False
        )

    def _discard_completed_external_owner_sidecar_tombstone(self, job_id: str) -> None:
        record = self._read_owner_deletion_tombstone_record(job_id)
        if (
            record is None
            or record['state'] != 'completed'
            or not self._is_external_owner_sidecar_cleanup(record)
            or self._entry_exists_no_follow(self.root / job_id)
            or self._entry_exists_no_follow(self._owner_identity_path(job_id))
        ):
            return
        self._safe_delete_managed_file(
            self._owner_deletion_tombstone_path(job_id),
            self._owner_deletion_tombstones_root,
            job_id,
            entry_kind='owner_deletion_tombstone',
            parent_id='owner_deletion_tombstones',
        )

    def _record_owner_deletion_tombstone_outcome(
        self,
        job_id: str,
        outcome: OfficeJobOwnerDeletionOutcome,
        *,
        state: str,
    ) -> OfficeJobOwnerDeletionOutcome:
        phase = self._owner_deletion_tombstone_phase(state)
        record = self._read_owner_deletion_tombstone_record(job_id)
        if record is None:
            self._ensure_owner_deletion_tombstone(job_id, outcome['owner_id'])
            record = self._read_owner_deletion_tombstone_record(job_id)
        if record is None or strict_owner_id(record['owner_id']) != outcome['owner_id']:
            raise OfficeJobCorruptionError([job_id])
        existing_phase = int(record['phase'])
        if phase < existing_phase:
            existing = self._owner_deletion_tombstone_outcome(record)
            if record.get('state') == 'completed' and existing is not None:
                return existing
            raise OfficeJobCorruptionError([job_id])
        saved = dict(outcome)
        self._owner_deletion_tombstone_outcome(
            {
                'job_id': job_id,
                'owner_id': record['owner_id'],
                'outcome': saved,
            }
        )
        audit_acknowledged_at = record.get('audit_acknowledged_at')
        record.update(
            {
                'version': 4 if isinstance(record.get('intent'), dict) else 3,
                'state': state,
                'phase': phase,
                'outcome': saved,
                'audit_acknowledged_at': audit_acknowledged_at,
                'gc_pending': state == 'completed' and audit_acknowledged_at is not None,
                'updated_at': _now_iso(),
            }
        )
        self._read_owner_deletion_tombstone_record(job_id)
        self._write_owner_deletion_tombstone(job_id, record)
        return saved  # type: ignore[return-value]

    def _mark_owner_deletion_tombstone_audited(self, receipt: dict[str, Any]) -> None:
        if (
            receipt.get('action') != 'office_jobs.owner_delete'
            or receipt.get('target_type') != 'office_job'
            or not isinstance(receipt.get('target_id'), str)
            or _JOB_ID.fullmatch(receipt['target_id']) is None
        ):
            return
        job_id = receipt['target_id']
        record = self._read_owner_deletion_tombstone_record(job_id)
        if record is None:
            return
        if strict_owner_id(receipt.get('actor_id')) != strict_owner_id(record['owner_id']):
            raise OfficeJobCorruptionError([job_id])
        if record.get('outcome') is None:
            return
        if record.get('audit_acknowledged_at') is None:
            record['audit_acknowledged_at'] = _now_iso()
        record['version'] = 3
        record['gc_pending'] = record['state'] == 'completed'
        record['updated_at'] = _now_iso()
        self._read_owner_deletion_tombstone_record(job_id)
        self._write_owner_deletion_tombstone(job_id, record)

    def _resolved_owner_id(self, job_id: str) -> int | None:
        identity_owner = self._read_owner_identity(job_id)
        tombstone_owner = self._read_owner_deletion_tombstone(job_id)
        if identity_owner is not None and tombstone_owner is not None and identity_owner != tombstone_owner:
            raise OfficeJobCorruptionError([job_id])
        return identity_owner if identity_owner is not None else tombstone_owner

    def _finalize_owner_deletion_tombstone(
        self,
        job_id: str,
        outcome: OfficeJobOwnerDeletionOutcome,
    ) -> OfficeJobOwnerDeletionOutcome:
        """Keep a durable completed marker; do not delete the retry target during fsync."""
        if not _JOB_ID.fullmatch(job_id):
            raise ValueError('invalid job id')
        if self._entry_exists_no_follow(self.root / job_id):
            raise OSError(f'job has not been resolved: {job_id}')
        if self._entry_exists_no_follow(self._owner_identity_path(job_id)):
            raise OSError(f'owner identity has not been resolved: {job_id}')
        record = self._read_owner_deletion_tombstone_record(job_id)
        if record is None:
            raise OSError(f'owner deletion tombstone is missing: {job_id}')
        existing = self._owner_deletion_tombstone_outcome(record)
        if record['state'] == 'completed' and existing is not None:
            return existing
        finalized = dict(outcome)
        finalized['retry_required'] = (
            finalized.get('durability') == 'pending'
            or finalized.get('owner_identity_durability') == 'pending'
        )
        finalized['owner_identity_removed'] = True
        return self._record_owner_deletion_tombstone_outcome(
            job_id,
            finalized,  # type: ignore[arg-type]
            state='completed',
        )

    def _remove_owner_identity_after_resolution(self, job_id: str) -> None:
        if not _JOB_ID.fullmatch(job_id):
            raise ValueError('invalid job id')
        job_dir = self.root / job_id
        if self._entry_exists_no_follow(job_dir):
            raise OSError(f'job has not been resolved: {job_id}')
        record = self._read_owner_deletion_tombstone_record(job_id)
        identity_owner = self._read_owner_identity(job_id)
        if record is not None and identity_owner is not None and record['owner_id'] != identity_owner:
            raise OfficeJobCorruptionError([job_id])
        if record is None and identity_owner is not None:
            self._prepare_owner_identity_cleanup_tombstone(
                job_id,
                identity_owner,
                source_parent='root',
                source_id=job_id,
                source_operation='orphan_owner_identity_cleanup',
            )
            record = self._read_owner_deletion_tombstone_record(job_id)
        if record is None:
            return
        outcome = self._owner_deletion_tombstone_outcome(record)
        if record['state'] == 'sidecar_cleanup_pending':
            outcome = self._owner_deletion_baseline(
                job_id,
                strict_owner_id(record['owner_id']),
                logical_bytes=0,
                physical_bytes=0,
            )
            outcome['partial_bytes_removed'] = 0
            outcome['removed'] = True
            self._apply_owner_directory_sync_outcome(outcome, self.root)
            outcome = self._record_owner_deletion_tombstone_outcome(
                job_id,
                outcome,
                state='finalization_pending',
            )
        elif outcome is None:
            raise OfficeJobCorruptionError([job_id])
        elif record['state'] != 'completed':
            outcome = dict(outcome)
            outcome['partial_bytes_removed'] = outcome['physical_bytes']
            outcome['removed'] = True
            if outcome['durability'] == 'pending':
                self._apply_owner_directory_sync_outcome(outcome, self.root)
            else:
                outcome['durably_synced'] = self._outcome_synced(outcome['durability'])
            outcome = self._record_owner_deletion_tombstone_outcome(
                job_id,
                outcome,  # type: ignore[arg-type]
                state='finalization_pending',
            )
        path = self._owner_identity_path(job_id)
        if self._entry_exists_no_follow(path):
            path.unlink()
        self._apply_owner_directory_sync_outcome(outcome, self._owner_identities_root, identity=True)
        if self._entry_exists_no_follow(path):
            raise OSError(f'owner identity was not deleted: {job_id}')
        finalized = dict(outcome)
        finalized['owner_identity_removed'] = True
        finalized['owner_identity_durably_synced'] = self._outcome_synced(outcome['owner_identity_durability'])
        finalized['owner_identity_durability'] = outcome['owner_identity_durability']
        self._finalize_owner_deletion_tombstone(
            job_id,
            finalized,  # type: ignore[arg-type]
        )
        self._discard_completed_external_owner_sidecar_tombstone(job_id)

    @staticmethod
    def _json_object_bytes(value: dict[str, Any], name: str) -> bytes:
        if not isinstance(value, dict):
            raise ValueError(f'{name} must be an object')
        try:
            return json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(',', ':'),
            ).encode('utf-8')
        except (TypeError, ValueError) as exc:
            raise ValueError(f'{name} must be JSON serializable') from exc

    @classmethod
    def _bounded_json_object(cls, value: dict[str, Any], name: str) -> dict[str, Any]:
        if len(cls._json_object_bytes(value, name)) > _PENDING_RESULT_MAX_BYTES:
            raise ValueError(f'{name} exceeds the pending result size limit')
        return value

    def _pending_result_path(self, pending_result_id: str) -> Path:
        if not _PENDING_RESULT_ID.fullmatch(pending_result_id):
            raise ValueError('invalid pending result id')
        return self._pending_results_root / f'{pending_result_id}.json'

    def _pending_result_chunk_path(self, pending_result_id: str, index: int) -> Path:
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < 1_000_000:
            raise ValueError('invalid pending result chunk index')
        self._pending_result_path(pending_result_id)
        return self._pending_results_root / f'{pending_result_id}.chunk-{index:06d}'

    def _pending_result_chunks(self, pending_result_id: str, count: int) -> list[Path]:
        if isinstance(count, bool) or not isinstance(count, int) or not 0 <= count < 1_000_000:
            raise ValueError('invalid pending result chunk count')
        return [self._pending_result_chunk_path(pending_result_id, index) for index in range(count)]

    def _read_pending_result_chunks(
        self,
        pending_result_id: str,
        count: int,
        expected_sha256: str,
    ) -> dict[str, Any]:
        chunks: list[bytes] = []
        for path in self._pending_result_chunks(pending_result_id, count):
            if (
                path.is_symlink()
                or not path.is_file()
                or path.resolve().parent != self._pending_results_root.resolve()
            ):
                raise ValueError('pending result chunk is invalid')
            chunks.append(path.read_bytes())
        encoded = b''.join(chunks)
        if hashlib.sha256(encoded).hexdigest() != expected_sha256:
            raise ValueError('pending result chunks do not match the receipt')
        value = json.loads(encoded.decode('utf-8'))
        self._json_object_bytes(value, 'pending result metadata')
        return value

    def _pending_result_storage_record(
        self,
        record: dict[str, Any],
    ) -> tuple[dict[str, Any], list[bytes]]:
        existing_chunk_count = record.get('result_chunk_count')
        existing_checksum = record.get('result_sha256')
        if (
            isinstance(existing_chunk_count, int)
            and not isinstance(existing_chunk_count, bool)
            and existing_chunk_count > 0
            and record.get('audit_metadata') == {'chunked': True}
            and isinstance(existing_checksum, str)
            and _SHA256.fullmatch(existing_checksum) is not None
        ):
            return dict(record), []
        metadata = record.get('audit_metadata')
        encoded_metadata = self._json_object_bytes(metadata, 'pending result metadata')
        storage = dict(record)
        storage['result_chunk_count'] = 0
        storage['result_sha256'] = None
        if len(self._json_object_bytes(storage, 'pending result receipt')) <= _PENDING_RESULT_MAX_BYTES:
            return storage, []
        chunks = [
            encoded_metadata[offset : offset + _PENDING_RESULT_CHUNK_BYTES]
            for offset in range(0, len(encoded_metadata), _PENDING_RESULT_CHUNK_BYTES)
        ]
        storage['audit_metadata'] = {'chunked': True}
        storage['result_chunk_count'] = len(chunks)
        storage['result_sha256'] = hashlib.sha256(encoded_metadata).hexdigest()
        if len(self._json_object_bytes(storage, 'pending result receipt')) > _PENDING_RESULT_MAX_BYTES:
            raise ValueError('pending result receipt exceeds the size limit')
        return storage, chunks

    def _write_pending_result_durable(
        self,
        pending_result_id: str,
        record: dict[str, Any],
    ) -> None:
        storage, chunks = self._pending_result_storage_record(record)
        for index, chunk in enumerate(chunks):
            self._write_bytes_durable(self._pending_result_chunk_path(pending_result_id, index), chunk)
        self._write_json_durable(self._pending_result_path(pending_result_id), storage)
        self._fsync_directory(self._pending_results_root)

    def _read_pending_result(
        self,
        pending_result_id: str,
        *,
        allow_cleanup_missing_chunks: bool = False,
    ) -> dict[str, Any]:
        path = self._pending_result_path(pending_result_id)
        try:
            if (
                path.is_symlink()
                or not path.is_file()
                or path.resolve().parent != self._pending_results_root.resolve()
            ):
                raise ValueError('pending result is invalid')
            value = json.loads(path.read_text(encoding='utf-8'))
            if (
                not isinstance(value, dict)
                or value.get('version') not in {1, 2}
                or value.get('pending_result_id') != pending_result_id
                or not isinstance(value.get('action'), str)
                or not value['action']
                or len(value['action']) > 160
                or not isinstance(value.get('target_type'), str)
                or not value['target_type']
                or len(value['target_type']) > 80
                or not isinstance(value.get('target_id'), str)
                or len(value['target_id']) > 160
                or value.get('state') not in {'prepared', 'result_ready', 'audit_persisted'}
                or not isinstance(value.get('intent'), dict)
                or not isinstance(value.get('audit_metadata'), dict)
                or value.get('audit_status') is not None
                and (
                    not isinstance(value.get('audit_status'), str)
                    or not value['audit_status']
                    or len(value['audit_status']) > 80
                )
            ):
                raise ValueError('pending result is invalid')
            strict_owner_id(value.get('actor_id'))
            for field in ('created_at', 'updated_at'):
                timestamp = value.get(field)
                if not isinstance(timestamp, str) or not timestamp:
                    raise ValueError('pending result timestamp is invalid')
                datetime.fromisoformat(timestamp)
            self._bounded_json_object(value['intent'], 'pending result intent')
            if value['version'] == 1:
                self._bounded_json_object(value['audit_metadata'], 'pending result metadata')
                value = self._upgrade_pending_result_record(value)
                self._write_pending_result_durable(pending_result_id, value)
            if (
                not isinstance(value.get('request_provenance'), dict)
                or value.get('outcome_state') not in {'unresolved', 'recorded'}
                or value.get('mutation_boundary')
                not in {'intent_durable', 'mutation_started', 'result_durable', 'audit_persisted'}
                or isinstance(value.get('phase'), bool)
                or not isinstance(value.get('phase'), int)
                or value['phase'] not in {0, 1, 2, 3}
                or isinstance(value.get('result_chunk_count'), bool)
                or not isinstance(value.get('result_chunk_count'), int)
                or value['result_chunk_count'] < 0
                or value.get('cleanup_phase', 'none')
                not in {'none', 'chunks_pending', 'header_pending'}
            ):
                raise ValueError('pending result lifecycle is invalid')
            self._bounded_json_object(value['request_provenance'], 'pending result provenance')
            state = value['state']
            phase = value['phase']
            boundary = value['mutation_boundary']
            outcome_state = value['outcome_state']
            cleanup_phase = value.get('cleanup_phase', 'none')
            chunk_count = value['result_chunk_count']
            if state == 'prepared':
                if (
                    outcome_state != 'unresolved'
                    or (phase, boundary) not in {(0, 'intent_durable'), (1, 'mutation_started')}
                    or value.get('audit_status') is not None
                    or value['audit_metadata'] != {}
                    or chunk_count
                    or value.get('result_sha256') is not None
                    or cleanup_phase != 'none'
                ):
                    raise ValueError('pending result lifecycle is invalid')
            elif state == 'result_ready':
                if (
                    outcome_state != 'recorded'
                    or (phase, boundary) != (2, 'result_durable')
                    or not isinstance(value.get('audit_status'), str)
                    or not value['audit_status']
                    or cleanup_phase != 'none'
                ):
                    raise ValueError('pending result lifecycle is invalid')
            elif (
                outcome_state != 'recorded'
                or (phase, boundary) != (3, 'audit_persisted')
                or not isinstance(value.get('audit_status'), str)
                or not value['audit_status']
                or cleanup_phase != 'none'
                and not chunk_count
            ):
                raise ValueError('pending result lifecycle is invalid')
            if chunk_count:
                checksum = value.get('result_sha256')
                if (
                    value['audit_metadata'] != {'chunked': True}
                    or not isinstance(checksum, str)
                    or _SHA256.fullmatch(checksum) is None
                ):
                    raise ValueError('pending result chunks are invalid')
                if cleanup_phase == 'header_pending' and any(
                    self._entry_exists_no_follow(path)
                    for path in self._pending_result_chunks(pending_result_id, chunk_count)
                ):
                    raise ValueError('pending result cleanup header is invalid')
                if cleanup_phase != 'none' and allow_cleanup_missing_chunks:
                    return value
                value['audit_metadata'] = self._read_pending_result_chunks(
                    pending_result_id,
                    chunk_count,
                    checksum,
                )
            else:
                if value.get('result_sha256') is not None:
                    raise ValueError('pending result chunks are invalid')
                self._bounded_json_object(value['audit_metadata'], 'pending result metadata')
            return value
        except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError, TypeError) as exc:
            raise OfficeJobCorruptionError([pending_result_id]) from exc
    @staticmethod
    def _upgrade_pending_result_record(record: dict[str, Any]) -> dict[str, Any]:
        if record.get('version') == 2:
            record.setdefault('cleanup_phase', 'none')
            return record
        state = record.get('state')
        phase = 1 if state == 'prepared' else 2 if state == 'result_ready' else 3
        boundary = (
            'mutation_started'
            if state == 'prepared'
            else 'result_durable'
            if state == 'result_ready'
            else 'audit_persisted'
        )
        actor_id = strict_owner_id(record['actor_id'])
        record.update(
            {
                'version': 2,
                'request_provenance': {
                    'actor_id': actor_id,
                    'actor_username': None,
                    'actor_role': None,
                    'method': None,
                    'path': None,
                    'ip_address': None,
                    'user_agent': None,
                    'request_id': None,
                    'request_available': False,
                },
                'outcome_state': 'unresolved' if state == 'prepared' else 'recorded',
                'mutation_boundary': boundary,
                'phase': phase,
                'cleanup_phase': 'none',
                'result_chunk_count': 0,
                'result_sha256': None,
                'updated_at': _now_iso(),
            }
        )
        return record

    def prepare_pending_result(
        self,
        *,
        actor_id: int,
        action: str,
        target_type: str,
        target_id: str,
        intent: dict[str, Any],
        request_provenance: dict[str, Any] | None = None,
    ) -> str:
        """Create an intent-durable receipt before a destructive mutation starts."""
        pending_result_id = uuid.uuid4().hex
        in_memory: dict[str, Any] = {
            'action': action,
            'target_type': target_type,
            'target_id': target_id,
            'intent': intent,
        }
        try:
            owner = strict_owner_id(actor_id)
            if not isinstance(action, str) or not action or len(action) > 160:
                raise ValueError('pending result action is invalid')
            if not isinstance(target_type, str) or not target_type or len(target_type) > 80:
                raise ValueError('pending result target type is invalid')
            if not isinstance(target_id, str) or len(target_id) > 160:
                raise ValueError('pending result target id is invalid')
            bounded_intent = self._bounded_json_object(intent, 'pending result intent')
            provenance = request_provenance or {'actor_id': owner, 'request_available': False}
            bounded_provenance = self._bounded_json_object(
                provenance,
                'pending result provenance',
            )
            now = _now_iso()
            record = {
                'version': 2,
                'pending_result_id': pending_result_id,
                'actor_id': owner,
                'action': action,
                'target_type': target_type,
                'target_id': target_id,
                'intent': bounded_intent,
                'request_provenance': bounded_provenance,
                'audit_metadata': {},
                'audit_status': None,
                'state': 'prepared',
                'outcome_state': 'unresolved',
                'mutation_boundary': 'intent_durable',
                'phase': 0,
                'cleanup_phase': 'none',
                'result_chunk_count': 0,
                'result_sha256': None,
                'created_at': now,
                'updated_at': now,
            }
            with self._maintenance_lock():
                self._write_pending_result_durable(pending_result_id, record)
                self._fsync_directory(self.root)
            return pending_result_id
        except Exception as exc:
            raise OfficeJobPendingResultError(pending_result_id, in_memory, exc) from exc
    def begin_pending_result_mutation(
        self,
        pending_result_id: str,
        *,
        action: str,
        target_type: str,
        target_id: str,
    ) -> dict[str, Any]:
        """Persist the mutation boundary before a caller crosses an irreversible step."""
        try:
            with self._maintenance_lock():
                record = self._upgrade_pending_result_record(
                    self._read_pending_result(pending_result_id)
                )
                if (
                    record['action'] != action
                    or record['target_type'] != target_type
                    or record['target_id'] != target_id
                ):
                    raise ValueError('pending result does not match the direct mutation')
                if record['state'] != 'prepared':
                    return record
                if record.get('phase') not in {0, 1}:
                    raise ValueError('pending result phase cannot begin a mutation')
                record['phase'] = 1
                record['mutation_boundary'] = 'mutation_started'
                record['outcome_state'] = 'unresolved'
                record['updated_at'] = _now_iso()
                self._write_pending_result_durable(pending_result_id, record)
                return record
        except Exception as exc:
            raise OfficeJobPendingResultError(pending_result_id, {}, exc) from exc

    def attach_pending_result_replay_evidence(
        self,
        pending_result_id: str,
        replay_evidence: dict[str, Any],
    ) -> dict[str, Any]:
        """Durably bind a pending receipt to exact pre-mutation cleanup evidence."""
        try:
            bounded_evidence = self._bounded_json_object(
                replay_evidence,
                'pending result replay evidence',
            )
            with self._maintenance_lock():
                record = self._upgrade_pending_result_record(
                    self._read_pending_result(pending_result_id)
                )
                intent = dict(record['intent'])
                existing = intent.get('_replay_evidence')
                if existing is not None:
                    if existing != bounded_evidence:
                        raise ValueError('pending result replay evidence conflicts')
                    return record
                if record['state'] == 'audit_persisted':
                    raise ValueError('pending result is already audit persisted')
                intent['_replay_evidence'] = bounded_evidence
                record['intent'] = self._bounded_json_object(intent, 'pending result intent')
                record['updated_at'] = _now_iso()
                self._write_pending_result_durable(pending_result_id, record)
                return record
        except Exception as exc:
            if isinstance(exc, OfficeJobPendingResultError):
                raise
            raise OfficeJobPendingResultError(pending_result_id, {}, exc) from exc
    def record_pending_result(
        self,
        pending_result_id: str,
        *,
        metadata: dict[str, Any],
        audit_status: str,
        replace_result: bool = False,
    ) -> dict[str, Any]:
        """Durably persist the actual outcome, chunking an oversized valid receipt."""
        in_memory = (
            dict(metadata['outcome'])
            if isinstance(metadata, dict) and isinstance(metadata.get('outcome'), dict)
            else dict(metadata)
            if isinstance(metadata, dict)
            else {'metadata': metadata}
        )
        try:
            if not isinstance(audit_status, str) or not audit_status or len(audit_status) > 80:
                raise ValueError('pending result audit status is invalid')
            self._json_object_bytes(metadata, 'pending result metadata')
            with self._maintenance_lock():
                record = self._upgrade_pending_result_record(
                    self._read_pending_result(pending_result_id)
                )
                if record['state'] == 'audit_persisted':
                    return record
                if record['state'] == 'result_ready':
                    if (
                        record['audit_status'] == audit_status
                        and record['audit_metadata'] == metadata
                    ):
                        return record
                    if replace_result and not record['result_chunk_count']:
                        record['audit_metadata'] = metadata
                        record['audit_status'] = audit_status
                        record['updated_at'] = _now_iso()
                        self._write_pending_result_durable(pending_result_id, record)
                        return record
                    raise ValueError('pending result already records a different outcome')
                record['audit_metadata'] = metadata
                record['audit_status'] = audit_status
                record['state'] = 'result_ready'
                record['outcome_state'] = 'recorded'
                record['mutation_boundary'] = 'result_durable'
                record['phase'] = 2
                record['updated_at'] = _now_iso()
                self._write_pending_result_durable(pending_result_id, record)
                return record
        except Exception as exc:
            if isinstance(exc, OfficeJobPendingResultError):
                raise
            raise OfficeJobPendingResultError(pending_result_id, in_memory, exc) from exc

    def mark_pending_result_audited(self, pending_result_id: str) -> dict[str, Any]:
        """DB commit 뒤 중복 replay를 막기 위해 outbox를 durably acknowledged로 전이한다."""
        outcome: dict[str, Any] = {}
        try:
            with self._maintenance_lock():
                record = self._upgrade_pending_result_record(
                    self._read_pending_result(pending_result_id)
                )
                outcome = dict(record.get('audit_metadata', {}))
                if record['state'] == 'audit_persisted':
                    return record
                if record['state'] != 'result_ready':
                    raise ValueError('pending result is not ready for audit acknowledgement')
                record['state'] = 'audit_persisted'
                record['mutation_boundary'] = 'audit_persisted'
                record['phase'] = 3
                record['updated_at'] = _now_iso()
                self._write_pending_result_durable(pending_result_id, record)
                return record
        except Exception as exc:
            raise OfficeJobPendingResultError(pending_result_id, outcome, exc) from exc

    @staticmethod
    def _pending_receipt_inventory_item(record: dict[str, Any]) -> dict[str, Any]:
        """Project one validated receipt onto the deliberately non-sensitive operator surface."""
        action = str(record['action'])
        target_type = str(record['target_type'])
        target_id: str | None = str(record['target_id'])
        if action == 'office_jobs.evidence.dispose' or target_type == 'office_job_corrupt_evidence':
            target_id = None
        state = str(record['state'])
        phase = int(record['phase'])
        if state == 'prepared' and phase == 1:
            state = 'mutation_started'
        return {
            'pending_result_id': str(record['pending_result_id']),
            'original_actor_id': strict_owner_id(record['actor_id']),
            'action': action,
            'target_type': target_type,
            'target_id': target_id,
            'state': state,
            'phase': phase,
            'outcome_known': record['outcome_state'] == 'recorded',
            'retry_required': True,
            'created_at': str(record['created_at']),
            'updated_at': str(record['updated_at']),
        }

    @staticmethod
    def _unresolved_pending_receipt_inventory_item(pending_result_id: str) -> dict[str, Any]:
        return {
            'pending_result_id': pending_result_id,
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

    def list_pending_receipt_inventory(self) -> dict[str, list[dict[str, Any]]]:
        """List every pending receipt without exposing its private replay or request evidence."""
        with self._maintenance_lock():
            items: list[dict[str, Any]] = []
            for path in sorted(self._pending_results_root.iterdir(), key=lambda entry: entry.name):
                if (
                    path.suffix != '.json'
                    or _PENDING_RESULT_ID.fullmatch(path.stem) is None
                    or path.is_symlink()
                    or not path.is_file()
                ):
                    continue
                try:
                    record = self._read_pending_result(
                        path.stem,
                        allow_cleanup_missing_chunks=True,
                    )
                except OfficeJobCorruptionError:
                    items.append(self._unresolved_pending_receipt_inventory_item(path.stem))
                else:
                    items.append(self._pending_receipt_inventory_item(record))
            return {'items': items}

    def get_pending_result(self, pending_result_id: str) -> dict[str, Any]:
        """Return one fully validated receipt for internal replay, never for API serialization."""
        with self._maintenance_lock():
            path = self._pending_result_path(pending_result_id)
            if not self._entry_exists_no_follow(path):
                raise FileNotFoundError(pending_result_id)
            return self._read_pending_result(
                pending_result_id,
                allow_cleanup_missing_chunks=True,
            )
    def list_pending_results_for_actor(self, actor_id: int) -> list[dict[str, Any]]:
        """현재 actor가 재시도할 수 있는 아직 DB에 반영되지 않은 결과만 반환한다."""
        owner = strict_owner_id(actor_id)
        with self._maintenance_lock():
            records = [
                self._read_pending_result(path.stem, allow_cleanup_missing_chunks=True)
                for path in self._pending_results_root.iterdir()
                if (
                    path.suffix == '.json'
                    and _PENDING_RESULT_ID.fullmatch(path.stem)
                    and not path.is_symlink()
                    and path.is_file()
                )
            ]
        return [
            record
            for record in records
            if record['actor_id'] == owner
            and record['state'] in {'prepared', 'result_ready', 'audit_persisted'}
        ]

    def acknowledge_pending_result(self, pending_result_id: str) -> OfficeJobDeletionOutcome:
        """Retain an audit-persisted chunk cleanup header until its evidence is durably gone."""
        with self._maintenance_lock():
            path = self._pending_result_path(pending_result_id)
            record = self._read_pending_result(
                pending_result_id,
                allow_cleanup_missing_chunks=True,
            )
            if record['state'] != 'audit_persisted':
                raise ValueError('pending result is not durably audit acknowledged')
            chunk_count = int(record['result_chunk_count'])
            if chunk_count:
                cleanup_phase = record.get('cleanup_phase', 'none')
                if cleanup_phase == 'none':
                    record['cleanup_phase'] = 'chunks_pending'
                    record['updated_at'] = _now_iso()
                    self._write_pending_result_durable(pending_result_id, record)
                    cleanup_phase = 'chunks_pending'
                if cleanup_phase == 'chunks_pending':
                    for chunk in self._pending_result_chunks(pending_result_id, chunk_count):
                        if self._entry_exists_no_follow(chunk):
                            self._safe_delete_managed_file(
                                chunk,
                                self._pending_results_root,
                                chunk.name,
                                entry_kind='pending_result_chunk',
                                parent_id='pending_results',
                            )
                    self._fsync_directory(self._pending_results_root)
                    record['audit_metadata'] = {'chunked': True}
                    record['cleanup_phase'] = 'header_pending'
                    record['updated_at'] = _now_iso()
                    self._write_pending_result_durable(pending_result_id, record)
                elif cleanup_phase != 'header_pending':
                    raise ValueError('pending result cleanup phase is invalid')
            self._mark_owner_deletion_tombstone_audited(record)
            return self._safe_delete_managed_file(
                path,
                self._pending_results_root,
                pending_result_id,
                entry_kind='pending_result',
                parent_id='pending_results',
            )
    @staticmethod
    def _direct_mutation_outcome_from_error(
        exc: BaseException,
    ) -> OfficeJobDirectMutationOutcome | None:
        """Recover a typed outcome hidden by a context-manager teardown exception."""
        seen: set[int] = set()
        current: BaseException | None = exc
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            if isinstance(current, OfficeJobDirectMutationError):
                return current.outcome
            current = current.__context__ or current.__cause__
        return None
    @staticmethod
    def _direct_child_signature(entry: Path) -> tuple[int, int, int, int] | None:
        try:
            value = entry.lstat()
        except OSError:
            return None
        return (value.st_dev, value.st_ino, value.st_mode, value.st_ctime_ns)
    @staticmethod
    def _replay_target_digest(target_id: str) -> str:
        return hashlib.sha256(target_id.encode('utf-8')).hexdigest()

    @classmethod
    def _replay_entry_identity(cls, entry: Path) -> dict[str, Any]:
        """Hash a managed entry without following links so replay cannot target a replacement."""
        value = entry.lstat()
        if stat.S_ISLNK(value.st_mode):
            return {
                'kind': 'symlink',
                'size_bytes': value.st_size,
                'sha256': hashlib.sha256(os.readlink(entry).encode('utf-8')).hexdigest(),
            }
        if stat.S_ISREG(value.st_mode):
            return {
                'kind': 'file',
                'size_bytes': value.st_size,
                'sha256': _sha256_file(entry),
            }
        if not stat.S_ISDIR(value.st_mode):
            raise OfficeJobCorruptionError([entry.name])
        digest = hashlib.sha256()

        def update_tree(path: Path, relative: str = '') -> None:
            for child in sorted(path.iterdir(), key=lambda candidate: candidate.name):
                child_relative = f'{relative}/{child.name}' if relative else child.name
                child_value = child.lstat()
                if child.is_symlink():
                    raise OfficeJobCorruptionError([entry.name])
                if stat.S_ISREG(child_value.st_mode):
                    digest.update(f'file\0{child_relative}\0{child_value.st_size}\0'.encode('utf-8'))
                    digest.update(_sha256_file(child).encode('ascii'))
                elif stat.S_ISDIR(child_value.st_mode):
                    digest.update(f'directory\0{child_relative}\0'.encode('utf-8'))
                    update_tree(child, child_relative)
                else:
                    raise OfficeJobCorruptionError([entry.name])

        update_tree(entry)
        return {
            'kind': 'directory',
            'size_bytes': cls._physical_size_no_follow(entry),
            'sha256': digest.hexdigest(),
        }

    @classmethod
    def _replay_entry_matches_identity(cls, entry: Path, evidence: object) -> bool:
        if not isinstance(evidence, dict):
            return False
        try:
            expected_kind = evidence.get('kind')
            expected_size = evidence.get('size_bytes')
            expected_sha256 = evidence.get('sha256')
            if (
                expected_kind not in {'file', 'directory', 'symlink'}
                or isinstance(expected_size, bool)
                or not isinstance(expected_size, int)
                or expected_size < 0
                or not isinstance(expected_sha256, str)
                or _SHA256.fullmatch(expected_sha256) is None
            ):
                return False
            actual = cls._replay_entry_identity(entry)
            return actual == {
                'kind': expected_kind,
                'size_bytes': expected_size,
                'sha256': expected_sha256,
            }
        except (OSError, OfficeJobCorruptionError):
            return False
    def _job_parent_replay_identity(
        self,
        job_dir: Path,
        record: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if job_dir.parent != self.root or _JOB_ID.fullmatch(job_dir.name) is None:
            raise OfficeJobCorruptionError([job_dir.name])
        current = record if record is not None else self._read_record(job_dir)
        owner = self._owner_identity_for_valid_record(job_dir, current)
        return {
            'kind': 'job_parent',
            'job_id': job_dir.name,
            'owner_id': owner,
            'job_json': self._replay_entry_identity(job_dir / 'job.json'),
        }

    def _job_parent_matches_replay_identity(self, job_dir: Path, evidence: object) -> bool:
        if not isinstance(evidence, dict):
            return False
        try:
            return self._job_parent_replay_identity(job_dir) == {
                'kind': evidence.get('kind'),
                'job_id': evidence.get('job_id'),
                'owner_id': evidence.get('owner_id'),
                'job_json': evidence.get('job_json'),
            }
        except (OSError, OfficeJobCorruptionError):
            return False

    def _replay_evidence(
        self,
        *,
        scope: str,
        entry: Path,
        operation: str,
        job_id: str | None = None,
        owner_id: int | None = None,
        parent_identity: dict[str, Any] | None = None,
        target_id: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(operation, str) or not operation:
            raise ValueError('replay operation is invalid')
        roots = {
            'bundles': self._bundles_root,
            'quarantine': self._quarantine_root,
            'recovery_quarantine': self._recovery_quarantine_root,
            'owner_identities': self._owner_identities_root,
            'job': self.root,
        }
        root = roots.get(scope)
        if root is None or entry.parent != root:
            raise ValueError('replay evidence scope is invalid')
        identity = self._replay_entry_identity(entry)
        evidence: dict[str, Any] = {
            'scope': scope,
            'name': entry.name,
            'operation': operation,
            'identity': identity,
            'signature': identity,
        }
        if job_id is not None:
            evidence['job_id'] = job_id
        if owner_id is not None:
            evidence['owner_id'] = strict_owner_id(owner_id)
        if parent_identity is not None:
            evidence['parent_identity'] = parent_identity
        if target_id is not None:
            if not isinstance(target_id, str) or not target_id or len(target_id) > 160:
                raise ValueError('replay target is invalid')
            evidence['target_sha256'] = self._replay_target_digest(target_id)
        return evidence

    def direct_mutation_replay_evidence(
        self,
        operation: str,
        target_id: str,
    ) -> dict[str, Any]:
        """Persist exact managed-entry identity before a direct destructive mutation."""
        with self._maintenance_lock():
            if operation == 'recovery_delete':
                entry = self._recovery_entry(target_id)
                return self._replay_evidence(
                    scope='recovery_quarantine',
                    entry=entry,
                    operation=operation,
                    target_id=target_id,
                )
            if operation in {'quarantine_delete', 'quarantine_restore'}:
                entry = self._quarantine_entry(target_id)
                metadata = self._read_quarantine_metadata(entry)
                record = self._quarantine_payload_record(entry, metadata)
                payload = entry / _QUARANTINE_PAYLOAD_NAME
                evidence = self._replay_evidence(
                    scope='quarantine',
                    entry=entry,
                    operation=operation,
                    job_id=str(metadata['job_id']),
                    owner_id=strict_owner_id(metadata['owner_id']),
                    target_id=target_id,
                )
                evidence['logical_bytes'] = self._artifact_logical_size(record)
                evidence['physical_bytes'] = int(evidence['identity']['size_bytes'])
                evidence['payload_identity'] = self._replay_entry_identity(payload)
                if not self._replay_entry_matches_identity(entry, evidence['identity']):
                    raise OfficeJobCorruptionError([target_id])
                return evidence
            raise ValueError('direct mutation replay operation is invalid')

    def corrupt_evidence_replay_evidence(self, management_token: str) -> dict[str, Any]:
        """Convert ephemeral management authorization into restart-safe private evidence."""
        with self._maintenance_lock():
            registered = self._management_tokens.get(management_token)
            if registered is None:
                raise FileNotFoundError('invalid management token')
            scope, name, signature = registered
            roots = {
                'quarantine': self._quarantine_root,
                'recovery': self._recovery_quarantine_root,
                'owner_identity': self._owner_identities_root,
            }
            root = roots.get(scope)
            if root is None:
                raise FileNotFoundError('invalid management token')
            entry = root / name
            if self._direct_child_signature(entry) != signature:
                raise OfficeJobCorruptionError(['managed evidence'])
            normalized_scope = {
                'quarantine': 'quarantine',
                'recovery': 'recovery_quarantine',
                'owner_identity': 'owner_identities',
            }[scope]
            return self._replay_evidence(
                scope=normalized_scope,
                entry=entry,
                operation=f'{scope}_corrupt_disposition',
                target_id=management_token,
            )

    def _management_token(self, scope: str, entry: Path) -> str:
        signature = self._direct_child_signature(entry)
        material = f'{scope}\0{entry.name}\0{signature!r}'.encode('utf-8')
        token = hashlib.blake2b(
            material,
            digest_size=16,
            key=self._management_token_key,
        ).hexdigest()
        self._management_tokens[token] = (scope, entry.name, signature)
        return token

    @staticmethod
    def _evidence_timestamp(entry: Path) -> str | None:
        try:
            return datetime.fromtimestamp(entry.lstat().st_mtime, UTC).isoformat()
        except OSError:
            return None

    @staticmethod
    def _direct_child_reason(
        root: Path,
        entry: Path,
        name_pattern: re.Pattern[str],
        required_type: str,
    ) -> str | None:
        try:
            if root.is_symlink() or not root.is_dir() or entry.parent != root:
                return 'evidence containment is invalid'
            if entry.is_symlink():
                return 'evidence is a symlink'
            if name_pattern.fullmatch(entry.name) is None:
                return 'evidence name is invalid'
            if required_type == 'directory' and not entry.is_dir():
                return 'evidence type is invalid'
            if required_type == 'file' and not entry.is_file():
                return 'evidence type is invalid'
            if entry.resolve().parent != root.resolve():
                return 'evidence containment is invalid'
        except OSError:
            return 'evidence metadata is unavailable'
        return None

    def _owner_identity_items_unlocked(self) -> list[dict[str, Any]]:
        if self._owner_identities_root.is_symlink() or not self._owner_identities_root.is_dir():
            raise OfficeJobCorruptionError(['owner identity inventory'])
        items: list[dict[str, Any]] = []
        for entry in self._owner_identities_root.iterdir():
            job_id = entry.stem if entry.suffix == '.json' else None
            reason = self._direct_child_reason(
                self._owner_identities_root,
                entry,
                re.compile(r'[0-9a-f]{32}\.json'),
                'file',
            )
            owner: int | None = None
            if reason is None and job_id is not None:
                try:
                    owner = self._read_owner_identity(job_id)
                    if owner is None:
                        raise ValueError('owner identity is missing')
                except OfficeJobCorruptionError:
                    reason = 'owner identity metadata is invalid'
            physical_bytes = self._physical_size_no_follow(entry)
            if reason is None:
                items.append(
                    {
                        'kind': 'owner_identity',
                        'job_id': job_id,
                        'owner_id': owner,
                        'physical_bytes': physical_bytes,
                    }
                )
                continue
            items.append(
                {
                    'kind': 'corrupt',
                    'management_token': self._management_token('owner_identity', entry),
                    'job_id': None,
                    'owner_id': None,
                    'physical_bytes': physical_bytes,
                    'reason': reason,
                }
            )
        return items

    def _unattributed_owner_identity_bytes_unlocked(self) -> int:
        return sum(
            int(item['physical_bytes'])
            for item in self._owner_identity_items_unlocked()
            if item['kind'] == 'corrupt'
        )

    @contextmanager
    def _owner_capacity_lock(self, owner_id: object) -> Iterator[None]:
        """동일 소유자의 용량 검사와 변경을 프로세스·스레드 간에 직렬화한다."""
        owner = strict_owner_id(owner_id)
        lock_path = self._locks_root / f'owner-{owner}.lock'
        lock_key = str(lock_path)
        with _PROCESS_LOCKS_GUARD:
            process_lock = _PROCESS_LOCKS.setdefault(lock_key, threading.RLock())

        with process_lock:
            with lock_path.open('a+b') as handle:
                self._lock_file(handle)
                try:
                    yield
                finally:
                    self._unlock_file(handle)

    @contextmanager
    def _maintenance_lock(self) -> Iterator[None]:
        """복구·격리·임시 bundle 정리를 프로세스·스레드 간에 직렬화한다."""
        lock_path = self._locks_root / 'maintenance.lock'
        lock_key = str(lock_path)
        with _PROCESS_LOCKS_GUARD:
            process_lock = _PROCESS_LOCKS.setdefault(lock_key, threading.RLock())

        with process_lock:
            with lock_path.open('a+b') as handle:
                self._lock_file(handle)
                try:
                    yield
                finally:
                    self._unlock_file(handle)
    @contextmanager
    def _job_lifecycle_lock(self, job_id: str) -> Iterator[None]:
        """삭제와 stream read lease를 직렬화하는 thread-independent file lock."""
        if not _JOB_ID.fullmatch(job_id):
            raise ValueError('invalid job id')
        lock_path = self._locks_root / f'job-{job_id}.lock'
        with lock_path.open('a+b') as handle:
            self._lock_file(handle)
            try:
                yield
            finally:
                self._unlock_file(handle)

    def _acquire_job_read_lease_lock(self, job_id: str) -> BinaryIO:
        """응답 worker가 해제해도 되는 per-job file lock handle을 반환한다."""
        if not _JOB_ID.fullmatch(job_id):
            raise ValueError('invalid job id')
        lock_path = self._locks_root / f'job-{job_id}.lock'
        handle = lock_path.open('a+b')
        try:
            self._lock_file(handle)
        except BaseException as exc:
            try:
                handle.close()
            except BaseException as teardown_exc:
                exc.add_note(
                    'artifact read lease lock acquisition teardown failed: '
                    f'{teardown_exc.__class__.__name__}: {teardown_exc}'
                )
            raise
        return handle

    @staticmethod
    def _is_windows_lock_contention_error(exc: OSError) -> bool:
        winerror = getattr(exc, 'winerror', None)
        if winerror is not None:
            return winerror in {32, 33}
        return exc.errno in {errno.EACCES, errno.EAGAIN, errno.EWOULDBLOCK}

    @staticmethod
    def _lock_file(handle: Any) -> None:
        if os.name == 'nt':
            import msvcrt

            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b'\0')
                handle.flush()
            handle.seek(0)
            for attempt in range(_WINDOWS_LOCK_RETRY_ATTEMPTS):
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    return
                except OSError as exc:
                    if not OfficeJobStore._is_windows_lock_contention_error(exc):
                        raise
                    if attempt + 1 == _WINDOWS_LOCK_RETRY_ATTEMPTS:
                        raise TimeoutError('timed out acquiring office job file lock') from exc
                    time.sleep(_WINDOWS_LOCK_RETRY_SECONDS)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)

    @staticmethod
    def _unlock_file(handle: Any) -> None:
        if os.name == 'nt':
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def create(self, service: str, owner_id: int, request_summary: dict[str, Any] | None = None) -> dict[str, Any]:
        """새 job을 journal로 생성한다. 만료 보존 정리는 관리자 purge에서만 수행한다."""
        owner = strict_owner_id(owner_id)
        with self._maintenance_lock():
            with self._owner_capacity_lock(owner):
                self._ensure_capacity(owner, jobs_to_add=1, bytes_to_add=0, temporary_write_bytes=0)
                job_id = uuid.uuid4().hex
                now = _now_iso()
                record: dict[str, Any] = {
                    'job_id': job_id,
                    'service': service,
                    'owner_id': owner,
                    'status': 'running',
                    'created_at': now,
                    'updated_at': now,
                    'request_summary': request_summary or {},
                    'warnings': [],
                    'artifacts': [],
                    'error': None,
                }
                stage_id = f'create-{uuid.uuid4().hex}'
                stage_dir = self._staging_root / stage_id
                stage_job_dir = stage_dir / job_id
                journal: dict[str, Any] = {
                    'version': 1,
                    'operation': 'create',
                    'phase': 'prepared',
                    'job_id': job_id,
                    'stage_id': stage_id,
                    'owner_id': owner,
                    'record': record,
                }
                stage_dir.mkdir(parents=False, exist_ok=False)
                self._fsync_directory(self._staging_root)
                try:
                    stage_job_dir.mkdir(parents=False, exist_ok=False)
                    self._write_record(stage_job_dir, record)
                    self._write_journal(stage_id, journal)
                    self._ensure_owner_identity(job_id, owner)
                    stage_job_dir.replace(self.root / job_id)
                    self._fsync_directory(self.root)
                    journal['phase'] = 'job_published'
                    self._write_journal(stage_id, journal)
                except Exception as exc:
                    try:
                        self._rollback_create_transaction(journal, remove_published_job=True)
                    except Exception as rollback_exc:
                        self._preserve_unresolved_recovery(
                            self._existing_journal_path(stage_id),
                            stage_id,
                            f'create rollback failed: {rollback_exc.__class__.__name__}: {rollback_exc}',
                        )
                        raise
                    raise exc
                try:
                    if not self._active_record_matches(self.root / job_id, record):
                        raise OfficeJobCorruptionError([job_id])
                    self._remove_stage_dir(stage_dir)
                    self._remove_journal(stage_id)
                except Exception as exc:
                    self._preserve_unresolved_recovery(
                        self._existing_journal_path(stage_id),
                        stage_id,
                        f'create commit cleanup failed: {exc.__class__.__name__}: {exc}',
                    )
                    raise
        return record

    def job_dir(self, job_id: str) -> Path:
        if not _JOB_ID.fullmatch(job_id):
            raise FileNotFoundError('invalid job id')
        path = self.root / job_id
        if path.parent != self.root or path.is_symlink() or not path.is_dir():
            raise FileNotFoundError(job_id)
        if path.resolve().parent != self.root:
            raise FileNotFoundError(job_id)
        return path

    def get(self, job_id: str) -> dict[str, Any]:
        with self._maintenance_lock():
            job_dir = self.job_dir(job_id)
            initial = self._read_record(job_dir)
            owner = self._owner_identity_for_valid_record(job_dir, initial)
            with self._owner_capacity_lock(owner):
                record = self._read_record(job_dir)
                if self._owner_identity_for_valid_record(job_dir, record) != owner:
                    raise OfficeJobCorruptionError([job_id])
                return record

    def list_for_owner(self, owner_id: int) -> list[dict[str, Any]]:
        """소유자 job을 최신 변경 순으로 반환하며 손상 저장소는 명시적으로 거부한다."""
        owner = strict_owner_id(owner_id)
        with self._maintenance_lock():
            with self._owner_capacity_lock(owner):
                owned_jobs = self._owned_job_records_unlocked(owner)
                for job_dir, record in owned_jobs:
                    self._job_data_size(job_dir, record)
                records = [record for _job_dir, record in owned_jobs]
        return sorted(
            records,
            key=lambda record: (str(record.get('updated_at', '')), str(record.get('job_id', ''))),
            reverse=True,
        )

    def usage_for_owner(self, owner_id: int) -> dict[str, int]:
        """소유자가 실제 점유한 검증된 산출물 바이트를 계산한다."""
        owner = strict_owner_id(owner_id)
        with self._maintenance_lock():
            with self._owner_capacity_lock(owner):
                return self._usage_for_owner_unlocked(owner)

    def storage_accounting(self) -> dict[str, int]:
        """운영자용 파일 저장소 점유량. 격리·임시 bundle도 숨기지 않는다."""
        with self._maintenance_lock():
            artifact_logical_bytes = self._artifact_logical_bytes_unlocked()
            job_physical = self._job_physical_accounting_unlocked()
            quarantine_items = self._quarantine_items_unlocked()
            quarantine_bytes = sum(int(item['size_bytes']) for item in quarantine_items)
            quarantine_physical_bytes = sum(
                int(item['physical_bytes']) for item in quarantine_items
            )
            temporary_bundle_bytes = self._temporary_bundle_usage_bytes_unlocked()
            owner_identity_items = self._owner_identity_items_unlocked()
            owner_identity_physical_bytes = sum(
                int(item['physical_bytes']) for item in owner_identity_items
            )
            corrupt_owner_identity_items = [
                item for item in owner_identity_items if item['kind'] == 'corrupt'
            ]
            recovery_items = self._recovery_items_unlocked()
            recovery_quarantine_physical_bytes = sum(
                int(item['physical_bytes']) for item in recovery_items
            )
            staging_physical_bytes = self._directory_size(self._staging_root)
            transaction_journal_physical_bytes = self._directory_size(self._transactions_root)
            owner_deletion_tombstone_physical_bytes = self._directory_size(
                self._owner_deletion_tombstones_root
            )
            owner_deletion_tombstone_entries = self._managed_regular_file_entries(
                self._owner_deletion_tombstones_root
            )
            pending_result_physical_bytes = self._directory_size(self._pending_results_root)
            pending_result_entries = self._managed_regular_file_entries(self._pending_results_root)
            bundle_physical_bytes = self._directory_size(self._bundles_root)
            lock_physical_bytes = self._directory_size(self._locks_root)
            root_unclassified_physical_bytes = self._root_unclassified_physical_bytes_unlocked()
        total_bytes = (
            job_physical['job_physical_bytes']
            + staging_physical_bytes
            + transaction_journal_physical_bytes
            + owner_deletion_tombstone_physical_bytes
            + pending_result_physical_bytes
            + quarantine_physical_bytes
            + recovery_quarantine_physical_bytes
            + owner_identity_physical_bytes
            + bundle_physical_bytes
            + lock_physical_bytes
            + root_unclassified_physical_bytes
        )
        return {
            'job_bytes': artifact_logical_bytes,
            'artifact_logical_bytes': artifact_logical_bytes,
            'job_logical_bytes': artifact_logical_bytes,
            **job_physical,
            'quarantine_bytes': quarantine_bytes,
            'quarantine_physical_bytes': quarantine_physical_bytes,
            'recovery_quarantine_physical_bytes': recovery_quarantine_physical_bytes,
            'owner_identity_physical_bytes': owner_identity_physical_bytes,
            'owner_identity_entries': len(owner_identity_items),
            'owner_identity_corrupt_entries': len(corrupt_owner_identity_items),
            'owner_identity_corrupt_physical_bytes': sum(
                int(item['physical_bytes']) for item in corrupt_owner_identity_items
            ),
            'staging_physical_bytes': staging_physical_bytes,
            'transaction_journal_physical_bytes': transaction_journal_physical_bytes,
            'owner_deletion_tombstone_entries': owner_deletion_tombstone_entries,
            'owner_deletion_tombstone_physical_bytes': owner_deletion_tombstone_physical_bytes,
            'pending_result_entries': pending_result_entries,
            'pending_result_physical_bytes': pending_result_physical_bytes,
            'temporary_bundle_bytes': temporary_bundle_bytes,
            'bundle_physical_bytes': bundle_physical_bytes,
            'lock_physical_bytes': lock_physical_bytes,
            'root_unclassified_physical_bytes': root_unclassified_physical_bytes,
            'total_bytes': total_bytes,
        }
    def list_owner_identities(self) -> dict[str, Any]:
        """소유자 sidecar를 경로 없이 운영자 inventory로 노출한다."""
        with self._maintenance_lock():
            items = self._owner_identity_items_unlocked()
            corrupt_items = [item for item in items if item['kind'] == 'corrupt']
            return {
                'items': items,
                'total_bytes': sum(int(item['physical_bytes']) for item in items),
                'corrupt_entries': len(corrupt_items),
                'corrupt_physical_bytes': sum(
                    int(item['physical_bytes']) for item in corrupt_items
                ),
            }

    def owner_deletion_intent(self, job_id: str, owner_id: int) -> dict[str, object]:
        """삭제 intent 전 소유권과 sidecar/tombstone 재시도 대상을 검증한다."""
        owner = strict_owner_id(owner_id)
        if not _JOB_ID.fullmatch(job_id):
            raise FileNotFoundError('invalid job id')
        with self._maintenance_lock():
            tombstone = self._read_owner_deletion_tombstone_record(job_id)
            if tombstone is not None:
                if strict_owner_id(tombstone['owner_id']) != owner:
                    raise PermissionError('job belongs to another user')
                stored = self._owner_deletion_tombstone_outcome(tombstone)
                if stored is not None:
                    return {
                        'job_id': job_id,
                        'owner_id': owner,
                        'retrying_sidecar_cleanup': False,
                        'stored_outcome': stored,
                    }
            try:
                job_dir = self.job_dir(job_id)
            except FileNotFoundError:
                if self._entry_exists_no_follow(self.root / job_id):
                    raise OfficeJobCorruptionError([job_id])
                resolved_owner = self._resolved_owner_id(job_id)
                if resolved_owner is None:
                    raise FileNotFoundError(job_id)
                if resolved_owner != owner:
                    raise PermissionError('job belongs to another user')
                return {
                    'job_id': job_id,
                    'owner_id': owner,
                    'retrying_sidecar_cleanup': True,
                    'stored_outcome': None,
                }
            record = self._read_record(job_dir)
            if self._owner_identity_for_valid_record(job_dir, record) != owner:
                raise PermissionError('job belongs to another user')
            intent = {
                'job_id': job_id,
                'owner_id': owner,
                'retrying_sidecar_cleanup': False,
            }
            if tombstone is not None:
                intent['tombstone_pending'] = True
            return intent

    @staticmethod
    def _owner_deletion_baseline(
        job_id: str,
        owner_id: int,
        *,
        logical_bytes: int,
        physical_bytes: int,
    ) -> OfficeJobOwnerDeletionOutcome:
        return {
            'operation': 'owner_delete',
            'job_id': job_id,
            'owner_id': owner_id,
            'logical_bytes': logical_bytes,
            'physical_bytes': physical_bytes,
            'partial_bytes_removed': 0,
            'removed': False,
            'durably_synced': False,
            'durability': 'pending',
            'owner_identity_removed': False,
            'owner_identity_durably_synced': False,
            'owner_identity_durability': 'pending',
            'retry_required': True,
        }

    def _merge_owner_deletion_progress(
        self,
        job_id: str,
        outcome: OfficeJobOwnerDeletionOutcome,
        deletion: OfficeJobDeletionOutcome,
    ) -> None:
        if deletion['removed']:
            outcome['partial_bytes_removed'] = outcome['physical_bytes']
            outcome['removed'] = True
            outcome['durably_synced'] = deletion['durably_synced']
            outcome['durability'] = deletion['durability']
            return
        remaining_bytes = self._physical_size_no_follow(self.root / job_id)
        outcome['partial_bytes_removed'] = max(
            outcome['partial_bytes_removed'],
            max(0, outcome['physical_bytes'] - remaining_bytes),
        )
        outcome['removed'] = False
        outcome['durably_synced'] = False
        outcome['durability'] = 'pending'

    def _complete_owner_deletion_unlocked(
        self,
        job_id: str,
        outcome: OfficeJobOwnerDeletionOutcome,
    ) -> OfficeJobOwnerDeletionOutcome:
        def retain_failure(cause: BaseException) -> None:
            state = 'finalization_pending' if outcome['removed'] else 'deletion_pending'
            try:
                self._record_owner_deletion_tombstone_outcome(job_id, outcome, state=state)
            except Exception as receipt_exc:
                raise OfficeJobOwnerDeletionError(outcome, receipt_exc) from cause
            raise OfficeJobOwnerDeletionError(outcome, cause) from cause

        job_path = self.root / job_id
        if self._entry_exists_no_follow(job_path):
            try:
                deletion = self._safe_delete_job_dir(job_path)
            except OfficeJobDeletionError as exc:
                self._merge_owner_deletion_progress(job_id, outcome, exc.outcome)
                retain_failure(exc)
            self._merge_owner_deletion_progress(job_id, outcome, deletion)
            if not outcome['removed']:
                retain_failure(OSError('job deletion did not complete'))
        else:
            outcome['partial_bytes_removed'] = outcome['physical_bytes']
            outcome['removed'] = True
        if outcome['durability'] == 'pending':
            try:
                self._apply_owner_directory_sync_outcome(outcome, self.root)
            except Exception as exc:
                retain_failure(exc)
        try:
            self._record_owner_deletion_tombstone_outcome(
                job_id,
                outcome,
                state='finalization_pending',
            )
            self._remove_owner_identity_after_resolution(job_id)
            current = self._owner_deletion_tombstone_outcome(
                self._read_owner_deletion_tombstone_record(job_id)
            )
            if current is not None:
                outcome = dict(current)
            outcome['owner_identity_removed'] = not self._entry_exists_no_follow(
                self._owner_identity_path(job_id)
            )
            return self._finalize_owner_deletion_tombstone(job_id, outcome)
        except OfficeJobOwnerDeletionError:
            raise
        except Exception as exc:
            outcome['owner_identity_removed'] = not self._entry_exists_no_follow(
                self._owner_identity_path(job_id)
            )
            retain_failure(exc)
        raise AssertionError('owner deletion failure must raise')

    def delete_for_owner_outcome(
        self,
        job_id: str,
        owner_id: int,
    ) -> OfficeJobOwnerDeletionOutcome | None:
        """Persist a deletion baseline before rmtree and reuse it across damaged retries."""
        owner = strict_owner_id(owner_id)
        if not _JOB_ID.fullmatch(job_id):
            raise FileNotFoundError('invalid job id')
        outcome: OfficeJobOwnerDeletionOutcome | None = None
        try:
            with self._maintenance_lock():
                tombstone = self._read_owner_deletion_tombstone_record(job_id)
                if tombstone is not None:
                    if strict_owner_id(tombstone['owner_id']) != owner:
                        return None
                    stored = self._owner_deletion_tombstone_outcome(tombstone)
                    if stored is not None:
                        if not stored['retry_required']:
                            return stored
                        outcome = dict(stored)
                        with self._owner_capacity_lock(owner):
                            current = self._read_owner_deletion_tombstone_record(job_id)
                            current_outcome = self._owner_deletion_tombstone_outcome(current)
                            if (
                                current is None
                                or strict_owner_id(current['owner_id']) != owner
                                or current_outcome is None
                            ):
                                raise OfficeJobCorruptionError([job_id])
                            if not current_outcome['retry_required']:
                                return current_outcome
                            outcome = dict(current_outcome)
                            return self._complete_owner_deletion_unlocked(job_id, outcome)
                try:
                    job_dir = self.job_dir(job_id)
                except FileNotFoundError:
                    if self._entry_exists_no_follow(self.root / job_id):
                        raise OfficeJobCorruptionError([job_id])
                    resolved_owner = self._resolved_owner_id(job_id)
                    if resolved_owner is None:
                        raise FileNotFoundError(job_id)
                    if resolved_owner != owner:
                        return None
                    with self._owner_capacity_lock(owner):
                        if self._resolved_owner_id(job_id) != owner:
                            return None
                        outcome = self._owner_deletion_baseline(
                            job_id,
                            owner,
                            logical_bytes=0,
                            physical_bytes=0,
                        )
                        outcome['removed'] = True
                        self._ensure_owner_deletion_tombstone(job_id, owner)
                        self._record_owner_deletion_tombstone_outcome(
                            job_id,
                            outcome,
                            state='finalization_pending',
                        )
                        return self._complete_owner_deletion_unlocked(job_id, outcome)
                initial = self._read_record(job_dir)
                if self._owner_identity_for_valid_record(job_dir, initial) != owner:
                    return None
                with self._owner_capacity_lock(owner):
                    tombstone = self._read_owner_deletion_tombstone_record(job_id)
                    stored = self._owner_deletion_tombstone_outcome(tombstone)
                    if tombstone is not None and strict_owner_id(tombstone['owner_id']) != owner:
                        return None
                    if stored is not None:
                        if not stored['retry_required']:
                            return stored
                        outcome = dict(stored)
                        return self._complete_owner_deletion_unlocked(job_id, outcome)
                    record = self._read_record(job_dir)
                    if self._owner_identity_for_valid_record(job_dir, record) != owner:
                        return None
                    outcome = self._owner_deletion_baseline(
                        job_id,
                        owner,
                        logical_bytes=self._artifact_logical_size(record),
                        physical_bytes=self._physical_size_no_follow(job_dir),
                    )
                    self._ensure_owner_deletion_tombstone(job_id, owner)
                    outcome = self._record_owner_deletion_tombstone_outcome(
                        job_id,
                        outcome,
                        state='deletion_pending',
                    )
                    return self._complete_owner_deletion_unlocked(job_id, outcome)
        except OfficeJobOwnerDeletionError:
            raise
        except Exception as exc:
            if outcome is not None:
                outcome['retry_required'] = True
                raise OfficeJobOwnerDeletionError(outcome, exc) from exc
            raise

    def recover(self) -> dict[str, int | list[str]]:
        """시작 시 명시적으로 호출하는 journal 기반 비보존 복구 진입점."""
        with self._maintenance_lock():
            self.last_maintenance = self._recovery_unlocked()
            return dict(self.last_maintenance)


    def _empty_maintenance_result(self) -> dict[str, int | list[str]]:
        return {
            'recovered_transactions': 0,
            'rolled_back_transactions': 0,
            'unresolved_recovery_transactions': 0,
            'unresolved_recovery_ids': [],
            'malformed_recovery_evidence': 0,
            'owner_deletion_tombstone_failures': [],
            'orphan_stage_dirs': 0,
            'orphan_stage_bytes': 0,
            'stale_bundles': 0,
            'stale_bundle_bytes': 0,
            'expired_quarantine_entries': 0,
            'expired_quarantine_bytes': 0,
        }
    def _collect_completed_owner_deletion_tombstones_unlocked(self) -> list[str]:
        cutoff = datetime.now(UTC) - timedelta(days=self.retention_days)
        failed_job_ids: list[str] = []
        for path in self._owner_deletion_tombstones_root.iterdir():
            if path.suffix != '.json' or not _JOB_ID.fullmatch(path.stem):
                continue
            job_id = path.stem
            record = self._read_owner_deletion_tombstone_record(job_id)
            if (
                record is None
                or record['state'] != 'completed'
                or not record['gc_pending']
                or self._entry_exists_no_follow(self.root / job_id)
                or self._entry_exists_no_follow(self._owner_identity_path(job_id))
            ):
                continue
            audit_acknowledged_at = record.get('audit_acknowledged_at')
            if not isinstance(audit_acknowledged_at, str):
                continue
            if datetime.fromisoformat(audit_acknowledged_at).astimezone(UTC) >= cutoff:
                continue
            try:
                self._safe_delete_managed_file(
                    path,
                    self._owner_deletion_tombstones_root,
                    job_id,
                    entry_kind='owner_deletion_tombstone',
                    parent_id='owner_deletion_tombstones',
                )
            except Exception:
                failed_job_ids.append(job_id)
        return failed_job_ids

    def _reconcile_owner_deletion_tombstones_unlocked(self) -> list[str]:
        """Finish marker-only owner deletion work while maintenance serialization is held."""
        if (
            self._owner_deletion_tombstones_root.is_symlink()
            or not self._owner_deletion_tombstones_root.is_dir()
        ):
            raise OfficeJobCorruptionError(['owner deletion tombstone inventory'])
        failed_job_ids: list[str] = []
        for path in self._owner_deletion_tombstones_root.iterdir():
            if path.suffix != '.json' or not _JOB_ID.fullmatch(path.stem):
                continue
            job_id = path.stem
            record = self._read_owner_deletion_tombstone_record(job_id)
            if record is None:
                continue
            external_sidecar = self._is_external_owner_sidecar_cleanup(record)
            if self._entry_exists_no_follow(self.root / job_id):
                if external_sidecar:
                    try:
                        self._safe_delete_managed_file(
                            path,
                            self._owner_deletion_tombstones_root,
                            job_id,
                            entry_kind='owner_deletion_tombstone',
                            parent_id='owner_deletion_tombstones',
                        )
                    except Exception:
                        failed_job_ids.append(job_id)
                continue
            try:
                if external_sidecar:
                    intent = record.get('intent')
                    if not isinstance(intent, dict):
                        raise OfficeJobCorruptionError([job_id])
                    parent_name = intent.get('source_parent')
                    source_id = intent.get('source_id')
                    parents = {
                        'root': self.root,
                        'quarantine': self._quarantine_root,
                        'recovery_quarantine': self._recovery_quarantine_root,
                    }
                    parent = parents.get(parent_name)
                    valid_source_id = (
                        parent_name == 'root'
                        and isinstance(source_id, str)
                        and _JOB_ID.fullmatch(source_id) is not None
                        or parent_name in {'quarantine', 'recovery_quarantine'}
                        and isinstance(source_id, str)
                        and _TRANSACTION_ID.fullmatch(source_id) is not None
                    )
                    if parent is None or not valid_source_id:
                        raise OfficeJobCorruptionError([job_id])
                    if self._entry_exists_no_follow(parent / source_id):
                        self._safe_delete_managed_file(
                            path,
                            self._owner_deletion_tombstones_root,
                            job_id,
                            entry_kind='owner_deletion_tombstone',
                            parent_id='owner_deletion_tombstones',
                        )
                        continue
                    parent_sync = self._fsync_directory(parent)
                else:
                    parent_sync = self._fsync_directory(self.root)
                self._remove_owner_identity_after_resolution(job_id)
                current_record = self._read_owner_deletion_tombstone_record(job_id)
                if not external_sidecar:
                    outcome = self._owner_deletion_tombstone_outcome(current_record)
                    if outcome is not None:
                        reconciled = dict(outcome)
                        reconciled['durably_synced'] = parent_sync is not False
                        reconciled['durability'] = 'synced' if reconciled['durably_synced'] else 'platform_best_effort'
                        self._finalize_owner_deletion_tombstone(
                            job_id,
                            reconciled,  # type: ignore[arg-type]
                        )
            except Exception:
                failed_job_ids.append(job_id)
        return [*failed_job_ids, *self._collect_completed_owner_deletion_tombstones_unlocked()]


    def _recovery_unlocked(
        self,
        purge_result: OfficeJobPurgeResult | None = None,
    ) -> dict[str, int | list[str]]:
        result = self._empty_maintenance_result()
        if purge_result is not None:
            purge_result['maintenance'] = result
        result['owner_deletion_tombstone_failures'] = self._reconcile_owner_deletion_tombstones_unlocked()
        recovered, rolled_back = self._recover_transactions_unlocked()
        result['recovered_transactions'] = recovered
        result['rolled_back_transactions'] = rolled_back
        orphan_dirs, orphan_bytes = self._reconcile_orphan_stage_dirs_unlocked(purge_result)
        result['orphan_stage_dirs'] = orphan_dirs
        result['orphan_stage_bytes'] = orphan_bytes
        recovery_items = self._recovery_items_unlocked()
        unresolved_ids = self._unresolved_recovery_ids_unlocked(recovery_items)
        result['unresolved_recovery_transactions'] = len(recovery_items)
        result['unresolved_recovery_ids'] = unresolved_ids
        result['malformed_recovery_evidence'] = sum(
            item.get('kind') == 'corrupt' for item in recovery_items
        )
        return result

    def _empty_purge_result(self) -> OfficeJobPurgeResult:
        return {
            'deleted_jobs': 0,
            'deleted_job_ids': [],
            'freed_bytes': 0,
            'logical_artifact_freed_bytes': 0,
            'physical_deleted_bytes': 0,
            'quarantined_job_ids': [],
            'quarantined_quarantine_ids': [],
            'quarantined_bytes': 0,
            'logical_artifact_quarantined_bytes': 0,
            'physical_quarantined_bytes': 0,
            'failed_job_ids': [],
            'failed_quarantine_ids': [],
            'quarantine_bytes': 0,
            'temporary_bundle_bytes': 0,
            'expired_quarantine_entries': 0,
            'expired_quarantine_bytes': 0,
            'expired_quarantine_ids': [],
            'stale_bundles': 0,
            'stale_bundle_bytes': 0,
            'orphan_stage_dirs': 0,
            'orphan_stage_bytes': 0,
            'maintenance': self._empty_maintenance_result(),
            'partial_deletion_outcomes': [],
        }
    def _record_deleted_job(
        self,
        result: OfficeJobPurgeResult,
        job_id: str,
        logical_bytes: int,
        outcome: OfficeJobDeletionOutcome,
    ) -> None:
        if not outcome['removed'] or job_id in result['deleted_job_ids']:
            return
        result['deleted_jobs'] += 1
        result['deleted_job_ids'].append(job_id)
        result['freed_bytes'] += logical_bytes
        result['logical_artifact_freed_bytes'] += logical_bytes
        result['physical_deleted_bytes'] += outcome['physical_bytes']
    @staticmethod
    def _record_partial_deletion(
        result: OfficeJobPurgeResult,
        outcome: OfficeJobDeletionOutcome,
        replay_evidence: dict[str, Any] | None = None,
    ) -> None:
        if outcome['removed'] and not outcome['retry_required']:
            return
        result['partial_deletion_outcomes'].append(dict(outcome))
        if outcome['removed'] and replay_evidence is not None:
            evidence = dict(replay_evidence)
            evidence['entry_kind'] = outcome['entry_kind']
            evidence['parent_id'] = outcome['parent_id']
            scope = evidence.get('scope')
            if scope == 'job':
                evidence['source_parent'] = 'root'
                evidence['source_id'] = outcome['entry_id']
                evidence['source_operation'] = 'purge_expired'
            elif scope == 'quarantine':
                evidence['source_parent'] = 'quarantine'
                evidence['source_id'] = outcome['entry_id']
                evidence['source_operation'] = 'purge_expired_quarantine'
            result.setdefault('_replay_evidence', []).append(evidence)

    def _record_expired_quarantine_deletion(
        self,
        result: OfficeJobPurgeResult,
        quarantine_id: str,
        outcome: OfficeJobDeletionOutcome,
    ) -> None:
        if not outcome['removed'] or quarantine_id in result['expired_quarantine_ids']:
            return
        result['expired_quarantine_entries'] += 1
        result['expired_quarantine_bytes'] += outcome['physical_bytes']
        result['expired_quarantine_ids'].append(quarantine_id)
        result['maintenance']['expired_quarantine_entries'] = result['expired_quarantine_entries']
        result['maintenance']['expired_quarantine_bytes'] = result['expired_quarantine_bytes']

    def _record_quarantine_mutation(
        self,
        result: OfficeJobPurgeResult,
        outcome: OfficeJobQuarantineMutationOutcome,
    ) -> None:
        if not outcome['payload_remains_moved']:
            return
        metadata = outcome['metadata']
        job_id = str(metadata['job_id'])
        quarantine_id = outcome['quarantine_id']
        if job_id not in result['quarantined_job_ids']:
            result['quarantined_job_ids'].append(job_id)
            result['quarantined_bytes'] += outcome['physical_moved_bytes']
            result['logical_artifact_quarantined_bytes'] += outcome['logical_artifact_bytes']
            result['physical_quarantined_bytes'] += outcome['physical_moved_bytes']
        if quarantine_id not in result['quarantined_quarantine_ids']:
            result['quarantined_quarantine_ids'].append(quarantine_id)



    def purge_expired(self) -> OfficeJobPurgeResult:
        """관리자 purge는 lock teardown 실패 뒤에도 현재 partial result를 보존한다."""
        result = self._empty_purge_result()
        try:
            return self._purge_expired_locked(result)
        except OfficeJobPurgeError:
            raise
        except Exception as exc:
            raise OfficeJobPurgeError(result, exc) from exc

    def _purge_expired_locked(self, result: OfficeJobPurgeResult) -> OfficeJobPurgeResult:
        with self._maintenance_lock():
            try:
                self.last_maintenance = self._recovery_unlocked(result)
                result['maintenance'] = dict(self.last_maintenance)
                stale_bundles, stale_bytes = self._reconcile_stale_bundles_unlocked(result)
                self.last_maintenance['stale_bundles'] = stale_bundles
                self.last_maintenance['stale_bundle_bytes'] = stale_bytes
                result['stale_bundles'] = stale_bundles
                result['stale_bundle_bytes'] = stale_bytes
                expired_entries, expired_bytes = self._purge_expired_quarantine_unlocked(result)
                self.last_maintenance['expired_quarantine_entries'] = expired_entries
                self.last_maintenance['expired_quarantine_bytes'] = expired_bytes
                result['expired_quarantine_entries'] = expired_entries
                result['expired_quarantine_bytes'] = expired_bytes
                self._reconcile_quarantine_entries_unlocked()
                result['maintenance'] = dict(self.last_maintenance)
                result['orphan_stage_dirs'] = int(self.last_maintenance['orphan_stage_dirs'])
                result['orphan_stage_bytes'] = int(self.last_maintenance['orphan_stage_bytes'])
                cutoff = datetime.now(UTC) - timedelta(days=self.retention_days)

                for job_dir in self._job_entries():
                    job_id = job_dir.name
                    initial: dict[str, Any] | None = None
                    try:
                        indexed_owner = self._corrupt_record_owner_id(job_dir)
                        if not self._is_valid_job_dir(job_dir):
                            if indexed_owner is None:
                                self._quarantine_purge_job(result, job_dir, 'invalid job directory', 0)
                            else:
                                with self._owner_capacity_lock(indexed_owner):
                                    self._quarantine_purge_job(
                                        result,
                                        job_dir,
                                        'invalid job directory',
                                        0,
                                    )
                            continue
                        try:
                            initial = self._read_record(job_dir)
                            owner = self._owner_identity_for_valid_record(job_dir, initial)
                        except OfficeJobCorruptionError:
                            owner = self._corrupt_record_owner_id(job_dir)
                            logical_bytes = self._artifact_logical_size(initial) if initial is not None else 0
                            if owner is None:
                                self._quarantine_purge_job(
                                    result,
                                    job_dir,
                                    'invalid job metadata or artifacts',
                                    logical_bytes,
                                )
                            else:
                                with self._owner_capacity_lock(owner):
                                    self._quarantine_purge_job(
                                        result,
                                        job_dir,
                                        'invalid job metadata or artifacts',
                                        logical_bytes,
                                    )
                            continue

                        with self._owner_capacity_lock(owner):
                            try:
                                record = self._read_record(job_dir)
                                if self._owner_identity_for_valid_record(job_dir, record) != owner:
                                    raise OfficeJobCorruptionError([job_id])
                                logical_bytes = self._job_data_size(job_dir, record)
                            except OfficeJobCorruptionError:
                                self._quarantine_purge_job(
                                    result,
                                    job_dir,
                                    'invalid job metadata or artifacts',
                                    self._artifact_logical_size(initial),
                                )
                                continue

                            if self._record_timestamp(record) < cutoff:
                                try:
                                    self._prepare_owner_identity_cleanup_tombstone(
                                        job_id,
                                        owner,
                                        source_parent='root',
                                        source_id=job_id,
                                        source_operation='purge_expired',
                                    )
                                    replay_evidence = self._replay_evidence(
                                        scope='job',
                                        entry=job_dir,
                                        operation='purge_expired',
                                        job_id=job_id,
                                        owner_id=owner,
                                    )
                                    outcome = self._safe_delete_job_dir(job_dir)
                                except OfficeJobDeletionError as exc:
                                    self._record_deleted_job(result, job_id, logical_bytes, exc.outcome)
                                    self._record_partial_deletion(
                                        result,
                                        exc.outcome,
                                        replay_evidence,
                                    )
                                    raise
                                self._record_deleted_job(result, job_id, logical_bytes, outcome)
                                self._record_partial_deletion(
                                    result,
                                    outcome,
                                    replay_evidence,
                                )
                                self._remove_owner_identity_after_resolution(job_id)
                    except Exception:
                        if (
                            job_id not in result['deleted_job_ids']
                            and job_id not in result['quarantined_job_ids']
                        ):
                            result['failed_job_ids'].append(job_id)
                        raise

                result['quarantine_bytes'] = self._quarantine_usage_bytes_unlocked()
                result['temporary_bundle_bytes'] = self._temporary_bundle_usage_bytes_unlocked()
                return result
            except OfficeJobPurgeError:
                raise
            except Exception as exc:
                try:
                    result['quarantine_bytes'] = self._quarantine_usage_bytes_unlocked()
                    result['temporary_bundle_bytes'] = self._temporary_bundle_usage_bytes_unlocked()
                except OSError as accounting_exc:
                    raise OfficeJobPurgeError(result, exc) from accounting_exc
                raise OfficeJobPurgeError(result, exc) from exc

    def write_text(self, job_id: str, filename: str, text: str, media_type: str) -> Path:
        return self.write_bytes(job_id, filename, text.encode('utf-8'), media_type)

    def write_bytes(self, job_id: str, filename: str, data: bytes, media_type: str) -> Path:
        job_dir = self.job_dir(job_id)
        initial = self._read_record(job_dir)
        artifact_name = safe_name(filename)
        if artifact_name == 'job.json':
            raise ValueError('job metadata cannot be replaced by an artifact')

        with self._maintenance_lock():
            owner = self._owner_identity_for_valid_record(job_dir, initial)
            with self._owner_capacity_lock(owner):
                record = self._read_record(job_dir)
                if self._owner_identity_for_valid_record(job_dir, record) != owner:
                    raise OfficeJobCorruptionError([job_id])
                path = job_dir / artifact_name
                if path.is_symlink() or path.is_dir() or (path.exists() and not path.is_file()):
                    raise FileNotFoundError(artifact_name)
                old_size = path.stat().st_size if path.is_file() else 0
                self._ensure_capacity(
                    owner,
                    jobs_to_add=0,
                    bytes_to_add=len(data) - old_size,
                    temporary_write_bytes=len(data),
                )
                stage_id = f'artifact-{uuid.uuid4().hex}'
                stage_dir = self._staging_root / stage_id
                stage_dir.mkdir(parents=False, exist_ok=False)
                self._fsync_directory(self._staging_root)
                staged_path = stage_dir / 'new'
                backup_path = stage_dir / 'backup'
                journal: dict[str, Any] | None = None
                updated: dict[str, Any] | None = None
                try:
                    self._write_bytes_durable(staged_path, data)
                    artifact = self._artifact_metadata(job_id, artifact_name, media_type, staged_path)
                    updated = self._record_with_artifact(record, artifact)
                    journal = {
                        'version': 1,
                        'operation': 'artifact_replace',
                        'phase': 'prepared',
                        'job_id': job_id,
                        'stage_id': stage_id,
                        'artifact_name': artifact_name,
                        'old_record': record,
                        'new_record': updated,
                    }
                    self._write_journal(stage_id, journal)
                    if path.exists():
                        path.replace(backup_path)
                        self._fsync_directory(job_dir)
                        self._fsync_directory(stage_dir)
                    journal['phase'] = 'backup_created'
                    self._write_journal(stage_id, journal)
                    staged_path.replace(path)
                    self._fsync_directory(job_dir)
                    journal['phase'] = 'artifact_published'
                    self._write_journal(stage_id, journal)
                    self._write_record(job_dir, updated)
                    journal['phase'] = 'manifest_committed'
                    self._write_journal(stage_id, journal)
                except Exception as exc:
                    if journal is None:
                        self._preserve_unresolved_recovery(
                            None,
                            stage_id,
                            f'artifact transaction failed before journal: {exc.__class__.__name__}: {exc}',
                        )
                    else:
                        try:
                            self._rollback_artifact_transaction(journal)
                        except Exception as rollback_exc:
                            self._preserve_unresolved_recovery(
                                self._existing_journal_path(stage_id),
                                stage_id,
                                f'artifact rollback failed: {rollback_exc.__class__.__name__}: {rollback_exc}',
                            )
                            raise
                    raise exc
                try:
                    if updated is None or not self._active_record_matches(job_dir, updated):
                        raise OfficeJobCorruptionError([job_id])
                    self._remove_stage_dir(stage_dir)
                    self._remove_journal(stage_id)
                except Exception as exc:
                    self._preserve_unresolved_recovery(
                        self._existing_journal_path(stage_id),
                        stage_id,
                        f'artifact commit cleanup failed: {exc.__class__.__name__}: {exc}',
                    )
                    raise
        return path

    def complete(self, job_id: str, warnings: list[str] | None = None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        if extra is not None and not isinstance(extra, dict):
            raise ValueError('complete extra must be an object')
        reserved = sorted(set(extra or {}).intersection(_RESERVED_COMPLETE_FIELDS))
        if reserved:
            raise ValueError(f'complete extra cannot overwrite reserved fields: {", ".join(reserved)}')

        with self._maintenance_lock():
            job_dir = self.job_dir(job_id)
            initial = self._read_record(job_dir)
            owner = self._owner_identity_for_valid_record(job_dir, initial)
            with self._owner_capacity_lock(owner):
                record = self._read_record(job_dir)
                if self._owner_identity_for_valid_record(job_dir, record) != owner:
                    raise OfficeJobCorruptionError([job_id])
                updated = {
                    **record,
                    'status': 'completed',
                    'updated_at': _now_iso(),
                    'warnings': list(dict.fromkeys([*record['warnings'], *(warnings or [])])),
                    **(extra or {}),
                }
                self._write_record(job_dir, updated)
        return updated

    def fail(self, job_id: str, error: str, warnings: list[str] | None = None) -> dict[str, Any]:
        with self._maintenance_lock():
            job_dir = self.job_dir(job_id)
            initial = self._read_record(job_dir)
            owner = self._owner_identity_for_valid_record(job_dir, initial)
            with self._owner_capacity_lock(owner):
                record = self._read_record(job_dir)
                if self._owner_identity_for_valid_record(job_dir, record) != owner:
                    raise OfficeJobCorruptionError([job_id])
                updated = {
                    **record,
                    'status': 'failed',
                    'updated_at': _now_iso(),
                    'error': error[:4000],
                    'warnings': list(dict.fromkeys([*record['warnings'], *(warnings or [])])),
                }
                self._write_record(job_dir, updated)
        return updated

    def artifact_path(self, job_id: str, filename: str) -> Path:
        with self._maintenance_lock():
            job_dir = self.job_dir(job_id)
            initial = self._read_record(job_dir)
            owner = self._owner_identity_for_valid_record(job_dir, initial)
            with self._owner_capacity_lock(owner):
                record = self._read_record(job_dir)
                if self._owner_identity_for_valid_record(job_dir, record) != owner:
                    raise OfficeJobCorruptionError([job_id])
                artifact_name = safe_name(filename)
                if artifact_name == 'job.json' or artifact_name.startswith(_TEMP_FILE_PREFIX):
                    raise FileNotFoundError(filename)
                artifact = next(
                    (item for item in record['artifacts'] if item['filename'] == artifact_name),
                    None,
                )
                if artifact is None:
                    raise FileNotFoundError(filename)
                return self._validated_artifact_path(job_dir, record['job_id'], artifact)
    def open_artifact_read_lease(
        self,
        job_id: str,
        filename: str,
        owner_id: int,
    ) -> OfficeJobArtifactReadLease:
        """검증 중인 RLock은 즉시 놓고 worker가 해제할 per-job file lease만 반환한다."""
        owner = strict_owner_id(owner_id)
        handle: BinaryIO | None = None
        lock_handle: BinaryIO | None = None
        try:
            with self._maintenance_lock():
                job_dir = self.job_dir(job_id)
                initial = self._read_record(job_dir)
                if self._owner_identity_for_valid_record(job_dir, initial) != owner:
                    raise PermissionError('job belongs to another user')
                with self._owner_capacity_lock(owner):
                    record = self._read_record(job_dir)
                    if self._owner_identity_for_valid_record(job_dir, record) != owner:
                        raise OfficeJobCorruptionError([job_id])
                    artifact_name = safe_name(filename)
                    if artifact_name == 'job.json' or artifact_name.startswith(_TEMP_FILE_PREFIX):
                        raise FileNotFoundError(filename)
                    artifact = next(
                        (item for item in record['artifacts'] if item['filename'] == artifact_name),
                        None,
                    )
                    if artifact is None:
                        raise FileNotFoundError(filename)
                    path = self._validated_artifact_path(job_dir, record['job_id'], artifact)
                    handle = self._open_file_no_follow(path)
                    if not self._artifact_handle_matches(handle, artifact):
                        raise OfficeJobCorruptionError([job_id])
                    lock_handle = self._acquire_job_read_lease_lock(job_id)
            if handle is None or lock_handle is None:
                raise RuntimeError('artifact read lease was not acquired')
            return OfficeJobArtifactReadLease(
                handle,
                filename=artifact_name,
                media_type=artifact['media_type'],
                size_bytes=artifact['size_bytes'],
                lock_handle=lock_handle,
            )
        except BaseException as exc:
            teardown_errors: list[BaseException] = []
            if lock_handle is not None:
                try:
                    self._unlock_file(lock_handle)
                except BaseException as teardown_exc:
                    teardown_errors.append(teardown_exc)
                try:
                    lock_handle.close()
                except BaseException as teardown_exc:
                    teardown_errors.append(teardown_exc)
            if handle is not None:
                try:
                    handle.close()
                except BaseException as teardown_exc:
                    teardown_errors.append(teardown_exc)
            for teardown_exc in teardown_errors:
                exc.add_note(
                    'artifact read lease acquisition teardown failed: '
                    f'{teardown_exc.__class__.__name__}: {teardown_exc}'
                )
            raise

    def create_temporary_bundle(self, job_id: str, *, bundle_id: str | None = None) -> Path:
        """동일 볼륨의 관리 루트에 manifest 산출물만 담은 비영구 bundle을 생성한다."""
        resolved_bundle_id = bundle_id or uuid.uuid4().hex
        if re.fullmatch(r'[0-9a-f]{32}', resolved_bundle_id) is None:
            raise ValueError('temporary bundle id is invalid')
        job_dir = self.job_dir(job_id)
        initial = self._read_record(job_dir)
        with self._maintenance_lock():
            owner = self._owner_identity_for_valid_record(job_dir, initial)
            with self._owner_capacity_lock(owner):
                record = self._read_record(job_dir)
                if self._owner_identity_for_valid_record(job_dir, record) != owner:
                    raise OfficeJobCorruptionError([job_id])
                self._job_data_size(job_dir, record)
                artifact_paths = [
                    self._validated_artifact_path(job_dir, record['job_id'], artifact)
                    for artifact in record['artifacts']
                ]
                reserved_bytes = self._temporary_bundle_upper_bound(artifact_paths)
                self._ensure_temporary_bundle_capacity(reserved_bytes)
                bundle = self._bundles_root / f'bundle-{resolved_bundle_id}.zip'
                if self._entry_exists_no_follow(bundle):
                    raise FileExistsError(f'temporary bundle already exists: {resolved_bundle_id}')
                fd, tmp_name = tempfile.mkstemp(
                    prefix=_TEMP_FILE_PREFIX,
                    suffix='.zip',
                    dir=self._bundles_root,
                )
                os.close(fd)
                staged_bundle = Path(tmp_name)
                published = False
                try:
                    with zipfile.ZipFile(staged_bundle, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                        for path in artifact_paths:
                            archive.write(path, arcname=path.name)
                    self._fsync_file(staged_bundle)
                    measured_bytes = staged_bundle.stat().st_size
                    self._verify_temporary_bundle_capacity_after_write(measured_bytes, reserved_bytes)
                    staged_bundle.replace(bundle)
                    published = True
                    self._fsync_directory(self._bundles_root)
                except Exception:
                    staged_bundle.unlink(missing_ok=True)
                    if published:
                        bundle.unlink(missing_ok=True)
                    self._fsync_directory(self._bundles_root)
                    raise
        return bundle


    def delete_temporary_bundle(self, path: Path) -> OfficeJobDeletionOutcome | None:
        """Retain cleanup evidence even when a response background task cannot surface it."""
        try:
            candidate = Path(path).resolve(strict=False)
        except OSError:
            return None
        if candidate.parent != self._bundles_root or not _BUNDLE_NAME.fullmatch(candidate.name):
            return None
        outcome: OfficeJobDeletionOutcome | None = None
        try:
            with self._maintenance_lock():
                if not self._entry_exists_no_follow(candidate):
                    outcome = {
                        'entry_id': candidate.name,
                        'entry_kind': 'temporary_bundle',
                        'parent_id': 'bundles',
                        'physical_bytes': 0,
                        'partial_bytes_removed': 0,
                        'removed': True,
                        'durably_synced': False,
                        'durability': 'pending',
                        'retry_required': True,
                    }
                    self._apply_directory_sync_outcome(outcome, self._bundles_root)
                    return outcome
                if candidate.is_symlink() or not candidate.is_file():
                    raise OfficeJobCorruptionError([candidate.name])
                outcome = self._safe_delete_managed_file(
                    candidate,
                    self._bundles_root,
                    candidate.name,
                    entry_kind='temporary_bundle',
                    parent_id='bundles',
                )
                return outcome
        except OfficeJobDeletionError:
            raise
        except Exception as exc:
            if outcome is not None:
                raise OfficeJobDeletionError(outcome, exc) from exc
            raise
    def delete_temporary_bundle_outcome(
        self,
        bundle_id: str,
    ) -> OfficeJobDeletionOutcome | None:
        """Delete one canonical temporary bundle and preserve its typed outcome."""
        if re.fullmatch(r'[0-9a-f]{32}', bundle_id) is None:
            raise ValueError('temporary bundle id is invalid')
        return self.delete_temporary_bundle(
            self._bundles_root / f'bundle-{bundle_id}.zip'
        )
    def temporary_bundle_replay_evidence(self, bundle_id: str) -> dict[str, Any]:
        """Capture a deterministic bundle's exact identity before cleanup unlinks it."""
        if re.fullmatch(r'[0-9a-f]{32}', bundle_id) is None:
            raise ValueError('temporary bundle id is invalid')
        target_id = f'bundle-{bundle_id}.zip'
        with self._maintenance_lock():
            entry = self._bundles_root / target_id
            if not self._entry_exists_no_follow(entry):
                raise FileNotFoundError('temporary bundle is unavailable for replay binding')
            if entry.is_symlink() or not entry.is_file():
                raise OfficeJobCorruptionError([target_id])
            return self._replay_evidence(
                scope='bundles',
                entry=entry,
                operation='bundle_cleanup',
                target_id=target_id,
            )
    def delete_temporary_bundle_with_replay_evidence(
        self,
        bundle_id: str,
        replay_evidence: object,
    ) -> OfficeJobDeletionOutcome:
        """Delete only the deterministic bundle whose bound evidence still matches."""
        if re.fullmatch(r'[0-9a-f]{32}', bundle_id) is None:
            raise ValueError('temporary bundle id is invalid')
        outcome: OfficeJobDeletionOutcome | None = None
        try:
            with self._maintenance_lock():
                entry, evidence = self._temporary_bundle_replay_entry(
                    bundle_id,
                    replay_evidence,
                )
                if not self._entry_exists_no_follow(entry):
                    outcome = {
                        'entry_id': entry.name,
                        'entry_kind': 'temporary_bundle',
                        'parent_id': 'bundles',
                        'physical_bytes': 0,
                        'partial_bytes_removed': 0,
                        'removed': True,
                        'durably_synced': False,
                        'durability': 'pending',
                        'retry_required': True,
                    }
                    self._apply_directory_sync_outcome(outcome, self._bundles_root)
                    return outcome
                if not self._replay_entry_matches_identity(entry, evidence['identity']):
                    raise OfficeJobCorruptionError([entry.name])
                outcome = self._safe_delete_managed_file(
                    entry,
                    self._bundles_root,
                    entry.name,
                    entry_kind='temporary_bundle',
                    parent_id='bundles',
                )
                return outcome
        except OfficeJobDeletionError:
            raise
        except Exception as exc:
            if outcome is not None:
                raise OfficeJobDeletionError(outcome, exc) from exc
            raise
    def _replay_evidence_entry(self, evidence: object) -> tuple[str, Path, dict[str, Any]]:
        if not isinstance(evidence, dict):
            raise ValueError('replay evidence is invalid')
        scope = evidence.get('scope')
        name = evidence.get('name')
        operation = evidence.get('operation')
        identity = evidence.get('identity')
        signature = evidence.get('signature')
        target_sha256 = evidence.get('target_sha256')
        if not isinstance(scope, str) or not isinstance(name, str) or not isinstance(operation, str):
            raise ValueError('replay evidence is invalid')
        roots = {
            'bundles': self._bundles_root,
            'quarantine': self._quarantine_root,
            'recovery_quarantine': self._recovery_quarantine_root,
            'owner_identities': self._owner_identities_root,
            'job': self.root,
        }
        root = roots.get(scope)
        if scope == 'job_temp':
            job_id = evidence.get('job_id')
            if not isinstance(job_id, str) or _JOB_ID.fullmatch(job_id) is None:
                raise ValueError('replay evidence scope is invalid')
            root = self.root / job_id
        if root is None:
            raise ValueError('replay evidence scope is invalid')
        corrupt_disposition = operation.endswith('_corrupt_disposition')
        if (
            Path(name).name != name
            or not name
            or (
                scope == 'bundles'
                and not (_BUNDLE_NAME.fullmatch(name) or name.startswith(_TEMP_FILE_PREFIX))
            )
            or (
                scope in {'quarantine', 'recovery_quarantine'}
                and not corrupt_disposition
                and _TRANSACTION_ID.fullmatch(name) is None
            )
            or (
                scope == 'owner_identities'
                and not corrupt_disposition
                and (not name.endswith('.json') or _JOB_ID.fullmatch(name[:-5]) is None)
            )
            or signature is not None
            and signature != identity
            or scope == 'job'
            and _JOB_ID.fullmatch(name) is None
            or scope == 'job_temp'
            and not name.startswith(_TEMP_FILE_PREFIX)
            or not isinstance(identity, dict)
            or target_sha256 is not None
            and (not isinstance(target_sha256, str) or _SHA256.fullmatch(target_sha256) is None)
        ):
            raise ValueError('replay evidence identity is invalid')
        return scope, root / name, evidence

    def _safe_delete_replay_evidence(
        self,
        scope: str,
        entry: Path,
        evidence: dict[str, Any],
    ) -> None:
        operation = evidence['operation']
        if not self._replay_entry_matches_identity(entry, evidence['identity']):
            raise OfficeJobCorruptionError([entry.name])
        if scope == 'recovery_quarantine' and operation == 'recovery_delete':
            self._safe_delete_recovery_entry(entry)
            return
        if scope == 'quarantine' and operation in {
            'quarantine_delete',
            'quarantine_restore',
            'purge_expired_quarantine',
        }:
            self._safe_delete_quarantine_entry(entry)
            return
        if scope == 'job':
            self._safe_delete_job_dir(entry)
            return
        if scope == 'job_temp':
            if self._entry_exists_no_follow(entry.parent):
                parent_identity = evidence.get('parent_identity')
                if not self._job_parent_matches_replay_identity(entry.parent, parent_identity):
                    raise OfficeJobCorruptionError([entry.parent.name])
            self._safe_delete_managed_file(
                entry,
                entry.parent,
                entry.name,
                entry_kind='orphan_temp',
                parent_id=str(evidence['job_id']),
            )
            return
        if scope == 'bundles':
            self._safe_delete_managed_file(
                entry,
                self._bundles_root,
                entry.name,
                entry_kind='stale_bundle' if _BUNDLE_NAME.fullmatch(entry.name) else 'orphan_temp',
                parent_id='bundles',
            )
            return
        root = {
            'quarantine': self._quarantine_root,
            'recovery_quarantine': self._recovery_quarantine_root,
            'owner_identities': self._owner_identities_root,
        }.get(scope)
        if root is None:
            raise ValueError('replay evidence scope is invalid')
        self._safe_delete_corrupt_evidence_child(root, entry, f'replay-{scope}-{entry.name}')

    def _confirm_replay_evidence_absence(self, evidence: object) -> tuple[str, Path, dict[str, Any]]:
        scope, entry, parsed = self._replay_evidence_entry(evidence)
        if scope == 'job_temp' and self._entry_exists_no_follow(entry.parent):
            if not self._is_valid_job_dir(entry.parent):
                raise OfficeJobCorruptionError([entry.parent.name])
            record = self._read_record(entry.parent)
            self._job_data_size(entry.parent, record)
            parent_identity = parsed.get('parent_identity')
            if not self._job_parent_matches_replay_identity(entry.parent, parent_identity):
                raise OfficeJobCorruptionError([entry.parent.name])
        if self._entry_exists_no_follow(entry):
            self._safe_delete_replay_evidence(scope, entry, parsed)
        if self._entry_exists_no_follow(entry):
            raise OSError(f'replay target remains present: {entry.name}')
        parent = self.root if scope == 'job_temp' and not self._entry_exists_no_follow(entry.parent) else entry.parent
        self._apply_directory_sync_outcome(parsed, parent)
        if self._entry_exists_no_follow(entry):
            raise OSError(f'replay target reappeared: {entry.name}')
        return scope, entry, parsed

    def _quarantine_replay_facts(
        self,
        evidence: dict[str, Any],
    ) -> tuple[str, int, int, int, dict[str, Any]]:
        """Require immutable pre-mutation quarantine facts before absent-entry recovery."""
        job_id = evidence.get('job_id')
        owner_id = evidence.get('owner_id')
        logical_bytes = evidence.get('logical_bytes')
        physical_bytes = evidence.get('physical_bytes')
        identity = evidence.get('identity')
        payload_identity = evidence.get('payload_identity')
        if (
            not isinstance(job_id, str)
            or _JOB_ID.fullmatch(job_id) is None
            or isinstance(owner_id, bool)
            or not isinstance(owner_id, int)
            or isinstance(logical_bytes, bool)
            or not isinstance(logical_bytes, int)
            or logical_bytes < 0
            or isinstance(physical_bytes, bool)
            or not isinstance(physical_bytes, int)
            or physical_bytes < 0
            or not isinstance(identity, dict)
            or identity.get('kind') != 'directory'
            or isinstance(identity.get('size_bytes'), bool)
            or not isinstance(identity.get('size_bytes'), int)
            or identity['size_bytes'] < 0
            or identity['size_bytes'] != physical_bytes
            or not isinstance(identity.get('sha256'), str)
            or _SHA256.fullmatch(identity['sha256']) is None
            or not isinstance(payload_identity, dict)
            or payload_identity.get('kind') != 'directory'
            or isinstance(payload_identity.get('size_bytes'), bool)
            or not isinstance(payload_identity.get('size_bytes'), int)
            or payload_identity['size_bytes'] < 0
            or payload_identity['size_bytes'] > physical_bytes
            or not isinstance(payload_identity.get('sha256'), str)
            or _SHA256.fullmatch(payload_identity['sha256']) is None
        ):
            raise ValueError('quarantine replay evidence is invalid')
        return job_id, strict_owner_id(owner_id), logical_bytes, physical_bytes, payload_identity

    def _validate_replayed_quarantine_restore(
        self,
        outcome: dict[str, Any],
        evidence: dict[str, Any],
    ) -> None:
        job_id, owner_id, logical_bytes, physical_bytes, payload_identity = (
            self._quarantine_replay_facts(evidence)
        )
        if (
            outcome.get('job_id') != job_id
            or outcome.get('owner_id') != owner_id
            or outcome.get('logical_bytes') != logical_bytes
            or outcome.get('physical_bytes') != physical_bytes
            or outcome.get('published') is not True
        ):
            raise ValueError('quarantine restore replay identity is invalid')
        job_dir = self.root / job_id
        if not self._is_valid_job_dir(job_dir):
            raise OfficeJobCorruptionError([job_id])
        record = self._read_record(job_dir)
        if (
            strict_owner_id(record['owner_id']) != owner_id
            or self._job_data_size(job_dir, record) != logical_bytes
            or not self._replay_entry_matches_identity(job_dir, payload_identity)
        ):
            raise OfficeJobCorruptionError([job_id])
        self._fsync_directory(self.root)

    def _validate_direct_replay_binding(
        self,
        outcome: dict[str, Any],
        scope: str,
        evidence: dict[str, Any],
    ) -> str:
        operation = outcome.get('operation')
        target_id = outcome.get('target_id')
        expected_scopes = {
            'recovery_delete': 'recovery_quarantine',
            'quarantine_delete': 'quarantine',
            'quarantine_restore': 'quarantine',
            'quarantine_corrupt_disposition': 'quarantine',
            'recovery_corrupt_disposition': 'recovery_quarantine',
            'owner_identity_corrupt_disposition': 'owner_identities',
        }
        if (
            not isinstance(operation, str)
            or not isinstance(target_id, str)
            or not target_id
            or evidence.get('operation') != operation
            or expected_scopes.get(operation) != scope
        ):
            raise ValueError('direct mutation replay operation is invalid')
        target_sha256 = evidence.get('target_sha256')
        if (
            not isinstance(target_sha256, str)
            or _SHA256.fullmatch(target_sha256) is None
            or target_sha256 != self._replay_target_digest(target_id)
        ):
            raise ValueError('direct mutation replay target is invalid')
        if operation in {'recovery_delete', 'quarantine_delete', 'quarantine_restore'}:
            if evidence.get('name') != target_id:
                raise ValueError('direct mutation replay target is invalid')
        return operation

    def _temporary_bundle_replay_entry(
        self,
        bundle_id: str,
        replay_evidence: object,
    ) -> tuple[Path, dict[str, Any]]:
        target_id = f'bundle-{bundle_id}.zip'
        scope, entry, evidence = self._replay_evidence_entry(replay_evidence)
        if (
            scope != 'bundles'
            or evidence.get('operation') != 'bundle_cleanup'
            or evidence.get('name') != target_id
            or evidence.get('target_sha256') != self._replay_target_digest(target_id)
        ):
            raise ValueError('temporary bundle replay identity is invalid')
        return entry, evidence

    def validate_temporary_bundle_replay_evidence(
        self,
        bundle_id: str,
        replay_evidence: object,
    ) -> None:
        """Reject a deterministic bundle replacement before cleanup can unlink it."""
        if re.fullmatch(r'[0-9a-f]{32}', bundle_id) is None:
            raise ValueError('temporary bundle id is invalid')
        with self._maintenance_lock():
            entry, evidence = self._temporary_bundle_replay_entry(bundle_id, replay_evidence)
            if self._entry_exists_no_follow(entry) and not self._replay_entry_matches_identity(
                entry,
                evidence['identity'],
            ):
                raise OfficeJobCorruptionError([entry.name])
    def reconcile_temporary_bundle_durability(
        self,
        outcome: dict[str, Any],
        replay_evidence: object | None = None,
    ) -> OfficeJobDeletionOutcome:
        """Confirm deterministic bundle absence from its pre-delete identity."""
        if replay_evidence is None:
            raise ValueError('temporary bundle replay evidence is missing')
        entry_id = outcome.get('entry_id')
        if (
            not isinstance(entry_id, str)
            or _BUNDLE_NAME.fullmatch(entry_id) is None
            or outcome.get('entry_kind') != 'temporary_bundle'
            or outcome.get('parent_id') != 'bundles'
            or outcome.get('removed') is not True
            or outcome.get('durably_synced') is not False
        ):
            raise ValueError('temporary bundle replay outcome is invalid')
        with self._maintenance_lock():
            bundle_id = entry_id[len('bundle-') : -len('.zip')]
            _entry, evidence = self._temporary_bundle_replay_entry(
                bundle_id,
                replay_evidence,
            )
            self._confirm_replay_evidence_absence(evidence)
        confirmed: OfficeJobDeletionOutcome = dict(outcome)
        confirmed['removed'] = True
        confirmed['durably_synced'] = True
        confirmed['durability'] = 'synced'
        confirmed['retry_required'] = False
        return confirmed

    def reconcile_direct_mutation_durability(
        self,
        outcome: dict[str, Any],
        replay_evidence: object | None = None,
        *,
        receipt_target_id: str | None = None,
    ) -> None:
        """Confirm exact pre-recorded target absence before acknowledging a direct mutation."""
        if outcome.get('removed') is not True or outcome.get('durably_synced') is not False:
            return
        if replay_evidence is None:
            raise ValueError('direct mutation replay evidence is missing')
        with self._maintenance_lock():
            scope, _entry, evidence = self._replay_evidence_entry(replay_evidence)
            operation = self._validate_direct_replay_binding(outcome, scope, evidence)
            if receipt_target_id is not None and outcome.get('target_id') != receipt_target_id:
                raise ValueError('direct mutation receipt target is invalid')
            quarantine_delete_facts: tuple[str, int, int, int, dict[str, Any]] | None = None
            if operation == 'quarantine_restore':
                self._validate_replayed_quarantine_restore(outcome, evidence)
            elif operation == 'quarantine_delete':
                quarantine_delete_facts = self._quarantine_replay_facts(evidence)
                job_id, owner_id, logical_bytes, physical_bytes, _payload_identity = (
                    quarantine_delete_facts
                )
                if (
                    outcome.get('job_id') != job_id
                    or outcome.get('owner_id') != owner_id
                    or outcome.get('logical_bytes') != logical_bytes
                    or outcome.get('physical_bytes') != physical_bytes
                ):
                    raise ValueError('quarantine deletion replay identity is invalid')
            confirmed_scope, _confirmed_entry, _confirmed = self._confirm_replay_evidence_absence(
                evidence
            )
            outcome['durably_synced'] = _confirmed.get('durability') != 'platform_best_effort'
            outcome['durability'] = _confirmed.get('durability', 'synced')
            outcome['retry_required'] = outcome['durability'] == 'pending'
            if confirmed_scope == 'quarantine' and operation == 'quarantine_delete':
                if quarantine_delete_facts is None:
                    raise ValueError('quarantine deletion replay identity is invalid')
                job_id, owner_id, _logical_bytes, _physical_bytes, _payload_identity = (
                    quarantine_delete_facts
                )
                self._prepare_owner_identity_cleanup_tombstone(
                    job_id,
                    owner_id,
                    source_parent='quarantine',
                    source_id=str(outcome.get('target_id')),
                    source_operation='quarantine_delete',
                )
                self._remove_owner_identity_after_resolution(job_id)
            self._reconcile_owner_deletion_tombstones_unlocked()


    def recover_direct_mutation_outcome(
        self,
        *,
        action: str,
        target_id: str,
        replay_evidence: object,
    ) -> OfficeJobDirectMutationOutcome:
        """Resume a phase-one direct mutation from exact persisted replay evidence."""
        action_operations = {
            'office_jobs.recovery.delete': {'recovery_delete'},
            'office_jobs.quarantine.restore': {'quarantine_restore'},
            'office_jobs.quarantine.delete': {'quarantine_delete'},
            'office_jobs.evidence.dispose': {
                'quarantine_corrupt_disposition',
                'recovery_corrupt_disposition',
                'owner_identity_corrupt_disposition',
            },
        }
        allowed = action_operations.get(action)
        if allowed is None:
            raise ValueError('direct mutation recovery action is invalid')
        with self._maintenance_lock():
            scope, entry, evidence = self._replay_evidence_entry(replay_evidence)
            operation = evidence.get('operation')
            if operation not in allowed:
                raise ValueError('direct mutation recovery evidence operation is invalid')
            quarantine_facts = (
                self._quarantine_replay_facts(evidence)
                if operation in {'quarantine_delete', 'quarantine_restore'}
                else None
            )
            job_id = (
                quarantine_facts[0]
                if quarantine_facts is not None
                else evidence.get('job_id')
                if isinstance(evidence.get('job_id'), str)
                else None
            )
            owner_id = (
                quarantine_facts[1]
                if quarantine_facts is not None
                else strict_owner_id(evidence['owner_id'])
                if 'owner_id' in evidence
                else None
            )
            logical_bytes = quarantine_facts[2] if quarantine_facts is not None else 0
            physical_bytes = (
                quarantine_facts[3]
                if quarantine_facts is not None
                else int(evidence['identity']['size_bytes'])
            )
            outcome: OfficeJobDirectMutationOutcome = {
                'operation': str(operation),
                'target_id': target_id,
                'management_token': target_id if action == 'office_jobs.evidence.dispose' else None,
                'job_id': job_id,
                'owner_id': owner_id,
                'logical_bytes': logical_bytes,
                'physical_bytes': physical_bytes,
                'partial_bytes_removed': 0,
                'published': False,
                'removed': False,
                'durably_synced': False,
                'durability': 'pending',
                'retry_required': True,
            }
            self._validate_direct_replay_binding(outcome, scope, evidence)
            if self._entry_exists_no_follow(entry):
                if not self._replay_entry_matches_identity(entry, evidence['identity']):
                    raise OfficeJobCorruptionError([entry.name])
                if operation == 'recovery_delete':
                    item = self._recovery_item_from_entry(entry)
                    return self._delete_recovery_outcome_unlocked(target_id, entry, item)
                if operation == 'quarantine_restore':
                    return self._restore_quarantine_outcome_unlocked(target_id)[1]
                if operation == 'quarantine_delete':
                    item = self._quarantine_item_from_entry(entry)
                    if item.get('kind') != 'quarantine':
                        raise OfficeJobCorruptionError([target_id])
                    return self._delete_quarantine_outcome_unlocked(target_id, entry, item)
                deletion = self._safe_delete_corrupt_evidence_child(
                    {
                        'quarantine': self._quarantine_root,
                        'recovery_quarantine': self._recovery_quarantine_root,
                        'owner_identities': self._owner_identities_root,
                    }[scope],
                    entry,
                    target_id,
                )
                outcome['physical_bytes'] = deletion['physical_bytes']
                outcome['partial_bytes_removed'] = deletion['partial_bytes_removed']
                outcome['removed'] = deletion['removed']
                outcome['durably_synced'] = deletion['durably_synced']
                outcome['durability'] = deletion.get('durability', 'synced' if deletion['durably_synced'] else 'platform_best_effort')
                outcome['retry_required'] = deletion.get('retry_required', False)
                return outcome
            if operation == 'quarantine_restore':
                outcome['published'] = True
                self._validate_replayed_quarantine_restore(outcome, evidence)
                if quarantine_facts is None:
                    raise ValueError('quarantine restore replay identity is invalid')
                outcome['partial_bytes_removed'] = (
                    outcome['physical_bytes'] - quarantine_facts[4]['size_bytes']
                )
            elif operation == 'quarantine_delete':
                if quarantine_facts is None:
                    raise ValueError('quarantine deletion replay identity is invalid')
                job_id, owner_id, logical_bytes, physical_bytes, _payload_identity = quarantine_facts
                if (
                    outcome['job_id'] != job_id
                    or outcome['owner_id'] != owner_id
                    or outcome['logical_bytes'] != logical_bytes
                    or outcome['physical_bytes'] != physical_bytes
                ):
                    raise ValueError('quarantine deletion replay identity is invalid')
                self._prepare_owner_identity_cleanup_tombstone(
                    job_id,
                    owner_id,
                    source_parent='quarantine',
                    source_id=target_id,
                    source_operation='quarantine_delete',
                )
                self._remove_owner_identity_after_resolution(job_id)
            elif action == 'office_jobs.evidence.dispose':
                pass
            elif operation != 'recovery_delete':
                raise ValueError('direct mutation recovery operation is invalid')
            outcome['removed'] = True
            if operation != 'quarantine_restore':
                outcome['partial_bytes_removed'] = outcome['physical_bytes']
            self._apply_directory_sync_outcome(outcome, entry.parent)
            if outcome['durability'] == 'platform_best_effort':
                outcome['durably_synced'] = False
            self._reconcile_owner_deletion_tombstones_unlocked()
            return outcome
    def reconcile_purge_partial_durability(
        self,
        partial_result: dict[str, Any],
        replay_evidence: object | None = None,
    ) -> None:
        """Confirm each exact pre-recorded purge target before acknowledging its receipt."""
        outcomes = partial_result.get('partial_deletion_outcomes')
        if not isinstance(outcomes, list) or not isinstance(replay_evidence, list):
            raise ValueError('purge durability replay is invalid')
        evidence_by_target: dict[tuple[str, str, str], dict[str, Any]] = {}
        for evidence in replay_evidence:
            _scope, entry, parsed = self._replay_evidence_entry(evidence)
            entry_kind = parsed.get('entry_kind')
            parent_id = parsed.get('parent_id')
            if not isinstance(entry_kind, str) or not isinstance(parent_id, str):
                raise ValueError('purge replay evidence is invalid')
            key = (entry.name, entry_kind, parent_id)
            if key in evidence_by_target:
                raise ValueError('purge replay evidence is ambiguous')
            evidence_by_target[key] = parsed
        with self._maintenance_lock():
            for outcome in outcomes:
                if not isinstance(outcome, dict):
                    raise ValueError('purge durability replay is invalid')
                if outcome.get('removed') is not True or outcome.get('durably_synced') is not False:
                    continue
                entry_id = outcome.get('entry_id')
                entry_kind = outcome.get('entry_kind')
                parent_id = outcome.get('parent_id')
                if not all(isinstance(value, str) for value in (entry_id, entry_kind, parent_id)):
                    raise ValueError('purge durability replay outcome is invalid')
                evidence = evidence_by_target.get((entry_id, entry_kind, parent_id))
                if evidence is None:
                    raise ValueError('purge replay evidence is missing')
                if evidence['scope'] == 'job' and (
                    entry_kind != 'job'
                    or parent_id != entry_id
                    or _JOB_ID.fullmatch(entry_id) is None
                ):
                    raise ValueError('purge replay job identity is invalid')
                if evidence['scope'] == 'quarantine' and (
                    entry_kind != 'quarantine'
                    or parent_id != 'quarantine'
                    or _TRANSACTION_ID.fullmatch(entry_id) is None
                ):
                    raise ValueError('purge replay quarantine identity is invalid')
                if evidence['scope'] == 'bundles' and (
                    parent_id != 'bundles'
                    or entry_kind not in {'stale_bundle', 'orphan_temp'}
                    or (
                        entry_kind == 'stale_bundle'
                        and _BUNDLE_NAME.fullmatch(entry_id) is None
                    )
                    or (
                        entry_kind == 'orphan_temp'
                        and not entry_id.startswith(_TEMP_FILE_PREFIX)
                    )
                ):
                    raise ValueError('purge replay bundle identity is invalid')
                if evidence['scope'] == 'job_temp' and (
                    entry_kind != 'orphan_temp'
                    or parent_id != evidence.get('job_id')
                    or not entry_id.startswith(_TEMP_FILE_PREFIX)
                ):
                    raise ValueError('purge replay temporary identity is invalid')
                scope = evidence['scope']
                operation = evidence.get('operation')
                if scope == 'job':
                    expected_operation = 'purge_expired'
                elif scope == 'quarantine':
                    expected_operation = 'purge_expired_quarantine'
                elif scope == 'job_temp':
                    expected_operation = 'purge_orphan_temp'
                elif scope == 'bundles':
                    expected_operation = (
                        'purge_stale_bundle'
                        if _BUNDLE_NAME.fullmatch(entry_id) is not None
                        else 'purge_orphan_temp'
                    )
                else:
                    raise ValueError('purge replay scope is invalid')
                if operation != expected_operation:
                    raise ValueError('purge replay operation is invalid')
                cleanup_owner: tuple[str, int, str, str, str] | None = None
                if evidence['scope'] in {'job', 'quarantine'}:
                    job_id = evidence.get('job_id')
                    source_parent = evidence.get('source_parent')
                    source_id = evidence.get('source_id')
                    source_operation = evidence.get('source_operation')
                    expected_source_parent = (
                        'root' if evidence['scope'] == 'job' else 'quarantine'
                    )
                    expected_operation = (
                        'purge_expired'
                        if evidence['scope'] == 'job'
                        else 'purge_expired_quarantine'
                    )
                    if (
                        not isinstance(job_id, str)
                        or _JOB_ID.fullmatch(job_id) is None
                        or (evidence['scope'] == 'job' and job_id != entry_id)
                        or source_parent != expected_source_parent
                        or source_id != entry_id
                        or source_operation != expected_operation
                        or evidence.get('operation') != expected_operation
                    ):
                        raise ValueError('purge replay owner source is invalid')
                    try:
                        owner_id = strict_owner_id(evidence.get('owner_id'))
                    except ValueError as exc:
                        raise ValueError('purge replay owner identity is invalid') from exc
                    cleanup_owner = (
                        job_id,
                        owner_id,
                        source_parent,
                        source_id,
                        source_operation,
                    )
                self._confirm_replay_evidence_absence(evidence)
                if cleanup_owner is not None:
                    (
                        job_id,
                        owner_id,
                        source_parent,
                        source_id,
                        source_operation,
                    ) = cleanup_owner
                    self._prepare_owner_identity_cleanup_tombstone(
                        job_id,
                        owner_id,
                        source_parent=source_parent,
                        source_id=source_id,
                        source_operation=source_operation,
                    )
                    self._remove_owner_identity_after_resolution(job_id)
            self._reconcile_owner_deletion_tombstones_unlocked()

    def list_quarantine(self) -> dict[str, Any]:
        """관리자 UI용 typed quarantine inventory."""
        with self._maintenance_lock():
            items = self._quarantine_items_unlocked()
            corrupt_items = [item for item in items if item['kind'] == 'corrupt']
            return {
                'items': items,
                'total_bytes': sum(int(item['size_bytes']) for item in items),
                'physical_total_bytes': sum(int(item['physical_bytes']) for item in items),
                'corrupt_entries': len(corrupt_items),
            }

    def list_recovery(self) -> dict[str, Any]:
        """관리자 후속 API용 unresolved recovery inventory; 경로나 비밀값은 노출하지 않는다."""
        with self._maintenance_lock():
            items = self._recovery_items_unlocked()
            corrupt_items = [item for item in items if item['kind'] == 'corrupt']
            return {
                'items': items,
                'recovery_ids': [
                    str(item['recovery_id'])
                    for item in items
                    if isinstance(item.get('recovery_id'), str)
                ],
                'management_tokens': [
                    str(item['management_token'])
                    for item in corrupt_items
                ],
                'total_bytes': sum(int(item['size_bytes']) for item in items),
                'corrupt_entries': len(corrupt_items),
            }



    def delete_recovery_outcome(self, recovery_id: str) -> OfficeJobDirectMutationOutcome:
        """관리 recovery evidence 삭제의 실제 제거·durability 결과를 teardown failure 뒤에도 보존한다."""
        outcome: OfficeJobDirectMutationOutcome | None = None
        try:
            with self._maintenance_lock():
                entry = self._recovery_entry(recovery_id)
                item = self._recovery_item_from_entry(entry)
                outcome = self._delete_recovery_outcome_unlocked(recovery_id, entry, item)
                return outcome
        except OfficeJobDirectMutationError:
            raise
        except Exception as exc:
            actual = outcome or self._direct_mutation_outcome_from_error(exc)
            if actual is not None:
                raise OfficeJobDirectMutationError(actual, exc) from exc
            raise

    def _delete_recovery_outcome_unlocked(
        self,
        recovery_id: str,
        entry: Path,
        item: dict[str, Any],
    ) -> OfficeJobDirectMutationOutcome:
        outcome: OfficeJobDirectMutationOutcome = {
            'operation': 'recovery_delete',
            'target_id': recovery_id,
            'management_token': item.get('management_token'),
            'job_id': None,
            'owner_id': None,
            'logical_bytes': 0,
            'physical_bytes': self._physical_size_no_follow(entry),
            'partial_bytes_removed': 0,
            'published': False,
            'removed': False,
            'durably_synced': False,
            'durability': 'pending',
            'retry_required': True,
        }
        try:
            deletion = self._safe_delete_recovery_entry(entry)
        except OfficeJobDeletionError as exc:
            outcome['physical_bytes'] = exc.outcome['physical_bytes']
            outcome['partial_bytes_removed'] = exc.outcome['partial_bytes_removed']
            outcome['removed'] = exc.outcome['removed']
            outcome['durably_synced'] = exc.outcome['durably_synced']
            outcome['durability'] = exc.outcome.get('durability', 'pending')
            outcome['retry_required'] = exc.outcome.get('retry_required', True)
            raise OfficeJobDirectMutationError(outcome, exc) from exc
        outcome['physical_bytes'] = deletion['physical_bytes']
        outcome['partial_bytes_removed'] = deletion['partial_bytes_removed']
        outcome['removed'] = deletion['removed']
        outcome['durably_synced'] = deletion['durably_synced']
        outcome['durability'] = deletion.get('durability', 'synced' if deletion['durably_synced'] else 'platform_best_effort')
        outcome['retry_required'] = deletion.get('retry_required', False)
        return outcome

    def restore_quarantine_outcome(self, quarantine_id: str) -> OfficeJobDirectMutationOutcome:
        """격리 복원의 공개·제거·durability 결과를 teardown failure 뒤에도 보존한다."""
        outcome: OfficeJobDirectMutationOutcome | None = None
        try:
            with self._maintenance_lock():
                _metadata, outcome = self._restore_quarantine_outcome_unlocked(quarantine_id)
                return outcome
        except OfficeJobDirectMutationError:
            raise
        except Exception as exc:
            actual = outcome or self._direct_mutation_outcome_from_error(exc)
            if actual is not None:
                raise OfficeJobDirectMutationError(actual, exc) from exc
            raise

    def _restore_quarantine_outcome_unlocked(
        self,
        quarantine_id: str,
    ) -> tuple[dict[str, Any], OfficeJobDirectMutationOutcome]:
        entry = self._quarantine_entry(quarantine_id)
        metadata = self._read_quarantine_metadata(entry)
        payload = entry / _QUARANTINE_PAYLOAD_NAME
        job_id = str(metadata['job_id'])
        record = self._validated_quarantine_payload(entry, metadata)
        owner = strict_owner_id(record['owner_id'])
        outcome: OfficeJobDirectMutationOutcome | None = None
        try:
            with self._owner_capacity_lock(owner):
                metadata = self._read_quarantine_metadata(entry)
                job_id = str(metadata['job_id'])
                record = self._validated_quarantine_payload(entry, metadata)
                restored_bytes = self._job_data_size(payload, record)
                target = self.root / job_id
                if target.exists() or target.is_symlink():
                    raise FileExistsError(job_id)
                self._ensure_capacity(
                    owner,
                    jobs_to_add=1,
                    bytes_to_add=restored_bytes,
                    temporary_write_bytes=0,
                )
                outcome = {
                    'operation': 'quarantine_restore',
                    'target_id': quarantine_id,
                    'management_token': None,
                    'job_id': job_id,
                    'owner_id': owner,
                    'logical_bytes': restored_bytes,
                    'physical_bytes': self._physical_size_no_follow(entry),
                    'partial_bytes_removed': 0,
                    'published': False,
                    'removed': False,
                    'durably_synced': False,
                    'durability': 'pending',
                    'retry_required': True,
                }
                self._ensure_owner_identity(job_id, owner)
                try:
                    payload.replace(target)
                    outcome['published'] = True
                    self._apply_directory_sync_outcome(outcome, self.root)
                    deletion = self._safe_delete_quarantine_entry(entry)
                except OfficeJobDeletionError as exc:
                    outcome['removed'] = exc.outcome['removed']
                    outcome['partial_bytes_removed'] = exc.outcome['partial_bytes_removed']
                    outcome['durably_synced'] = False
                    outcome['durability'] = exc.outcome.get('durability', 'pending')
                    outcome['retry_required'] = exc.outcome.get('retry_required', True)
                    raise OfficeJobDirectMutationError(outcome, exc) from exc
                except Exception as exc:
                    raise OfficeJobDirectMutationError(outcome, exc) from exc
                outcome['removed'] = deletion['removed']
                outcome['partial_bytes_removed'] = deletion['partial_bytes_removed']
                outcome['durably_synced'] = (
                    deletion['durably_synced'] and outcome['durability'] == 'synced'
                )
                outcome['durability'] = (
                    'platform_best_effort'
                    if outcome['durability'] == 'platform_best_effort'
                    or deletion.get('durability') == 'platform_best_effort'
                    else deletion.get('durability', 'synced')
                )
                outcome['retry_required'] = deletion.get('retry_required', False) or outcome['durability'] == 'pending'
                return metadata, outcome
        except OfficeJobDirectMutationError:
            raise
        except Exception as exc:
            if outcome is not None:
                raise OfficeJobDirectMutationError(outcome, exc) from exc
            raise

    def delete_quarantine_outcome(self, quarantine_id: str) -> OfficeJobDirectMutationOutcome:
        """quarantine 삭제의 실제 제거·durability 결과를 teardown failure 뒤에도 보존한다."""
        outcome: OfficeJobDirectMutationOutcome | None = None
        try:
            with self._maintenance_lock():
                entry = self._quarantine_entry(quarantine_id)
                item = self._quarantine_item_from_entry(entry)
                if item.get('kind') != 'quarantine':
                    raise OfficeJobCorruptionError([quarantine_id])
                outcome = self._delete_quarantine_outcome_unlocked(quarantine_id, entry, item)
                return outcome
        except OfficeJobDirectMutationError:
            raise
        except Exception as exc:
            actual = outcome or self._direct_mutation_outcome_from_error(exc)
            if actual is not None:
                raise OfficeJobDirectMutationError(actual, exc) from exc
            raise

    def _delete_quarantine_outcome_unlocked(
        self,
        quarantine_id: str,
        entry: Path,
        item: dict[str, Any],
    ) -> OfficeJobDirectMutationOutcome:
        job_id = item['job_id']
        owner = item['owner_id']
        payload_record = self._quarantine_payload_record(entry, item)
        logical_bytes = self._artifact_logical_size(payload_record)
        outcome: OfficeJobDirectMutationOutcome = {
            'operation': 'quarantine_delete',
            'target_id': quarantine_id,
            'management_token': item.get('management_token'),
            'job_id': job_id,
            'owner_id': owner,
            'logical_bytes': logical_bytes,
            'physical_bytes': self._physical_size_no_follow(entry),
            'partial_bytes_removed': 0,
            'published': False,
            'removed': False,
            'durably_synced': False,
            'durability': 'pending',
            'retry_required': True,
        }
        try:
            if isinstance(job_id, str) and _JOB_ID.fullmatch(job_id):
                self._prepare_owner_identity_cleanup_tombstone(
                    job_id,
                    strict_owner_id(owner),
                    source_parent='quarantine',
                    source_id=quarantine_id,
                    source_operation='quarantine_delete',
                )
            deletion = self._safe_delete_quarantine_entry(entry)
            outcome['physical_bytes'] = deletion['physical_bytes']
            outcome['partial_bytes_removed'] = deletion['partial_bytes_removed']
            outcome['removed'] = deletion['removed']
            if isinstance(job_id, str) and _JOB_ID.fullmatch(job_id):
                self._remove_owner_identity_after_resolution(job_id)
        except OfficeJobDeletionError as exc:
            outcome['physical_bytes'] = exc.outcome['physical_bytes']
            outcome['partial_bytes_removed'] = exc.outcome['partial_bytes_removed']
            outcome['removed'] = exc.outcome['removed']
            outcome['durability'] = exc.outcome.get('durability', 'pending')
            outcome['retry_required'] = exc.outcome.get('retry_required', True)
            raise OfficeJobDirectMutationError(outcome, exc) from exc

        except Exception as exc:
            raise OfficeJobDirectMutationError(outcome, exc) from exc
        outcome['durably_synced'] = deletion['durably_synced']
        outcome['durability'] = deletion.get('durability', 'synced' if deletion['durably_synced'] else 'platform_best_effort')
        outcome['retry_required'] = deletion.get('retry_required', False)
        return outcome

    def dispose_corrupt_evidence_outcome(self, management_token: str) -> OfficeJobDirectMutationOutcome:
        """Preserve corrupt-evidence disposition outcomes across maintenance teardown."""
        outcome: OfficeJobDirectMutationOutcome | None = None
        try:
            with self._maintenance_lock():
                registered = self._management_tokens.get(management_token)
                if registered is None:
                    raise FileNotFoundError('invalid management token')
                scope, name, signature = registered
                roots = {
                    'quarantine': self._quarantine_root,
                    'recovery': self._recovery_quarantine_root,
                    'owner_identity': self._owner_identities_root,
                }
                root = roots.get(scope)
                if root is None:
                    raise FileNotFoundError('invalid management token')
                entry = root / name
                if self._direct_child_signature(entry) != signature:
                    raise OfficeJobCorruptionError(['managed evidence'])
                if scope == 'quarantine':
                    item = self._quarantine_item_from_entry(entry)
                elif scope == 'recovery':
                    item = self._recovery_item_from_entry(entry)
                else:
                    item = next(
                        (
                            candidate
                            for candidate in self._owner_identity_items_unlocked()
                            if candidate.get('management_token') == management_token
                        ),
                        None,
                    )
                    if item is None:
                        raise OfficeJobCorruptionError(['managed evidence'])
                if item.get('kind') != 'corrupt':
                    raise OfficeJobCorruptionError(['managed evidence'])
                outcome = {
                    'operation': f'{scope}_corrupt_disposition',
                    'target_id': management_token,
                    'management_token': management_token,
                    'job_id': None,
                    'owner_id': None,
                    'logical_bytes': 0,
                    'physical_bytes': self._physical_size_no_follow(entry),
                    'partial_bytes_removed': 0,
                    'published': False,
                    'removed': False,
                    'durably_synced': False,
                    'durability': 'pending',
                    'retry_required': True,
                }
                try:
                    deletion = self._safe_delete_corrupt_evidence_child(root, entry, management_token)
                except OfficeJobDeletionError as exc:
                    outcome['physical_bytes'] = exc.outcome['physical_bytes']
                    outcome['partial_bytes_removed'] = exc.outcome['partial_bytes_removed']
                    outcome['removed'] = exc.outcome['removed']
                    outcome['durably_synced'] = exc.outcome['durably_synced']
                    outcome['durability'] = exc.outcome.get('durability', 'pending')
                    outcome['retry_required'] = exc.outcome.get('retry_required', True)
                    raise OfficeJobDirectMutationError(outcome, exc) from exc
                except Exception as exc:
                    raise OfficeJobDirectMutationError(outcome, exc) from exc
                outcome['physical_bytes'] = deletion['physical_bytes']
                outcome['partial_bytes_removed'] = deletion['partial_bytes_removed']
                outcome['removed'] = deletion['removed']
                outcome['durably_synced'] = deletion['durably_synced']
                outcome['durability'] = deletion.get('durability', 'synced' if deletion['durably_synced'] else 'platform_best_effort')
                outcome['retry_required'] = deletion.get('retry_required', False)
                return outcome
        except OfficeJobDirectMutationError:
            raise
        except Exception as exc:
            actual = outcome or self._direct_mutation_outcome_from_error(exc)
            if actual is not None:
                raise OfficeJobDirectMutationError(actual, exc) from exc
            raise

    def _artifact_metadata(self, job_id: str, filename: str, media_type: str, path: Path) -> dict[str, Any]:
        if not isinstance(media_type, str) or not media_type:
            raise ValueError('artifact media_type must be a non-empty string')
        return {
            'filename': filename,
            'media_type': media_type,
            'size_bytes': path.stat().st_size,
            'sha256': _sha256_file(path),
            'download_url': f'/api/v1/office-tools/jobs/{job_id}/artifacts/{filename}',
        }

    @staticmethod
    def _record_with_artifact(record: dict[str, Any], artifact: dict[str, Any]) -> dict[str, Any]:
        artifacts = [item for item in record['artifacts'] if item['filename'] != artifact['filename']]
        artifacts.append(artifact)
        return {**record, 'artifacts': artifacts, 'updated_at': _now_iso()}

    def _ensure_capacity(
        self,
        owner_id: int,
        *,
        jobs_to_add: int,
        bytes_to_add: int,
        temporary_write_bytes: int,
    ) -> None:
        usage = self._usage_for_owner_unlocked(owner_id)
        if usage['job_count'] + jobs_to_add > self.max_jobs_per_owner:
            raise OfficeJobCapacityError('owner job quota exceeded')
        if usage['total_bytes'] + bytes_to_add > self.max_bytes_per_owner:
            raise OfficeJobCapacityError('owner storage quota exceeded')
        free_bytes = shutil.disk_usage(self.root).free
        unattributed_owner_identity_bytes = self._unattributed_owner_identity_bytes_unlocked()
        if (
            free_bytes - temporary_write_bytes - unattributed_owner_identity_bytes
            < self.min_free_bytes
        ):
            raise OfficeJobCapacityError('office job storage is below the minimum free disk threshold')

    def _temporary_bundle_upper_bound(self, artifact_paths: list[Path]) -> int:
        """DEFLATE expansion, ZIP headers, central directory, and ZIP64 metadata를 예약한다."""
        total = 22  # End of central directory.
        for path in artifact_paths:
            size = path.stat().st_size
            filename_bytes = len(path.name.encode('utf-8'))
            compression_expansion = max(64 * 1024, (size + 99) // 100)
            zip_metadata = 512 + 2 * filename_bytes
            total += size + compression_expansion + zip_metadata
        return total

    def _ensure_temporary_bundle_capacity(self, reserved_bytes: int) -> None:
        bundles = self._bundle_paths_unlocked()
        if len(bundles) + 1 > self.max_temporary_bundles:
            raise OfficeJobCapacityError('temporary office bundle limit exceeded')
        free_bytes = shutil.disk_usage(self._bundles_root).free
        if (
            free_bytes - reserved_bytes - self._unattributed_owner_identity_bytes_unlocked()
            < self.min_free_bytes
        ):
            raise OfficeJobCapacityError('office bundle volume is below the minimum free disk threshold')

    def _verify_temporary_bundle_capacity_after_write(self, measured_bytes: int, reserved_bytes: int) -> None:
        if measured_bytes > reserved_bytes:
            raise OfficeJobCapacityError('temporary office bundle exceeded its reserved capacity')
        if len(self._bundle_paths_unlocked()) + 1 > self.max_temporary_bundles:
            raise OfficeJobCapacityError('temporary office bundle limit exceeded')
        if (
            shutil.disk_usage(self._bundles_root).free
            - self._unattributed_owner_identity_bytes_unlocked()
            < self.min_free_bytes
        ):
            raise OfficeJobCapacityError('office bundle volume is below the minimum free disk threshold')

    def _owned_job_records_unlocked(self, owner_id: int) -> list[tuple[Path, dict[str, Any]]]:
        owner = strict_owner_id(owner_id)
        owned_jobs: list[tuple[Path, dict[str, Any]]] = []
        corrupt_job_ids: list[str] = []
        for job_dir in self._job_entries():
            indexed_owner = self._corrupt_record_owner_id(job_dir)
            if not self._is_valid_job_dir(job_dir):
                if indexed_owner == owner:
                    corrupt_job_ids.append(job_dir.name)
                continue
            try:
                record = self._read_record(job_dir)
                record_owner = self._owner_identity_for_valid_record(job_dir, record)
                if record_owner == owner:
                    owned_jobs.append((job_dir, record))
            except OfficeJobCorruptionError:
                corrupt_owner = indexed_owner or self._corrupt_record_owner_id(job_dir)
                if corrupt_owner == owner:
                    corrupt_job_ids.append(job_dir.name)
        if corrupt_job_ids:
            raise OfficeJobCorruptionError(corrupt_job_ids)
        return owned_jobs

    def _usage_for_owner_unlocked(self, owner_id: int) -> dict[str, int]:
        owner = strict_owner_id(owner_id)
        job_count = 0
        total_bytes = 0
        for job_dir in self._job_entries():
            indexed_owner = self._corrupt_record_owner_id(job_dir)
            if not self._is_valid_job_dir(job_dir):
                if indexed_owner == owner:
                    job_count += 1
                    total_bytes += self._physical_size_no_follow(job_dir)
                continue
            try:
                record = self._read_record(job_dir)
                record_owner = self._owner_identity_for_valid_record(job_dir, record)
                logical_bytes = self._job_data_size(job_dir, record)
            except OfficeJobCorruptionError:
                corrupt_owner = indexed_owner or self._corrupt_record_owner_id(job_dir)
                if corrupt_owner == owner:
                    job_count += 1
                    total_bytes += self._physical_size_no_follow(job_dir)
                continue
            if record_owner == owner:
                job_count += 1
                total_bytes += logical_bytes
        return {'job_count': job_count, 'total_bytes': total_bytes}

    def _artifact_logical_size(self, record: dict[str, Any]) -> int:
        return sum(int(artifact['size_bytes']) for artifact in record['artifacts'])

    def _artifact_logical_bytes_unlocked(self) -> int:
        total = 0
        for job_dir in self._job_entries():
            if not self._is_valid_job_dir(job_dir):
                continue
            try:
                record = self._read_record(job_dir)
                total += self._job_data_size(job_dir, record)
            except OfficeJobCorruptionError:
                continue
        return total

    def _job_physical_accounting_unlocked(self) -> dict[str, int]:
        job_physical_bytes = 0
        job_metadata_physical_bytes = 0
        job_temporary_physical_bytes = 0
        job_artifact_physical_bytes = 0
        for job_dir in self._job_entries():
            job_physical_bytes += self._physical_size_no_follow(job_dir)
            if not self._is_valid_job_dir(job_dir):
                continue
            metadata = job_dir / 'job.json'
            if (
                not metadata.is_symlink()
                and metadata.is_file()
                and metadata.resolve().parent == job_dir.resolve()
            ):
                job_metadata_physical_bytes += metadata.stat().st_size
            for path in job_dir.iterdir():
                if (
                    path.name.startswith(_TEMP_FILE_PREFIX)
                    and not path.is_symlink()
                    and path.is_file()
                    and path.resolve().parent == job_dir.resolve()
                ):
                    job_temporary_physical_bytes += path.stat().st_size
            try:
                record = self._read_record(job_dir)
                job_artifact_physical_bytes += self._job_data_size(job_dir, record)
            except OfficeJobCorruptionError:
                continue
        return {
            'job_physical_bytes': job_physical_bytes,
            'job_metadata_physical_bytes': job_metadata_physical_bytes,
            'job_temporary_physical_bytes': job_temporary_physical_bytes,
            'job_artifact_physical_bytes': job_artifact_physical_bytes,
            'job_unclassified_physical_bytes': max(
                0,
                job_physical_bytes
                - job_metadata_physical_bytes
                - job_temporary_physical_bytes
                - job_artifact_physical_bytes,
            ),
        }

    def _root_unclassified_physical_bytes_unlocked(self) -> int:
        managed_names = {
            _LOCKS_DIR_NAME,
            _QUARANTINE_DIR_NAME,
            _STAGING_DIR_NAME,
            _TRANSACTIONS_DIR_NAME,
            _RECOVERY_QUARANTINE_DIR_NAME,
            _BUNDLES_DIR_NAME,
            _OWNER_IDENTITIES_DIR_NAME,
            _OWNER_DELETION_TOMBSTONES_DIR_NAME,
            _PENDING_RESULTS_DIR_NAME,
        }
        return sum(
            self._path_size(path)
            for path in self.root.iterdir()
            if path.name not in managed_names and not _JOB_ID.fullmatch(path.name)
        )

    def _corrupt_record_owner_id(self, job_dir: Path) -> int | None:
        try:
            return self._read_owner_identity(job_dir.name)
        except OfficeJobCorruptionError:
            return None

    def _job_entries(self) -> list[Path]:
        return [path for path in self.root.iterdir() if _JOB_ID.fullmatch(path.name)]
    def _is_valid_job_dir(self, path: Path) -> bool:
        try:
            return not path.is_symlink() and path.is_dir() and path.resolve().parent == self.root
        except OSError:
            return False

    def _job_data_size(self, job_dir: Path, record: dict[str, Any]) -> int:
        artifacts = {artifact['filename']: artifact for artifact in record['artifacts']}
        actual_names: set[str] = set()
        for path in job_dir.iterdir():
            if path.name == 'job.json' or path.name.startswith(_TEMP_FILE_PREFIX):
                continue
            if path.is_symlink() or not path.is_file() or path.resolve().parent != job_dir.resolve():
                raise OfficeJobCorruptionError([record['job_id']])
            if path.name not in artifacts:
                raise OfficeJobCorruptionError([record['job_id']])
            actual_names.add(path.name)
            self._validated_artifact_path(job_dir, record['job_id'], artifacts[path.name])
        if actual_names != set(artifacts):
            raise OfficeJobCorruptionError([record['job_id']])
        return sum(artifact['size_bytes'] for artifact in artifacts.values())

    def _validated_artifact_path(self, job_dir: Path, job_id: str, artifact: dict[str, Any]) -> Path:
        filename = artifact['filename']
        path = job_dir / filename
        if path.is_symlink() or not path.is_file() or path.resolve().parent != job_dir.resolve():
            raise OfficeJobCorruptionError([job_id])
        if not self._artifact_file_matches(path, artifact):
            raise OfficeJobCorruptionError([job_id])
        return path

    @staticmethod
    def _artifact_file_matches(path: Path, artifact: dict[str, Any]) -> bool:
        try:
            return path.stat().st_size == artifact['size_bytes'] and _sha256_file(path) == artifact['sha256']
        except (KeyError, OSError, TypeError):
            return False
    @staticmethod
    def _open_file_no_follow(path: Path) -> BinaryIO:
        """최종 artifact가 symlink/reparse point가 아닌 열린 regular-file handle을 만든다."""
        if os.name == 'nt':
            import ctypes
            import msvcrt
            from ctypes import wintypes

            generic_read = 0x80000000
            file_share_read = 0x00000001
            open_existing = 3
            file_flag_open_reparse_point = 0x00200000
            file_attribute_reparse_point = 0x00000400

            class FileBasicInfo(ctypes.Structure):
                _fields_ = [
                    ('creation_time', ctypes.c_longlong),
                    ('last_access_time', ctypes.c_longlong),
                    ('last_write_time', ctypes.c_longlong),
                    ('change_time', ctypes.c_longlong),
                    ('file_attributes', wintypes.DWORD),
                ]

            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            create_file = kernel32.CreateFileW
            create_file.argtypes = [
                wintypes.LPCWSTR,
                wintypes.DWORD,
                wintypes.DWORD,
                ctypes.c_void_p,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.HANDLE,
            ]
            create_file.restype = wintypes.HANDLE
            get_info = kernel32.GetFileInformationByHandleEx
            get_info.argtypes = [
                wintypes.HANDLE,
                ctypes.c_int,
                ctypes.c_void_p,
                wintypes.DWORD,
            ]
            get_info.restype = wintypes.BOOL
            close_handle = kernel32.CloseHandle
            close_handle.argtypes = [wintypes.HANDLE]
            close_handle.restype = wintypes.BOOL

            handle = create_file(
                str(path),
                generic_read,
                file_share_read,
                None,
                open_existing,
                file_flag_open_reparse_point,
                None,
            )
            invalid_handle = ctypes.c_void_p(-1).value
            if handle == invalid_handle:
                raise OSError(ctypes.get_last_error(), f'cannot open artifact: {path.name}')
            fd = -1
            try:
                info = FileBasicInfo()
                if not get_info(handle, 0, ctypes.byref(info), ctypes.sizeof(info)):
                    raise OSError(ctypes.get_last_error(), f'cannot inspect artifact: {path.name}')
                if info.file_attributes & file_attribute_reparse_point:
                    raise OSError(errno.ELOOP, f'artifact is a reparse point: {path.name}')
                fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | getattr(os, 'O_BINARY', 0))
                handle = None
                return os.fdopen(fd, 'rb', closefd=True)
            except BaseException:
                if fd != -1:
                    os.close(fd)
                elif handle is not None:
                    close_handle(handle)
                raise

        no_follow = getattr(os, 'O_NOFOLLOW', None)
        if no_follow is None:
            raise OSError(errno.EOPNOTSUPP, 'platform does not provide no-follow artifact opens')
        fd = os.open(path, os.O_RDONLY | no_follow | getattr(os, 'O_BINARY', 0))
        try:
            return os.fdopen(fd, 'rb', closefd=True)
        except BaseException:
            os.close(fd)
            raise

    @staticmethod
    def _artifact_handle_matches(handle: BinaryIO, artifact: dict[str, Any]) -> bool:
        """열린 handle 자체가 manifest의 regular file·size·hash와 일치하는지 확인한다."""
        try:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                return False
            if os.fstat(handle.fileno()).st_size != artifact['size_bytes']:
                return False
            digest = hashlib.sha256()
            for block in iter(lambda: handle.read(1024 * 1024), b''):
                digest.update(block)
            handle.seek(0)
            return digest.hexdigest() == artifact['sha256']
        except (KeyError, OSError, TypeError):
            return False

    @staticmethod
    def _record_timestamp(record: dict[str, Any]) -> datetime:
        value = record['updated_at']
        timestamp = datetime.fromisoformat(value)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        return timestamp.astimezone(UTC)

    def _quarantine_purge_job(
        self,
        result: OfficeJobPurgeResult,
        job_dir: Path,
        reason: str,
        logical_artifact_bytes: int,
    ) -> None:
        try:
            outcome = self._quarantine_corrupt_job_mutation(
                job_dir,
                reason,
                logical_artifact_bytes,
            )
        except OfficeJobQuarantineMutationError as exc:
            self._record_quarantine_mutation(result, exc.outcome)
            if exc.outcome['quarantine_id'] not in result['failed_quarantine_ids']:
                result['failed_quarantine_ids'].append(exc.outcome['quarantine_id'])
            raise
        if outcome is not None:
            self._record_quarantine_mutation(result, outcome)

    def _quarantine_corrupt_job(self, job_dir: Path, reason: str) -> dict[str, Any] | None:
        outcome = self._quarantine_corrupt_job_mutation(job_dir, reason, 0)
        return None if outcome is None else outcome['metadata']

    def _quarantine_corrupt_job_mutation(
        self,
        job_dir: Path,
        reason: str,
        logical_artifact_bytes: int,
    ) -> OfficeJobQuarantineMutationOutcome | None:
        if not job_dir.exists() and not job_dir.is_symlink():
            return None
        if not _JOB_ID.fullmatch(job_dir.name) or job_dir.parent != self.root:
            raise OfficeJobCorruptionError([job_dir.name])
        job_id = job_dir.name
        size = self._path_size(job_dir)
        quarantine_id = uuid.uuid4().hex
        entry = self._quarantine_root / quarantine_id
        payload = entry / _QUARANTINE_PAYLOAD_NAME
        owner = self._corrupt_record_owner_id(job_dir)
        metadata = {
            'quarantine_id': quarantine_id,
            'job_id': job_id,
            'size_bytes': size,
            'quarantined_at': _now_iso(),
            'reason': reason,
        }
        if owner is not None:
            metadata['owner_id'] = owner
        if owner is not None:
            self._prepare_owner_identity_cleanup_tombstone(
                job_id,
                owner,
                source_parent='root',
                source_id=job_id,
                source_operation='quarantine_corrupt_job',
            )

        def outcome() -> OfficeJobQuarantineMutationOutcome:
            payload_remains_moved = (
                (payload.exists() or payload.is_symlink())
                and not job_dir.exists()
                and not job_dir.is_symlink()
            )
            return {
                'metadata': dict(metadata),
                'quarantine_id': quarantine_id,
                'logical_artifact_bytes': logical_artifact_bytes if payload_remains_moved else 0,
                'physical_moved_bytes': size if payload_remains_moved else 0,
                'payload_remains_moved': payload_remains_moved,
            }

        try:
            entry.mkdir(parents=False, exist_ok=False)
            self._fsync_directory(self._quarantine_root)
            self._write_json_durable(entry / _QUARANTINE_METADATA_NAME, metadata)
            job_dir.replace(payload)
            if not outcome()['payload_remains_moved']:
                raise OSError(f'job payload was not quarantined: {job_id}')
            self._fsync_directory(self.root)
            self._fsync_directory(entry)
        except Exception as exc:
            if outcome()['payload_remains_moved']:
                try:
                    payload.replace(job_dir)
                    self._fsync_directory(self.root)
                    self._fsync_directory(entry)
                except Exception:
                    pass
            raise OfficeJobQuarantineMutationError(outcome(), exc) from exc
        try:
            self._remove_owner_identity_after_resolution(job_id)
        except Exception as exc:
            raise OfficeJobQuarantineMutationError(outcome(), exc) from exc
        return outcome()

    def _quarantine_entry(self, quarantine_id: str) -> Path:
        if not _TRANSACTION_ID.fullmatch(quarantine_id):
            raise FileNotFoundError('invalid quarantine id')
        entry = self._quarantine_root / quarantine_id
        if entry.parent != self._quarantine_root or entry.is_symlink() or not entry.is_dir():
            raise FileNotFoundError(quarantine_id)
        if entry.resolve().parent != self._quarantine_root:
            raise FileNotFoundError(quarantine_id)
        return entry

    def _recovery_entry(self, recovery_id: object) -> Path:
        if not isinstance(recovery_id, str) or not _TRANSACTION_ID.fullmatch(recovery_id):
            raise FileNotFoundError('invalid recovery id')
        entry = self._recovery_quarantine_root / recovery_id
        try:
            if not entry.exists() and not entry.is_symlink():
                raise FileNotFoundError(recovery_id)
            if (
                self._recovery_quarantine_root.is_symlink()
                or not self._recovery_quarantine_root.is_dir()
                or entry.parent != self._recovery_quarantine_root
                or entry.is_symlink()
                or not entry.is_dir()
                or entry.resolve().parent != self._recovery_quarantine_root.resolve()
            ):
                raise OfficeJobCorruptionError([recovery_id])
        except FileNotFoundError:
            raise
        except OSError as exc:
            raise OfficeJobCorruptionError([recovery_id]) from exc
        return entry

    def _quarantine_items_unlocked(self) -> list[dict[str, Any]]:
        if self._quarantine_root.is_symlink() or not self._quarantine_root.is_dir():
            raise OfficeJobCorruptionError(['quarantine inventory'])
        items = [
            self._quarantine_item_from_entry(entry)
            for entry in self._quarantine_root.iterdir()
        ]
        return sorted(
            items,
            key=lambda item: (
                str(item.get('quarantined_at') or ''),
                str(item.get('quarantine_id') or item.get('management_token') or ''),
            ),
            reverse=True,
        )

    def _quarantine_item_from_entry(self, entry: Path) -> dict[str, Any]:
        physical_bytes = self._physical_size_no_follow(entry)
        reason = self._direct_child_reason(
            self._quarantine_root,
            entry,
            _TRANSACTION_ID,
            'directory',
        )
        if reason is None:
            try:
                metadata = self._read_quarantine_metadata(entry)
                return {
                    'kind': 'quarantine',
                    'management_token': None,
                    **metadata,
                    'physical_bytes': physical_bytes,
                }
            except OfficeJobCorruptionError:
                reason = 'quarantine metadata is invalid'
        return {
            'kind': 'corrupt',
            'management_token': self._management_token('quarantine', entry),
            'quarantine_id': None,
            'job_id': None,
            'owner_id': None,
            'size_bytes': physical_bytes,
            'physical_bytes': physical_bytes,
            'quarantined_at': self._evidence_timestamp(entry),
            'reason': reason,
        }

    def _read_quarantine_metadata(self, entry: Path) -> dict[str, Any]:
        path = entry / _QUARANTINE_METADATA_NAME
        try:
            if path.is_symlink() or not path.is_file() or path.resolve().parent != entry.resolve():
                raise ValueError('metadata not found')
            metadata = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(metadata, dict):
                raise ValueError('metadata must be an object')
            if metadata.get('quarantine_id') != entry.name or not _TRANSACTION_ID.fullmatch(entry.name):
                raise ValueError('quarantine_id is invalid')
            if not isinstance(metadata.get('job_id'), str) or not _JOB_ID.fullmatch(metadata['job_id']):
                raise ValueError('job_id is invalid')
            size_bytes = metadata.get('size_bytes')
            if isinstance(size_bytes, bool) or not isinstance(size_bytes, int) or size_bytes < 0:
                raise ValueError('size_bytes is invalid')
            timestamp = metadata.get('quarantined_at')
            if not isinstance(timestamp, str) or not timestamp:
                raise ValueError('quarantined_at is invalid')
            datetime.fromisoformat(timestamp)
            if not isinstance(metadata.get('reason'), str) or not metadata['reason'].strip():
                raise ValueError('reason is invalid')
            owner = strict_owner_id(metadata.get('owner_id'))
            payload_owner = strict_owner_id(
                self._quarantine_payload_record(entry, metadata)['owner_id']
            )
            if owner != payload_owner:
                raise ValueError('quarantine owner_id does not match payload owner_id')
        except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError, TypeError) as exc:
            raise OfficeJobCorruptionError([entry.name]) from exc
        return {
            'quarantine_id': metadata['quarantine_id'],
            'job_id': metadata['job_id'],
            'owner_id': owner,
            'size_bytes': metadata['size_bytes'],
            'quarantined_at': metadata['quarantined_at'],
            'reason': metadata['reason'],
        }
    def _quarantine_payload_record(self, entry: Path, metadata: dict[str, Any]) -> dict[str, Any]:
        """Validate payload containment and ownership without hashing every artifact."""
        job_id = str(metadata['job_id'])
        payload = entry / _QUARANTINE_PAYLOAD_NAME
        if (
            payload.is_symlink()
            or not payload.is_dir()
            or payload.resolve().parent != entry.resolve()
            or self._path_size(payload) != metadata['size_bytes']
        ):
            raise OfficeJobCorruptionError([job_id])
        return self._read_record(payload, expected_job_id=job_id)

    def _validated_quarantine_payload(self, entry: Path, metadata: dict[str, Any]) -> dict[str, Any]:
        record = self._quarantine_payload_record(entry, metadata)
        self._job_data_size(entry / _QUARANTINE_PAYLOAD_NAME, record)
        return record

    def _reconcile_quarantine_entries_unlocked(self) -> None:
        """Validate quarantine evidence without deleting metadata-only containers."""
        for entry in self._quarantine_root.iterdir():
            if not _TRANSACTION_ID.fullmatch(entry.name) or entry.is_symlink() or not entry.is_dir():
                continue
            try:
                self._read_quarantine_metadata(entry)
            except OfficeJobCorruptionError:
                continue

    def _purge_expired_quarantine_unlocked(
        self,
        result: OfficeJobPurgeResult | None = None,
    ) -> tuple[int, int]:
        cutoff = datetime.now(UTC) - timedelta(days=self.quarantine_retention_days)
        deleted_entries = 0
        deleted_bytes = 0
        for entry in list(self._quarantine_root.iterdir()):
            if not _TRANSACTION_ID.fullmatch(entry.name) or entry.is_symlink() or not entry.is_dir():
                continue
            item = self._quarantine_item_from_entry(entry)
            if item.get('kind') == 'corrupt':
                continue
            try:
                timestamp = datetime.fromisoformat(str(item['quarantined_at']))
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=UTC)
                timestamp = timestamp.astimezone(UTC)
            except ValueError:
                timestamp = datetime.fromtimestamp(entry.stat().st_mtime, UTC)
            if timestamp < cutoff:
                try:
                    job_id = item.get('job_id')
                    owner_id = item.get('owner_id')
                    if isinstance(job_id, str) and _JOB_ID.fullmatch(job_id):
                        self._prepare_owner_identity_cleanup_tombstone(
                            job_id,
                            strict_owner_id(owner_id),
                            source_parent='quarantine',
                            source_id=entry.name,
                            source_operation='purge_expired_quarantine',
                        )
                    replay_evidence = self._replay_evidence(
                        scope='quarantine',
                        entry=entry,
                        operation='purge_expired_quarantine',
                        job_id=job_id if isinstance(job_id, str) else None,
                        owner_id=strict_owner_id(owner_id) if owner_id is not None else None,
                    )
                    outcome = self._safe_delete_quarantine_entry(entry)
                except OfficeJobDeletionError as exc:
                    if result is not None:
                        self._record_partial_deletion(
                            result,
                            exc.outcome,
                            replay_evidence,
                        )
                        self._record_expired_quarantine_deletion(result, entry.name, exc.outcome)
                    raise
                except Exception:
                    if result is not None and entry.name not in result['failed_quarantine_ids']:
                        result['failed_quarantine_ids'].append(entry.name)
                    raise
                deleted_bytes += outcome['physical_bytes']
                deleted_entries += 1
                if result is not None:
                    self._record_expired_quarantine_deletion(result, entry.name, outcome)
                    self._record_partial_deletion(
                        result,
                        outcome,
                        replay_evidence,
                    )
                job_id = item.get('job_id')
                if isinstance(job_id, str) and _JOB_ID.fullmatch(job_id):
                    self._remove_owner_identity_after_resolution(job_id)
        return deleted_entries, deleted_bytes

    def _quarantine_usage_bytes_unlocked(self) -> int:
        return sum(int(item['size_bytes']) for item in self._quarantine_items_unlocked())

    def _safe_delete_quarantine_entry(self, entry: Path) -> OfficeJobDeletionOutcome:
        if (
            entry.parent != self._quarantine_root
            or not _TRANSACTION_ID.fullmatch(entry.name)
            or entry.is_symlink()
            or not entry.is_dir()
            or entry.resolve().parent != self._quarantine_root
        ):
            raise OfficeJobCorruptionError([entry.name])
        return self._safe_delete_managed_directory(
            entry,
            self._quarantine_root,
            entry.name,
            entry_kind='quarantine',
            parent_id='quarantine',
        )

    def _safe_delete_recovery_entry(self, entry: Path) -> OfficeJobDeletionOutcome:
        recovery_id = entry.name
        verified_entry = self._recovery_entry(recovery_id)
        if verified_entry != entry:
            raise OfficeJobCorruptionError([recovery_id])
        return self._safe_delete_managed_directory(
            verified_entry,
            self._recovery_quarantine_root,
            recovery_id,
            entry_kind='recovery',
            parent_id='recovery_quarantine',
        )
    def _bundle_paths_unlocked(self) -> list[Path]:
        bundles: list[Path] = []
        for path in self._bundles_root.iterdir():
            if (
                _BUNDLE_NAME.fullmatch(path.name)
                and not path.is_symlink()
                and path.is_file()
                and path.resolve().parent == self._bundles_root
            ):
                bundles.append(path)
        return bundles

    def _temporary_bundle_usage_bytes_unlocked(self) -> int:
        return sum(path.stat().st_size for path in self._bundle_paths_unlocked())

    def _reconcile_stale_bundles_unlocked(
        self,
        result: OfficeJobPurgeResult | None = None,
    ) -> tuple[int, int]:
        cutoff = time.time() - self.temporary_bundle_retention_seconds
        deleted = 0
        bytes_deleted = 0
        for path in list(self._bundles_root.iterdir()):
            known_bundle = _BUNDLE_NAME.fullmatch(path.name) is not None
            orphan_temp = path.name.startswith(_TEMP_FILE_PREFIX)
            if path.is_symlink() or not path.is_file() or not (known_bundle or orphan_temp):
                continue
            if not (orphan_temp or path.stat().st_mtime < cutoff):
                continue
            try:
                replay_evidence = self._replay_evidence(
                    scope='bundles',
                    entry=path,
                    operation='purge_stale_bundle' if known_bundle else 'purge_orphan_temp',
                )
                outcome = self._safe_delete_managed_file(
                    path,
                    self._bundles_root,
                    path.name,
                    entry_kind='stale_bundle' if known_bundle else 'orphan_temp',
                    parent_id='bundles',
                )
            except OfficeJobDeletionError as exc:
                outcome = exc.outcome
                if outcome['removed']:
                    deleted += 1
                    bytes_deleted += outcome['physical_bytes']
                    if result is not None:
                        result['stale_bundles'] += 1
                        result['stale_bundle_bytes'] += outcome['physical_bytes']
                        result['maintenance']['stale_bundles'] = result['stale_bundles']
                        result['maintenance']['stale_bundle_bytes'] = result['stale_bundle_bytes']
                if result is not None:
                    self._record_partial_deletion(result, outcome, replay_evidence)
                raise
            deleted += 1
            bytes_deleted += outcome['physical_bytes']
            if result is not None:
                result['stale_bundles'] += 1
                result['stale_bundle_bytes'] += outcome['physical_bytes']
                result['maintenance']['stale_bundles'] = result['stale_bundles']
                result['maintenance']['stale_bundle_bytes'] = result['stale_bundle_bytes']
        return deleted, bytes_deleted

    def _recover_transactions_unlocked(self) -> tuple[int, int]:
        recovered = 0
        rolled_back = 0
        for path in list(self._transactions_root.iterdir()):
            stage_id = path.stem if path.suffix == '.json' and _STAGE_ID.fullmatch(path.stem) else None
            try:
                if path.is_symlink() or not path.is_file() or path.suffix != '.json':
                    raise ValueError('journal is not a regular JSON file')
                if stage_id is None:
                    raise ValueError('journal transaction identifier is invalid')
                journal = json.loads(path.read_text(encoding='utf-8'))
                if not isinstance(journal, dict) or journal.get('stage_id') != stage_id:
                    raise ValueError('journal is invalid')
                operation = journal.get('operation')
                if operation not in {'create', 'artifact_replace'}:
                    raise ValueError('journal operation is unknown')
                owner = self._recovery_owner_id(journal)
                with self._owner_capacity_lock(owner):
                    if operation == 'create':
                        outcome = self._recover_create_transaction(journal)
                    else:
                        outcome = self._recover_artifact_transaction(journal)
            except Exception as exc:
                self._preserve_unresolved_recovery(
                    path,
                    stage_id,
                    f'{exc.__class__.__name__}: {exc}',
                )
                continue
            if outcome == 'recovered':
                recovered += 1
            elif outcome == 'rolled_back':
                rolled_back += 1
            else:
                self._preserve_unresolved_recovery(path, stage_id, 'recovery outcome is unknown')
        return recovered, rolled_back

    def _recovery_owner_id(self, journal: dict[str, Any]) -> int:
        job_id = journal.get('job_id')
        stage_id = journal.get('stage_id')
        operation = journal.get('operation')
        if (
            not isinstance(job_id, str)
            or not _JOB_ID.fullmatch(job_id)
            or not isinstance(stage_id, str)
            or not _STAGE_ID.fullmatch(stage_id)
            or operation not in {'create', 'artifact_replace'}
        ):
            raise ValueError('journal cannot prove its owner')

        owners: list[int] = []
        if 'owner_id' in journal:
            owners.append(strict_owner_id(journal['owner_id']))
        if operation == 'artifact_replace':
            for field in ('old_record', 'new_record'):
                record = journal.get(field)
                if not isinstance(record, dict):
                    raise ValueError(f'{field} cannot prove its owner')
                self._validate_record(self.root / job_id, record, expected_job_id=job_id)
                owners.append(strict_owner_id(record['owner_id']))

        job_dir = self.root / job_id
        if self._is_valid_job_dir(job_dir):
            try:
                owners.append(strict_owner_id(self._read_record(job_dir)['owner_id']))
            except OfficeJobCorruptionError:
                pass

        stage_dir = self._staging_root / stage_id
        stage_job_dir = stage_dir / job_id
        if self._is_valid_staged_job_dir(stage_job_dir, job_id):
            try:
                owners.append(strict_owner_id(self._read_record(stage_job_dir, expected_job_id=job_id)['owner_id']))
            except OfficeJobCorruptionError:
                pass

        if not owners or len(set(owners)) != 1:
            raise ValueError('journal cannot prove a single owner')
        return owners[0]

    def _recover_create_transaction(self, journal: dict[str, Any]) -> str:
        job_id = journal.get('job_id')
        stage_id = journal.get('stage_id')
        phase = journal.get('phase')
        expected_record = journal.get('record')
        if (
            not isinstance(job_id, str)
            or not _JOB_ID.fullmatch(job_id)
            or not isinstance(stage_id, str)
            or not _STAGE_ID.fullmatch(stage_id)
            or phase not in {'prepared', 'job_published'}
        ):
            raise ValueError('invalid create journal')
        if expected_record is not None:
            self._validate_record(self.root / job_id, expected_record, expected_job_id=job_id)

        job_dir = self.root / job_id
        stage_dir = self._staging_root / stage_id
        if self._is_valid_job_dir(job_dir):
            record = self._read_record(job_dir)
            self._job_data_size(job_dir, record)
            if expected_record is not None and record != expected_record:
                raise OfficeJobCorruptionError([job_id])
            self._ensure_owner_identity(job_id, record['owner_id'])
            self._validate_create_stage_for_cleanup(stage_dir, job_id)
            self._remove_stage_dir(stage_dir)
            self._remove_journal(stage_id)
            return 'recovered'
        if job_dir.exists() or job_dir.is_symlink():
            raise ValueError('create transaction target is invalid')

        if not stage_dir.exists() and not stage_dir.is_symlink():
            self._remove_owner_identity_after_resolution(job_id)
            self._remove_journal(stage_id)
            return 'rolled_back'

        record = self._validated_create_stage_record(stage_dir, job_id)
        if expected_record is not None and record != expected_record:
            raise OfficeJobCorruptionError([job_id])
        self._ensure_owner_identity(job_id, record['owner_id'])
        (stage_dir / job_id).replace(job_dir)
        self._fsync_directory(self.root)
        record = self._read_record(job_dir)
        self._job_data_size(job_dir, record)
        if expected_record is not None and record != expected_record:
            raise OfficeJobCorruptionError([job_id])
        self._remove_stage_dir(stage_dir)
        self._remove_journal(stage_id)
        return 'recovered'

    def _validated_create_stage_record(self, stage_dir: Path, job_id: str) -> dict[str, Any]:
        if not self._is_valid_stage_dir(stage_dir):
            raise ValueError('create transaction stage is invalid')
        entries = list(stage_dir.iterdir())
        if {entry.name for entry in entries} != {job_id}:
            raise ValueError('create transaction stage has unexpected evidence')
        staged_job = stage_dir / job_id
        if not self._is_valid_staged_job_dir(staged_job, job_id):
            raise ValueError('staged job is invalid')
        record = self._read_record(staged_job, expected_job_id=job_id)
        self._job_data_size(staged_job, record)
        return record

    def _validate_create_stage_for_cleanup(self, stage_dir: Path, job_id: str) -> None:
        if not stage_dir.exists() and not stage_dir.is_symlink():
            return
        if not self._is_valid_stage_dir(stage_dir):
            raise ValueError('create transaction stage is invalid')
        entries = list(stage_dir.iterdir())
        if not entries:
            return
        self._validated_create_stage_record(stage_dir, job_id)

    def _recover_artifact_transaction(self, journal: dict[str, Any]) -> str:
        job_id = journal.get('job_id')
        stage_id = journal.get('stage_id')
        artifact_name = journal.get('artifact_name')
        phase = journal.get('phase')
        old_record = journal.get('old_record')
        new_record = journal.get('new_record')
        if (
            not isinstance(job_id, str)
            or not _JOB_ID.fullmatch(job_id)
            or not isinstance(stage_id, str)
            or not _STAGE_ID.fullmatch(stage_id)
            or not isinstance(artifact_name, str)
            or artifact_name != safe_name(artifact_name)
            or artifact_name == 'job.json'
            or artifact_name.startswith(_TEMP_FILE_PREFIX)
            or phase not in {'prepared', 'backup_created', 'artifact_published', 'manifest_committed'}
            or not isinstance(old_record, dict)
            or not isinstance(new_record, dict)
        ):
            raise ValueError('invalid artifact journal')

        job_dir = self.root / job_id
        if not self._is_valid_job_dir(job_dir):
            raise ValueError('artifact transaction job is invalid')
        self._validate_record(job_dir, old_record, expected_job_id=job_id)
        self._validate_record(job_dir, new_record, expected_job_id=job_id)
        old_artifact = next((item for item in old_record['artifacts'] if item['filename'] == artifact_name), None)
        new_artifact = next((item for item in new_record['artifacts'] if item['filename'] == artifact_name), None)
        if new_artifact is None:
            raise ValueError('new artifact is missing from journal')

        stage_dir = self._staging_root / stage_id
        stage_exists = stage_dir.exists() or stage_dir.is_symlink()
        staged_path: Path | None = None
        backup_path: Path | None = None
        if stage_exists:
            staged_path, backup_path = self._validated_artifact_stage(
                stage_dir,
                old_artifact,
                new_artifact,
            )

        if self._active_record_matches(job_dir, new_record):
            self._remove_validated_recovery_stage(stage_dir, stage_exists)
            self._remove_journal(stage_id)
            return 'recovered'
        if self._active_record_matches(job_dir, old_record):
            self._remove_validated_recovery_stage(stage_dir, stage_exists)
            self._remove_journal(stage_id)
            return 'rolled_back'
        if not stage_exists:
            raise ValueError('artifact transaction stage is missing')

        if phase in {'prepared', 'backup_created'}:
            self._restore_artifact_transaction(
                job_dir,
                job_id,
                artifact_name,
                old_record,
                old_artifact,
                new_artifact,
                backup_path,
            )
            self._remove_validated_recovery_stage(stage_dir, True)
            self._remove_journal(stage_id)
            return 'rolled_back'

        self._publish_artifact_transaction(
            job_dir,
            job_id,
            artifact_name,
            new_record,
            old_artifact,
            new_artifact,
            staged_path,
        )
        self._remove_validated_recovery_stage(stage_dir, True)
        self._remove_journal(stage_id)
        return 'recovered'

    def _validated_artifact_stage(
        self,
        stage_dir: Path,
        old_artifact: dict[str, Any] | None,
        new_artifact: dict[str, Any],
    ) -> tuple[Path | None, Path | None]:
        if not self._is_valid_stage_dir(stage_dir):
            raise ValueError('artifact transaction stage is invalid')
        entries = list(stage_dir.iterdir())
        if any(entry.name not in {'new', 'backup'} for entry in entries):
            raise ValueError('artifact transaction stage has unexpected evidence')

        staged_path = stage_dir / 'new'
        if staged_path.exists() or staged_path.is_symlink():
            if (
                staged_path.is_symlink()
                or not staged_path.is_file()
                or staged_path.resolve().parent != stage_dir.resolve()
                or not self._artifact_file_matches(staged_path, new_artifact)
            ):
                raise ValueError('staged artifact is invalid')
        else:
            staged_path = None

        backup_path = stage_dir / 'backup'
        if backup_path.exists() or backup_path.is_symlink():
            if (
                old_artifact is None
                or backup_path.is_symlink()
                or not backup_path.is_file()
                or backup_path.resolve().parent != stage_dir.resolve()
                or not self._artifact_file_matches(backup_path, old_artifact)
            ):
                raise ValueError('staged backup is invalid')
        else:
            backup_path = None
        return staged_path, backup_path

    def _active_record_matches(self, job_dir: Path, expected: dict[str, Any]) -> bool:
        try:
            return self._read_record(job_dir) == expected and self._job_data_size(job_dir, expected) >= 0
        except OfficeJobCorruptionError:
            return False

    def _restore_artifact_transaction(
        self,
        job_dir: Path,
        job_id: str,
        artifact_name: str,
        old_record: dict[str, Any],
        old_artifact: dict[str, Any] | None,
        new_artifact: dict[str, Any],
        backup_path: Path | None,
    ) -> None:
        target = job_dir / artifact_name
        if backup_path is not None:
            if target.exists() or target.is_symlink():
                if (
                    target.is_symlink()
                    or not target.is_file()
                    or target.resolve().parent != job_dir.resolve()
                    or not (
                        self._artifact_file_matches(target, old_artifact)
                        or self._artifact_file_matches(target, new_artifact)
                    )
                ):
                    raise ValueError('artifact target cannot be rolled back')
                self._safe_unlink_artifact(target, job_id)
            backup_path.replace(target)
            self._fsync_directory(job_dir)
        elif old_artifact is not None:
            if not self._artifact_file_matches(target, old_artifact):
                raise ValueError('original artifact is not available')
        elif target.exists() or target.is_symlink():
            if (
                target.is_symlink()
                or not target.is_file()
                or target.resolve().parent != job_dir.resolve()
                or not self._artifact_file_matches(target, new_artifact)
            ):
                raise ValueError('new artifact cannot be removed')
            self._safe_unlink_artifact(target, job_id)

        self._write_record(job_dir, old_record)
        if not self._active_record_matches(job_dir, old_record):
            raise ValueError('rollback did not restore the active manifest')

    def _publish_artifact_transaction(
        self,
        job_dir: Path,
        job_id: str,
        artifact_name: str,
        new_record: dict[str, Any],
        old_artifact: dict[str, Any] | None,
        new_artifact: dict[str, Any],
        staged_path: Path | None,
    ) -> None:
        target = job_dir / artifact_name
        if staged_path is not None:
            if target.exists() or target.is_symlink():
                if (
                    target.is_symlink()
                    or not target.is_file()
                    or target.resolve().parent != job_dir.resolve()
                    or not (
                        self._artifact_file_matches(target, old_artifact)
                        or self._artifact_file_matches(target, new_artifact)
                    )
                ):
                    raise ValueError('artifact target cannot be published')
                if not self._artifact_file_matches(target, new_artifact):
                    self._safe_unlink_artifact(target, job_id)
                    staged_path.replace(target)
                    self._fsync_directory(job_dir)
            else:
                staged_path.replace(target)
                self._fsync_directory(job_dir)
        elif not self._artifact_file_matches(target, new_artifact):
            raise ValueError('new artifact is not available')

        self._write_record(job_dir, new_record)
        if not self._active_record_matches(job_dir, new_record):
            raise ValueError('recovery did not restore the active manifest')

    def _remove_validated_recovery_stage(self, stage_dir: Path, stage_exists: bool) -> None:
        if stage_exists:
            self._remove_stage_dir(stage_dir)

    def _preserve_unresolved_recovery(
        self,
        journal_path: Path | None,
        stage_id: str | None,
        reason: str,
    ) -> None:
        transaction_id = stage_id or (journal_path.name if journal_path is not None else 'unknown')
        recovery_id = uuid.uuid4().hex
        entry = self._recovery_quarantine_root / recovery_id
        metadata = {
            'recovery_id': recovery_id,
            'transaction_id': transaction_id,
            'reason': reason[:4000] or 'unknown recovery failure',
            'quarantined_at': _now_iso(),
            'journal_name': journal_path.name if journal_path is not None else None,
            'stage_id': stage_id,
            'journal_preserved': False,
            'stage_preserved': False,
        }
        entry.mkdir(parents=False, exist_ok=False)
        self._fsync_directory(self._recovery_quarantine_root)
        self._write_json_durable(entry / _RECOVERY_METADATA_NAME, metadata)
        if journal_path is not None and (journal_path.exists() or journal_path.is_symlink()):
            journal_path.replace(entry / _RECOVERY_JOURNAL_NAME)
            metadata['journal_preserved'] = True
            self._fsync_directory(journal_path.parent)
        if stage_id is not None:
            stage_dir = self._staging_root / stage_id
            if stage_dir.exists() or stage_dir.is_symlink():
                stage_dir.replace(entry / _RECOVERY_STAGE_NAME)
                metadata['stage_preserved'] = True
                self._fsync_directory(self._staging_root)
        self._write_json_durable(entry / _RECOVERY_METADATA_NAME, metadata)
        self._fsync_directory(entry)
        self._fsync_directory(self._recovery_quarantine_root)

    def _recovery_items_unlocked(self) -> list[dict[str, Any]]:
        if self._recovery_quarantine_root.is_symlink() or not self._recovery_quarantine_root.is_dir():
            raise OfficeJobCorruptionError(['recovery inventory'])
        items = [
            self._recovery_item_from_entry(entry)
            for entry in self._recovery_quarantine_root.iterdir()
        ]
        return sorted(
            items,
            key=lambda item: (
                str(item.get('quarantined_at') or ''),
                str(item.get('recovery_id') or item.get('management_token') or ''),
            ),
            reverse=True,
        )

    def _recovery_item_from_entry(self, entry: Path) -> dict[str, Any]:
        physical_bytes = self._physical_size_no_follow(entry)
        reason = self._direct_child_reason(
            self._recovery_quarantine_root,
            entry,
            _TRANSACTION_ID,
            'directory',
        )
        if reason is None:
            try:
                metadata_path = entry / _RECOVERY_METADATA_NAME
                if (
                    metadata_path.is_symlink()
                    or not metadata_path.is_file()
                    or metadata_path.resolve().parent != entry.resolve()
                ):
                    raise ValueError('recovery metadata is invalid')
                metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
                if not isinstance(metadata, dict) or metadata.get('recovery_id') != entry.name:
                    raise ValueError('recovery metadata is invalid')
                timestamp = metadata.get('quarantined_at')
                if not isinstance(timestamp, str) or not timestamp:
                    raise ValueError('recovery timestamp is invalid')
                datetime.fromisoformat(timestamp)
                transaction_id = metadata.get('transaction_id')
                if not isinstance(transaction_id, str) or not _STAGE_ID.fullmatch(transaction_id):
                    transaction_id = None
                evidence_reason = metadata.get('reason')
                if not isinstance(evidence_reason, str) or not evidence_reason:
                    raise ValueError('recovery reason is invalid')
                return {
                    'kind': 'recovery',
                    'management_token': None,
                    'recovery_id': entry.name,
                    'transaction_id': transaction_id,
                    'reason': evidence_reason,
                    'quarantined_at': timestamp,
                    'journal_preserved': metadata.get('journal_preserved') is True,
                    'stage_preserved': metadata.get('stage_preserved') is True,
                    'size_bytes': physical_bytes,
                    'physical_bytes': physical_bytes,
                }
            except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError, TypeError):
                reason = 'recovery metadata is invalid'
        return {
            'kind': 'corrupt',
            'management_token': self._management_token('recovery', entry),
            'recovery_id': None,
            'transaction_id': None,
            'reason': reason,
            'quarantined_at': self._evidence_timestamp(entry),
            'journal_preserved': False,
            'stage_preserved': False,
            'size_bytes': physical_bytes,
            'physical_bytes': physical_bytes,
        }

    def _unresolved_recovery_ids_unlocked(
        self,
        items: list[dict[str, Any]] | None = None,
    ) -> list[str]:
        return sorted(
            str(item['transaction_id'] or item['recovery_id'] or item['management_token'])
            for item in (self._recovery_items_unlocked() if items is None else items)
        )

    def _rollback_create_transaction(self, journal: dict[str, Any], *, remove_published_job: bool = False) -> None:
        stage_id = journal.get('stage_id')
        job_id = journal.get('job_id')
        expected_record = journal.get('record')
        if (
            not isinstance(stage_id, str)
            or not _STAGE_ID.fullmatch(stage_id)
            or not isinstance(job_id, str)
            or not _JOB_ID.fullmatch(job_id)
        ):
            raise ValueError('invalid create rollback journal')
        if expected_record is not None:
            self._validate_record(self.root / job_id, expected_record, expected_job_id=job_id)

        job_dir = self.root / job_id
        if job_dir.exists() or job_dir.is_symlink():
            if not self._is_valid_job_dir(job_dir):
                raise OfficeJobCorruptionError([job_id])
            active_record = self._read_record(job_dir)
            self._job_data_size(job_dir, active_record)
            if expected_record is not None and active_record != expected_record:
                raise OfficeJobCorruptionError([job_id])
            if remove_published_job:
                self._safe_delete_job_dir(job_dir)
                if job_dir.exists() or job_dir.is_symlink():
                    raise OSError(f'published job was not rolled back: {job_id}')

        stage_dir = self._staging_root / stage_id
        if stage_dir.exists() or stage_dir.is_symlink():
            self._validate_create_stage_for_cleanup(stage_dir, job_id)
            if expected_record is not None and any(stage_dir.iterdir()):
                staged_record = self._validated_create_stage_record(stage_dir, job_id)
                if staged_record != expected_record:
                    raise OfficeJobCorruptionError([job_id])
            self._remove_stage_dir(stage_dir)
        if not job_dir.exists() and not job_dir.is_symlink():
            self._remove_owner_identity_after_resolution(job_id)
        self._remove_journal(stage_id)

    def _rollback_artifact_transaction(self, journal: dict[str, Any]) -> None:
        job_id = journal.get('job_id')
        stage_id = journal.get('stage_id')
        artifact_name = journal.get('artifact_name')
        old_record = journal.get('old_record')
        new_record = journal.get('new_record')
        if (
            not isinstance(job_id, str)
            or not _JOB_ID.fullmatch(job_id)
            or not isinstance(stage_id, str)
            or not _STAGE_ID.fullmatch(stage_id)
            or not isinstance(artifact_name, str)
            or artifact_name != safe_name(artifact_name)
            or artifact_name == 'job.json'
            or artifact_name.startswith(_TEMP_FILE_PREFIX)
            or not isinstance(old_record, dict)
            or not isinstance(new_record, dict)
        ):
            raise ValueError('invalid artifact rollback journal')

        job_dir = self.root / job_id
        if not self._is_valid_job_dir(job_dir):
            raise OfficeJobCorruptionError([job_id])
        self._validate_record(job_dir, old_record, expected_job_id=job_id)
        self._validate_record(job_dir, new_record, expected_job_id=job_id)
        old_artifact = next((item for item in old_record['artifacts'] if item['filename'] == artifact_name), None)
        new_artifact = next((item for item in new_record['artifacts'] if item['filename'] == artifact_name), None)
        if new_artifact is None:
            raise ValueError('new artifact is missing from rollback journal')

        stage_dir = self._staging_root / stage_id
        _staged_path, backup_path = self._validated_artifact_stage(
            stage_dir,
            old_artifact,
            new_artifact,
        )
        current = self._read_record(job_dir)
        if current != old_record and current != new_record:
            raise OfficeJobCorruptionError([job_id])
        if not self._active_record_matches(job_dir, old_record):
            self._restore_artifact_transaction(
                job_dir,
                job_id,
                artifact_name,
                old_record,
                old_artifact,
                new_artifact,
                backup_path,
            )
        if not self._active_record_matches(job_dir, old_record):
            raise OfficeJobCorruptionError([job_id])
        self._remove_stage_dir(stage_dir)
        self._remove_journal(stage_id)

    def _reconcile_orphan_stage_dirs_unlocked(
        self,
        purge_result: OfficeJobPurgeResult | None = None,
    ) -> tuple[int, int]:
        reconciled = 0
        reconciled_bytes = 0
        active_stage_ids = {
            path.stem
            for path in self._transactions_root.iterdir()
            if path.is_file() and not path.is_symlink() and path.suffix == '.json' and _STAGE_ID.fullmatch(path.stem)
        }
        for stage_dir in list(self._staging_root.iterdir()):
            if not _STAGE_ID.fullmatch(stage_dir.name) or stage_dir.name in active_stage_ids:
                continue
            if stage_dir.is_symlink() or not stage_dir.is_dir() or stage_dir.resolve().parent != self._staging_root:
                continue
            reconciled_bytes += self._directory_size(stage_dir)
            self._preserve_unresolved_recovery(
                None,
                stage_dir.name,
                'orphan transaction stage has no recoverable journal',
            )
            reconciled += 1

        for job_dir in self._job_entries():
            if not self._is_valid_job_dir(job_dir):
                continue
            try:
                initial = self._read_record(job_dir)
                owner = self._owner_identity_for_valid_record(job_dir, initial)
            except OfficeJobCorruptionError:
                continue
            with self._owner_capacity_lock(owner):
                try:
                    record = self._read_record(job_dir)
                    if self._owner_identity_for_valid_record(job_dir, record) != owner:
                        continue
                    self._job_data_size(job_dir, record)
                except OfficeJobCorruptionError:
                    continue
                for path in list(job_dir.iterdir()):
                    if not path.name.startswith(_TEMP_FILE_PREFIX):
                        continue
                    if path.is_symlink() or not path.is_file() or path.resolve().parent != job_dir.resolve():
                        continue
                    identity = self._replay_entry_identity(path)
                    replay_evidence = {
                        'scope': 'job_temp',
                        'name': path.name,
                        'operation': 'purge_orphan_temp',
                        'identity': identity,
                        'signature': identity,
                        'parent_identity': self._job_parent_replay_identity(job_dir, record),
                        'job_id': job_dir.name,
                    }
                    try:
                        outcome = self._safe_delete_managed_file(
                            path,
                            job_dir,
                            path.name,
                            entry_kind='orphan_temp',
                            parent_id=job_dir.name,
                        )
                    except OfficeJobDeletionError as exc:
                        if exc.outcome['removed']:
                            reconciled_bytes += exc.outcome['physical_bytes']
                            reconciled += 1
                        if purge_result is not None:
                            self._record_partial_deletion(
                                purge_result,
                                exc.outcome,
                                replay_evidence,
                            )
                            purge_result['maintenance']['orphan_stage_dirs'] = reconciled
                            purge_result['maintenance']['orphan_stage_bytes'] = reconciled_bytes
                        raise
                    reconciled_bytes += outcome['physical_bytes']
                    reconciled += 1
        return reconciled, reconciled_bytes

    def _is_valid_stage_dir(self, path: Path) -> bool:
        try:
            return (
                _STAGE_ID.fullmatch(path.name) is not None
                and not path.is_symlink()
                and path.is_dir()
                and path.resolve().parent == self._staging_root
            )
        except OSError:
            return False

    def _is_valid_staged_job_dir(self, path: Path, job_id: str) -> bool:
        try:
            if path.is_symlink() or not path.is_dir() or path.name != job_id:
                return False
            self._read_record(path, expected_job_id=job_id)
            return True
        except (OSError, OfficeJobCorruptionError):
            return False

    def _remove_stage_dir(self, stage_dir: Path) -> None:
        if not stage_dir.exists() and not stage_dir.is_symlink():
            return
        if not self._is_valid_stage_dir(stage_dir):
            raise ValueError('invalid transaction stage directory')
        shutil.rmtree(stage_dir)
        self._fsync_directory(self._staging_root)
        if stage_dir.exists() or stage_dir.is_symlink():
            raise OSError(f'transaction stage was not deleted: {stage_dir.name}')

    def _journal_path(self, stage_id: str) -> Path:
        if not _STAGE_ID.fullmatch(stage_id):
            raise ValueError('invalid transaction stage id')
        return self._transactions_root / f'{stage_id}.json'

    def _write_journal(self, stage_id: str, journal: dict[str, Any]) -> None:
        self._write_json_durable(self._journal_path(stage_id), journal)

    def _existing_journal_path(self, stage_id: str) -> Path | None:
        path = self._journal_path(stage_id)
        return path if path.exists() or path.is_symlink() else None

    def _remove_journal(self, stage_id: str) -> None:
        path = self._journal_path(stage_id)
        if not path.exists() and not path.is_symlink():
            return
        if path.is_symlink() or not path.is_file() or path.resolve().parent != self._transactions_root:
            raise ValueError('invalid transaction journal')
        path.unlink()
        self._fsync_directory(self._transactions_root)
        if path.exists() or path.is_symlink():
            raise OSError(f'transaction journal was not deleted: {path.name}')

    def _safe_unlink_artifact(self, path: Path, job_id: str) -> None:
        if path.parent != self.root / job_id or path.is_symlink() or not path.is_file() or path.resolve().parent != (self.root / job_id).resolve():
            raise OfficeJobCorruptionError([job_id])
        path.unlink(missing_ok=True)
        self._fsync_directory(path.parent)


    @staticmethod
    def _path_size(path: Path) -> int:
        if path.is_symlink():
            return 0
        if path.is_file():
            return path.stat().st_size
        if path.is_dir():
            return OfficeJobStore._directory_size(path)
        return 0
    @staticmethod
    def _physical_size_no_follow(path: Path) -> int:
        try:
            entry = path.lstat()
        except OSError:
            return 0
        if stat.S_ISREG(entry.st_mode) or stat.S_ISLNK(entry.st_mode):
            return entry.st_size
        if not stat.S_ISDIR(entry.st_mode):
            return 0
        total = 0
        try:
            with os.scandir(path) as children:
                for child in children:
                    total += OfficeJobStore._physical_size_no_follow(Path(child.path))
        except OSError:
            return total
        return total

    @staticmethod
    def _entry_exists_no_follow(path: Path) -> bool:
        try:
            path.lstat()
        except FileNotFoundError:
            return False
        except OSError:
            return True
        return True

    def _deletion_outcome_after_rmtree(
        self,
        entry: Path,
        outcome: OfficeJobDeletionOutcome,
    ) -> None:
        if not self._entry_exists_no_follow(entry):
            outcome['removed'] = True
            outcome['partial_bytes_removed'] = outcome['physical_bytes']
            return
        remaining_bytes = self._physical_size_no_follow(entry)
        outcome['partial_bytes_removed'] = max(0, outcome['physical_bytes'] - remaining_bytes)

    def _safe_delete_managed_directory(
        self,
        entry: Path,
        parent: Path,
        entry_id: str,
        *,
        entry_kind: str,
        parent_id: str,
    ) -> OfficeJobDeletionOutcome:
        outcome: OfficeJobDeletionOutcome = {
            'entry_id': entry_id,
            'entry_kind': entry_kind,
            'parent_id': parent_id,
            'physical_bytes': self._physical_size_no_follow(entry),
            'partial_bytes_removed': 0,
            'removed': False,
            'durably_synced': False,
            'durability': 'pending',
            'retry_required': True,
        }
        try:
            shutil.rmtree(entry)
        except Exception as exc:
            self._deletion_outcome_after_rmtree(entry, outcome)
            raise OfficeJobDeletionError(outcome, exc) from exc
        self._deletion_outcome_after_rmtree(entry, outcome)
        if not outcome['removed']:
            raise OfficeJobDeletionError(
                outcome,
                OSError(f'managed directory was not deleted: {entry_id}'),
            )
        try:
            self._apply_directory_sync_outcome(outcome, parent)
        except Exception as exc:
            raise OfficeJobDeletionError(outcome, exc) from exc

        return outcome
    def _safe_delete_managed_file(
        self,
        entry: Path,
        parent: Path,
        entry_id: str,
        *,
        entry_kind: str,
        parent_id: str,
    ) -> OfficeJobDeletionOutcome:
        if (
            parent.is_symlink()
            or not parent.is_dir()
            or entry.parent != parent
            or entry.is_symlink()
            or not entry.is_file()
            or entry.resolve().parent != parent.resolve()
        ):
            raise OfficeJobCorruptionError([entry_id])
        outcome: OfficeJobDeletionOutcome = {
            'entry_id': entry_id,
            'entry_kind': entry_kind,
            'parent_id': parent_id,
            'physical_bytes': self._physical_size_no_follow(entry),
            'partial_bytes_removed': 0,
            'removed': False,
            'durably_synced': False,
            'durability': 'pending',
            'retry_required': True,
        }
        try:
            entry.unlink()
        except Exception as exc:
            if not self._entry_exists_no_follow(entry):
                outcome['removed'] = True
                outcome['partial_bytes_removed'] = outcome['physical_bytes']
            raise OfficeJobDeletionError(outcome, exc) from exc
        if self._entry_exists_no_follow(entry):
            raise OfficeJobDeletionError(
                outcome,
                OSError(f'managed file was not deleted: {entry_id}'),
            )
        outcome['removed'] = True
        outcome['partial_bytes_removed'] = outcome['physical_bytes']
        try:
            self._apply_directory_sync_outcome(outcome, parent)
        except Exception as exc:
            raise OfficeJobDeletionError(outcome, exc) from exc

        return outcome

    def _safe_delete_corrupt_evidence_child(
        self,
        root: Path,
        entry: Path,
        management_token: str,
    ) -> OfficeJobDeletionOutcome:
        if (
            root.is_symlink()
            or not root.is_dir()
            or entry.parent != root
            or not self._entry_exists_no_follow(entry)
        ):
            raise OfficeJobCorruptionError(['managed evidence'])
        try:
            mode = entry.lstat().st_mode
        except OSError as exc:
            raise OfficeJobCorruptionError(['managed evidence']) from exc
        if stat.S_ISDIR(mode):
            if entry.is_symlink() or entry.resolve().parent != root.resolve():
                raise OfficeJobCorruptionError(['managed evidence'])
            return self._safe_delete_managed_directory(
                entry,
                root,
                management_token,
                entry_kind='corrupt_evidence',
                parent_id=root.name.lstrip('.'),
            )
        if stat.S_ISLNK(mode):
            pass
        elif stat.S_ISREG(mode):
            if entry.resolve().parent != root.resolve():
                raise OfficeJobCorruptionError(['managed evidence'])
        else:
            raise OfficeJobCorruptionError(['managed evidence'])
        outcome: OfficeJobDeletionOutcome = {
            'entry_id': management_token,
            'entry_kind': 'corrupt_evidence',
            'parent_id': root.name.lstrip('.'),
            'physical_bytes': self._physical_size_no_follow(entry),
            'partial_bytes_removed': 0,
            'removed': False,
            'durably_synced': False,
            'durability': 'pending',
            'retry_required': True,
        }
        try:
            entry.unlink()
        except Exception as exc:
            if not self._entry_exists_no_follow(entry):
                outcome['removed'] = True
                outcome['partial_bytes_removed'] = outcome['physical_bytes']
            raise OfficeJobDeletionError(outcome, exc) from exc
        if self._entry_exists_no_follow(entry):
            raise OfficeJobDeletionError(
                outcome,
                OSError('managed evidence was not deleted'),
            )
        outcome['removed'] = True
        outcome['partial_bytes_removed'] = outcome['physical_bytes']
        try:
            self._apply_directory_sync_outcome(outcome, root)
        except Exception as exc:
            raise OfficeJobDeletionError(outcome, exc) from exc
        return outcome

    @staticmethod
    def _directory_size(root: Path) -> int:
        total = 0
        for current_root, directories, files in os.walk(root, followlinks=False):
            root_path = Path(current_root)
            directories[:] = [
                name for name in directories if not (root_path / name).is_symlink()
            ]
            for name in files:
                path = root_path / name
                if not path.is_symlink() and path.is_file():
                    total += path.stat().st_size
        return total
    @staticmethod
    def _managed_regular_file_entries(root: Path) -> int:
        if root.is_symlink() or not root.is_dir():
            return 0
        return sum(
            1
            for path in root.rglob('*')
            if not path.is_symlink() and path.is_file()
        )

    def _safe_delete_job_dir(self, job_dir: Path) -> OfficeJobDeletionOutcome:
        if (
            not _JOB_ID.fullmatch(job_dir.name)
            or job_dir.parent != self.root
            or job_dir.is_symlink()
            or not job_dir.is_dir()
            or job_dir.resolve().parent != self.root
        ):
            raise FileNotFoundError('invalid job directory')
        outcome: OfficeJobDeletionOutcome | None = None
        try:
            with self._job_lifecycle_lock(job_dir.name):
                outcome = self._safe_delete_managed_directory(
                    job_dir,
                    self.root,
                    job_dir.name,
                    entry_kind='job',
                    parent_id=job_dir.name,
                )
            return outcome
        except OfficeJobDeletionError:
            raise
        except Exception as exc:
            if outcome is not None:
                raise OfficeJobDeletionError(outcome, exc) from exc
            raise

    def _read_record(self, job_dir: Path, *, expected_job_id: str | None = None) -> dict[str, Any]:
        path = job_dir / 'job.json'
        record_id = expected_job_id or job_dir.name
        try:
            if path.is_symlink() or not path.is_file():
                raise ValueError('job metadata not found')
            record = json.loads(path.read_text(encoding='utf-8'))
            self._validate_record(job_dir, record, expected_job_id=record_id)
        except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError, TypeError) as exc:
            raise OfficeJobCorruptionError([record_id]) from exc
        return record

    @staticmethod
    def _validate_record(job_dir: Path, record: object, *, expected_job_id: str | None = None) -> None:
        if not isinstance(record, dict):
            raise ValueError('job metadata must be an object')
        job_id = expected_job_id or job_dir.name
        if not _JOB_ID.fullmatch(job_id) or record.get('job_id') != job_id:
            raise ValueError('job_id does not match job directory')
        if not isinstance(record.get('service'), str) or not record['service']:
            raise ValueError('service must be a non-empty string')
        strict_owner_id(record.get('owner_id'))
        if record.get('status') not in {'running', 'completed', 'failed'}:
            raise ValueError('job status is invalid')
        for field in ('created_at', 'updated_at'):
            value = record.get(field)
            if not isinstance(value, str) or not value:
                raise ValueError(f'{field} must be a timestamp string')
            datetime.fromisoformat(value)
        if not isinstance(record.get('request_summary'), dict):
            raise ValueError('request_summary must be an object')
        warnings = record.get('warnings')
        if not isinstance(warnings, list) or any(not isinstance(item, str) for item in warnings):
            raise ValueError('warnings must be a list of strings')
        if record.get('error') is not None and not isinstance(record['error'], str):
            raise ValueError('error must be a string or null')
        artifacts = record.get('artifacts')
        if not isinstance(artifacts, list):
            raise ValueError('artifacts must be a list')
        seen_names: set[str] = set()
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                raise ValueError('artifact must be an object')
            filename = artifact.get('filename')
            if (
                not isinstance(filename, str)
                or filename != safe_name(filename)
                or filename == 'job.json'
                or filename.startswith(_TEMP_FILE_PREFIX)
                or filename in seen_names
            ):
                raise ValueError('artifact filename is invalid')
            seen_names.add(filename)
            if not isinstance(artifact.get('media_type'), str) or not artifact['media_type']:
                raise ValueError('artifact media_type is invalid')
            size_bytes = artifact.get('size_bytes')
            if isinstance(size_bytes, bool) or not isinstance(size_bytes, int) or size_bytes < 0:
                raise ValueError('artifact size is invalid')
            sha256 = artifact.get('sha256')
            if not isinstance(sha256, str) or not _SHA256.fullmatch(sha256):
                raise ValueError('artifact sha256 is invalid')
            expected_url = f'/api/v1/office-tools/jobs/{job_id}/artifacts/{filename}'
            if artifact.get('download_url') != expected_url:
                raise ValueError('artifact download_url is invalid')

    @staticmethod
    def _fsync_file(path: Path) -> None:
        with path.open('r+b') as handle:
            os.fsync(handle.fileno())

    @staticmethod
    def _is_windows_unsupported_directory_fsync_error(exc: OSError) -> bool:
        winerror = getattr(exc, 'winerror', None)
        if winerror in {1, 5, 6, 50, 87}:
            return True
        return winerror is None and exc.errno in {
            errno.EACCES,
            errno.EBADF,
            errno.EINVAL,
            errno.ENOTSUP,
            errno.EOPNOTSUPP,
        }


    def _apply_directory_sync_outcome(self, outcome: dict[str, Any], path: Path) -> None:
        synced = self._fsync_directory(path)
        outcome['durably_synced'] = synced is not False
        outcome['retry_required'] = False
        if outcome['durably_synced']:
            outcome['durability'] = 'synced'
        else:
            outcome['durability'] = 'platform_best_effort'
    @staticmethod
    def _outcome_synced(durability: object) -> bool:
        return durability == 'synced'

    def _apply_owner_directory_sync_outcome(
        self,
        outcome: dict[str, Any],
        path: Path,
        *,
        identity: bool = False,
    ) -> None:
        sync: dict[str, Any] = {
            'durably_synced': False,
            'durability': 'pending',
            'retry_required': True,
        }
        self._apply_directory_sync_outcome(sync, path)
        if identity:
            outcome['owner_identity_durability'] = sync['durability']
            outcome['owner_identity_durably_synced'] = self._outcome_synced(sync['durability'])
        else:
            outcome['durability'] = sync['durability']
            outcome['durably_synced'] = self._outcome_synced(sync['durability'])
        outcome['retry_required'] = (
            outcome.get('durability') == 'pending'
            or outcome.get('owner_identity_durability') == 'pending'
        )
    @classmethod
    def _fsync_directory(cls, path: Path) -> bool:
        try:
            descriptor = os.open(path, os.O_RDONLY)
        except OSError as exc:
            if os.name == 'nt' and cls._is_windows_unsupported_directory_fsync_error(exc):
                return False
            raise
        try:
            os.fsync(descriptor)
        except OSError as exc:
            if os.name == 'nt' and cls._is_windows_unsupported_directory_fsync_error(exc):
                return False
            raise
        finally:
            os.close(descriptor)
        return True

    @classmethod
    def _write_bytes_durable(cls, target: Path, data: bytes) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=_TEMP_FILE_PREFIX, dir=target.parent)
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, 'wb') as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            tmp_path.replace(target)
            cls._fsync_directory(target.parent)
        finally:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    @classmethod
    def _write_json_durable(cls, target: Path, value: dict[str, Any]) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=_TEMP_FILE_PREFIX, suffix='.json', dir=target.parent)
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                json.dump(value, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            tmp_path.replace(target)
            cls._fsync_directory(target.parent)
        finally:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    @classmethod
    def _write_record(cls, job_dir: Path, record: dict[str, Any]) -> None:
        cls._write_json_durable(job_dir / 'job.json', record)
