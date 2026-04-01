from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.modules.newsletter.models.newsletter import AssetType, Newsletter, NewsletterAsset, SourceType
from app.modules.newsletter.repositories.newsletter_repository import NewsletterRepository
from app.modules.newsletter.services.file_discovery_service import DiscoveredIssue, FileDiscoveryService


@dataclass(slots=True)
class ImportResult:
    created: int = 0
    updated: int = 0
    deactivated: int = 0
    skipped: int = 0
    issues: int = 0


class NewsletterImportService:
    def __init__(self, db: Session, import_root: Path) -> None:
        self.db = db
        self.import_root = import_root.resolve()
        self.discovery_service = FileDiscoveryService(self.import_root)
        self.repository = NewsletterRepository(db)
        self._was_created = False

    def sync(self) -> ImportResult:
        discovered = self.discovery_service.scan()
        result = ImportResult(issues=len(discovered))
        for issue in discovered.values():
            if self._upsert_issue(issue):
                result.created += 1 if self._was_created else 0
                result.updated += 0 if self._was_created else 1
            else:
                result.skipped += 1
        result.deactivated += self._deactivate_missing(set(discovered.keys()))
        return result

    def _upsert_issue(self, issue: DiscoveredIssue) -> bool:
        self._was_created = False
        newsletter = self.repository.get_by_source_identifier(issue.issue_key)
        primary_asset = issue.assets.get(AssetType.HTML) or issue.assets.get(AssetType.PDF)
        source_type = SourceType.HTML if AssetType.HTML in issue.assets else SourceType.PDF
        title = issue.title_candidate or f'Aerospace Daily News {issue.issue_key}'
        checksum = primary_asset.checksum if primary_asset else None
        if newsletter is None:
            newsletter = Newsletter(
                title=title,
                slug=f'newsletter-{issue.issue_key}',
                description='Imported from local newsletter files.',
                source_type=source_type,
                source_identifier=issue.issue_key,
                published_at=issue.published_at,
                source_checksum=checksum,
                source_mtime=issue.published_at,
                is_active=True,
            )
            self.db.add(newsletter)
            self.db.flush()
            self._was_created = True
        changed = self._was_created
        if newsletter.title != title:
            newsletter.title = title
            changed = True
        if newsletter.source_type != source_type:
            newsletter.source_type = source_type
            changed = True
        newsletter.is_active = True
        newsletter.published_at = issue.published_at
        newsletter.source_mtime = issue.published_at
        newsletter.source_checksum = checksum
        asset_map = {asset.asset_type: asset for asset in newsletter.assets}
        for asset_type, discovered_asset in issue.assets.items():
            asset = asset_map.get(asset_type)
            if asset is None:
                asset = NewsletterAsset(asset_type=asset_type, newsletter=newsletter)
                newsletter.assets.append(asset)
                changed = True
            if (
                asset.file_path != discovered_asset.relative_path
                or asset.checksum != discovered_asset.checksum
                or asset.file_size != discovered_asset.file_size
            ):
                asset.file_path = discovered_asset.relative_path
                asset.checksum = discovered_asset.checksum
                asset.file_size = discovered_asset.file_size
                changed = True
            asset.is_primary = asset_type == primary_asset.asset_type if primary_asset else False
        newsletter.source_file_path = primary_asset.relative_path if primary_asset else None
        newsletter.markdown_file_path = next(
            (asset.file_path for asset in newsletter.assets if asset.asset_type == AssetType.MARKDOWN),
            None,
        )
        return changed

    def _deactivate_missing(self, issue_keys: set[str]) -> int:
        deactivated = 0
        for newsletter in self.repository.list_imported_with_external_assets():
            if newsletter.source_identifier not in issue_keys and newsletter.is_active:
                newsletter.is_active = False
                deactivated += 1
        return deactivated
