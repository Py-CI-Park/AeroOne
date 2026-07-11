"""파일 기반 작업 저장소 — MVP ``core/job_store.py`` 를 AeroOne 로 포팅.

MVP 계약(정규식 ``[0-9a-f]{32}`` job_id, ``safe_name`` 경로 방어, atomic write)을
그대로 유지하되, 두 가지를 더한다.

1. **소유권**: ``create(service, owner_id=...)`` 가 ``owner_id`` 를 ``job.json`` 에 기록한다.
   라우트 계층은 ``owner_id`` 와 세션 사용자를 대조해 타인 접근을 403 으로 막는다.
2. **루트 주입**: 생성자가 루트 경로를 직접 받는다(테스트에서 tmp 루트 주입 가능).
   실제 배포 루트는 ``from_settings`` 가 ``project_root/backend/data/office_jobs`` 로 계산한다.

DB 모델을 추가하지 않는다(파일 저장). 산출물 렌더링 자체는 각 도구 서비스가 채운다.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import Settings

_SAFE_NAME = re.compile(r'[^A-Za-z0-9._-]+')
_JOB_ID = re.compile(r'[0-9a-f]{32}')


def safe_name(value: str, fallback: str = 'artifact') -> str:
    """artifact 파일명을 ``[A-Za-z0-9._-]`` 로 정규화하고 디렉터리 성분을 제거한다."""

    value = Path(value or fallback).name
    cleaned = _SAFE_NAME.sub('_', value).strip('._')
    return cleaned[:160] or fallback


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class OfficeJobStore:
    """파일시스템 기반 job 저장소. 인터페이스는 향후 DB/오브젝트 스토리지 교체를 견딘다."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_settings(cls, settings: Settings) -> 'OfficeJobStore':
        return cls(settings.project_root / 'backend' / 'data' / 'office_jobs')

    def create(self, service: str, owner_id: int, request_summary: dict[str, Any] | None = None) -> dict[str, Any]:
        job_id = uuid.uuid4().hex
        now = _now_iso()
        job_dir = self.root / job_id
        job_dir.mkdir(parents=True, exist_ok=False)
        record: dict[str, Any] = {
            'job_id': job_id,
            'service': service,
            'owner_id': owner_id,
            'status': 'running',
            'created_at': now,
            'updated_at': now,
            'request_summary': request_summary or {},
            'warnings': [],
            'artifacts': [],
            'error': None,
        }
        self._write_record(job_dir, record)
        return record

    def job_dir(self, job_id: str) -> Path:
        if not _JOB_ID.fullmatch(job_id):
            raise FileNotFoundError('invalid job id')
        path = self.root / job_id
        if not path.is_dir():
            raise FileNotFoundError(job_id)
        return path

    def get(self, job_id: str) -> dict[str, Any]:
        path = self.job_dir(job_id) / 'job.json'
        return json.loads(path.read_text(encoding='utf-8'))

    def write_text(self, job_id: str, filename: str, text: str, media_type: str) -> Path:
        return self.write_bytes(job_id, filename, text.encode('utf-8'), media_type)

    def write_bytes(self, job_id: str, filename: str, data: bytes, media_type: str) -> Path:
        job_dir = self.job_dir(job_id)
        path = job_dir / safe_name(filename)
        path.write_bytes(data)
        self._register_artifact(job_id, path, media_type)
        return path

    def complete(self, job_id: str, warnings: list[str] | None = None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        record = self.get(job_id)
        updated = {
            **record,
            'status': 'completed',
            'updated_at': _now_iso(),
            'warnings': list(dict.fromkeys([*record.get('warnings', []), *(warnings or [])])),
            **(extra or {}),
        }
        self._write_record(self.job_dir(job_id), updated)
        return updated

    def fail(self, job_id: str, error: str, warnings: list[str] | None = None) -> dict[str, Any]:
        record = self.get(job_id)
        updated = {
            **record,
            'status': 'failed',
            'updated_at': _now_iso(),
            'error': error[:4000],
            'warnings': list(dict.fromkeys([*record.get('warnings', []), *(warnings or [])])),
        }
        self._write_record(self.job_dir(job_id), updated)
        return updated

    def artifact_path(self, job_id: str, filename: str) -> Path:
        job_dir = self.job_dir(job_id).resolve()
        path = (job_dir / safe_name(filename)).resolve()
        if job_dir not in path.parents or not path.is_file():
            raise FileNotFoundError(filename)
        return path

    def create_bundle(self, job_id: str) -> Path:
        job_dir = self.job_dir(job_id)
        bundle = job_dir / f'aeroone_{job_id}.zip'
        with zipfile.ZipFile(bundle, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(job_dir.iterdir()):
                if path.is_file() and path != bundle:
                    archive.write(path, arcname=path.name)
        return bundle

    def _register_artifact(self, job_id: str, path: Path, media_type: str) -> None:
        record = self.get(job_id)
        artifact = {
            'filename': path.name,
            'media_type': media_type,
            'size_bytes': path.stat().st_size,
            'sha256': _sha256_file(path),
            'download_url': f'/api/v1/office-tools/jobs/{job_id}/artifacts/{path.name}',
        }
        artifacts = [a for a in record.get('artifacts', []) if a.get('filename') != path.name]
        artifacts.append(artifact)
        updated = {**record, 'artifacts': artifacts, 'updated_at': _now_iso()}
        self._write_record(self.job_dir(job_id), updated)

    @staticmethod
    def _write_record(job_dir: Path, record: dict[str, Any]) -> None:
        target = job_dir / 'job.json'
        fd, tmp_name = tempfile.mkstemp(prefix='job_', suffix='.json', dir=job_dir)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                json.dump(record, handle, ensure_ascii=False, indent=2)
            Path(tmp_name).replace(target)
        finally:
            tmp = Path(tmp_name)
            if tmp.exists():
                tmp.unlink(missing_ok=True)
