from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import hash_file_bytes
from app.modules.admin.schemas import AssetHealthItem, AssetHealthResponse, ConfigHealthItem, ConfigHealthResponse
from app.modules.newsletter.models.newsletter import AssetType
from app.modules.newsletter.repositories.newsletter_repository import NewsletterRepository
from app.modules.read_tracking.models.read_event import NewsletterReadEvent
from app.modules.shared.storage.service import StorageError, StorageService


def read_tracking_summary(db: Session) -> dict[str, int]:
    row = db.execute(select(func.count(NewsletterReadEvent.id), func.coalesce(func.sum(NewsletterReadEvent.read_count), 0))).one()
    return {'rows': int(row[0] or 0), 'total_reads': int(row[1] or 0)}


def _asset_root(storage: StorageService, asset_type: AssetType) -> tuple[str, Path]:
    if asset_type == AssetType.MARKDOWN:
        return 'markdown', storage.managed_root
    return 'import', storage.import_root


def _asset_path(storage: StorageService, asset_type: AssetType, relative_path: str) -> Path:
    if asset_type == AssetType.MARKDOWN:
        return storage.resolve_managed_relative_path(relative_path)
    return storage.resolve_external_relative_path(relative_path)


def _path_readable(path: Path) -> bool:
    try:
        if not path.exists():
            return False
        if path.is_dir():
            next(path.iterdir(), None)
        else:
            with path.open('rb'):
                pass
        return True
    except OSError:
        return False


def _root_missing_remediation(root: Path) -> str:
    return f'루트 경로 {root}를 확인하세요. _database/storage 위치를 가리켜야 하며 환경변수 override 오설정을 점검하세요.'


def config_health(settings: Settings) -> ConfigHealthResponse:
    roots = [
        ('storage', settings.storage_root_path),
        ('import', settings.import_root),
        ('document', settings.document_root_path),
        ('civil', settings.civil_aircraft_root_path),
        ('nsa', settings.nsa_root_path),
        ('markdown', settings.markdown_root),
        ('thumbnails', settings.thumbnails_root),
    ]
    return ConfigHealthResponse(
        roots=[
            ConfigHealthItem(kind=kind, resolved_path=str(path), exists=path.exists(), readable=_path_readable(path))
            for kind, path in roots
        ]
    )


def asset_health(db: Session, settings: Settings) -> AssetHealthResponse:
    storage = StorageService(settings)
    newsletters = NewsletterRepository(db).list_admin()
    items: list[AssetHealthItem] = []
    missing = 0
    mismatch = 0
    misconfig = 0
    ok_count = 0
    for newsletter in newsletters:
        for asset in newsletter.assets:
            root_kind, root = _asset_root(storage, asset.asset_type)
            exists = False
            size: int | None = None
            actual_checksum: str | None = None
            ok = False
            status_value: str = 'missing'
            error_code: str | None = 'FILE_NOT_FOUND'
            remediation = '해석된 자산 경로에 파일이 없습니다. 가져오기 루트와 DB 파일 경로를 확인하세요.'
            resolved_path: Path | None = None
            if not root.exists() or not root.is_dir() or not _path_readable(root):
                status_value = 'misconfig'
                error_code = 'ROOT_MISSING'
                remediation = _root_missing_remediation(root)
            else:
                try:
                    resolved_path = _asset_path(storage, asset.asset_type, asset.file_path)
                    exists = resolved_path.exists()
                    if exists:
                        data = resolved_path.read_bytes()
                        size = len(data)
                        actual_checksum = hash_file_bytes(data)
                        ok = not asset.checksum or asset.checksum == actual_checksum
                        if ok:
                            status_value = 'ok'
                            error_code = None
                            remediation = '정상입니다.'
                        else:
                            status_value = 'checksum_mismatch'
                            error_code = 'CHECKSUM_MISMATCH'
                            remediation = '파일은 있지만 DB 체크섬과 다릅니다. 원본 파일 변경 여부를 확인하고 재가져오기를 실행하세요.'
                    else:
                        status_value = 'missing'
                        error_code = 'FILE_NOT_FOUND'
                except StorageError:
                    status_value = 'misconfig'
                    error_code = 'PATH_ESCAPE'
                    remediation = 'DB 파일 경로가 허용된 루트 밖을 가리킵니다. 경로 값을 수정하거나 재가져오기 하세요.'
                except OSError:
                    exists = False
                    ok = False
                    status_value = 'missing'
                    error_code = 'FILE_NOT_FOUND'
            if status_value == 'ok':
                ok_count += 1
            elif status_value == 'missing':
                missing += 1
            elif status_value == 'checksum_mismatch':
                mismatch += 1
            else:
                misconfig += 1
            items.append(
                AssetHealthItem(
                    newsletter_id=newsletter.id,
                    newsletter_title=newsletter.title,
                    asset_type=asset.asset_type.value,
                    file_path=asset.file_path,
                    exists=exists,
                    file_size=size,
                    checksum=actual_checksum,
                    expected_checksum=asset.checksum,
                    ok=ok,
                    status=status_value,
                    resolved_root=str(root),
                    resolved_path=str(resolved_path) if resolved_path is not None else None,
                    root_kind=root_kind,
                    remediation=remediation,
                    error_code=error_code,
                )
            )
    return AssetHealthResponse(ok=ok_count, missing=missing, checksum_mismatch=mismatch, misconfig=misconfig, items=items)
