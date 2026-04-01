from __future__ import annotations

from pathlib import Path

from app.modules.shared.storage.service import StorageService


class PdfDeliveryService:
    def __init__(self, storage_service: StorageService) -> None:
        self.storage_service = storage_service

    def resolve_pdf_path(self, relative_path: str) -> Path:
        return self.storage_service.resolve_external_relative_path(relative_path)
