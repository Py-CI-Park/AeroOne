from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import Settings, get_settings
from app.core.path_guard import PathGuardError, ensure_within_root


class StorageError(ValueError):
    pass


class StorageService:
    def __init__(self, settings_or_import_root: Settings | Path | None = None, managed_root: Path | None = None) -> None:
        if isinstance(settings_or_import_root, Settings):
            self.settings = settings_or_import_root
            self.import_root = self.settings.import_root
            self.managed_root = self.settings.managed_storage_root
        elif isinstance(settings_or_import_root, Path) and managed_root is not None:
            self.settings = get_settings()
            self.import_root = settings_or_import_root.resolve()
            self.managed_root = managed_root.resolve()
        else:
            self.settings = get_settings()
            self.import_root = self.settings.import_root
            self.managed_root = self.settings.managed_storage_root

    def resolve_external_relative_path(self, relative_path: str) -> Path:
        try:
            return ensure_within_root(self.import_root, self.import_root / relative_path)
        except PathGuardError as exc:
            raise StorageError(str(exc)) from exc

    def resolve_import_relative(self, relative_path: str) -> Path:
        return self.resolve_external_relative_path(relative_path)

    def resolve_managed_relative_path(self, relative_path: str) -> Path:
        try:
            return ensure_within_root(self.managed_root, self.managed_root / relative_path)
        except PathGuardError as exc:
            raise StorageError(str(exc)) from exc

    def resolve_markdown_relative(self, relative_path: str) -> Path:
        return self.resolve_managed_relative_path(relative_path)

    def read_external_text(self, relative_path: str, encoding: str = 'utf-8') -> str:
        return self.resolve_external_relative_path(relative_path).read_text(encoding=encoding)

    def read_managed_text(self, relative_path: str, encoding: str = 'utf-8') -> str:
        return self.resolve_managed_relative_path(relative_path).read_text(encoding=encoding)

    def relative_to_import_root(self, path: Path) -> str:
        try:
            return str(ensure_within_root(self.import_root, path).relative_to(self.import_root)).replace('\\', '/')
        except PathGuardError as exc:
            raise StorageError(str(exc)) from exc

    def relative_to_storage_root(self, path: Path) -> str:
        try:
            return str(ensure_within_root(self.managed_root, path).relative_to(self.managed_root)).replace('\\', '/')
        except PathGuardError as exc:
            raise StorageError(str(exc)) from exc

    def write_markdown(self, filename_stem: str, content: str) -> str:
        safe_name = f'{filename_stem}-{uuid4().hex[:8]}.md'
        target = self.settings.markdown_root / safe_name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')
        return self.relative_to_storage_root(target)

    def overwrite_relative_text(self, relative_path: str, content: str) -> str:
        path = self.resolve_managed_relative_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        return self.relative_to_storage_root(path)

    def save_markdown_text(self, markdown_root: Path, slug: str, content: str) -> str:
        markdown_root.mkdir(parents=True, exist_ok=True)
        path = markdown_root / f'{slug}.md'
        path.write_text(content, encoding='utf-8')
        return self.relative_to_storage_root(path)

    async def save_thumbnail(self, upload_file: UploadFile, target: Path | str) -> str:
        if isinstance(target, Path):
            destination_dir = target
            filename_base = uuid4().hex
        else:
            destination_dir = self.settings.thumbnails_root
            filename_base = target
        destination_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(upload_file.filename or 'upload.bin').suffix or '.bin'
        destination = destination_dir / f'{filename_base}-{uuid4().hex[:8]}{suffix}'
        destination.write_bytes(await upload_file.read())
        return self.relative_to_storage_root(destination)


def sha256_for_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()
