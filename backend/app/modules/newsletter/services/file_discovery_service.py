from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re

from bs4 import BeautifulSoup

from app.core.security import hash_file_bytes
from app.modules.newsletter.models.newsletter import AssetType
from app.modules.newsletter.services.utils import issue_key_to_datetime

HTML_RE = re.compile(r'^newsletter_(\d{8})\.html$')
PDF_RE = re.compile(r'^Aerospace Daily News_(\d{8})\.pdf$')


@dataclass(slots=True)
class DiscoveredAsset:
    issue_key: str
    asset_type: AssetType
    relative_path: str
    checksum: str
    file_size: int
    title_candidate: str | None = None


@dataclass(slots=True)
class DiscoveredIssue:
    issue_key: str
    published_at: object
    assets: dict[AssetType, DiscoveredAsset] = field(default_factory=dict)
    title_candidate: str | None = None


class FileDiscoveryService:
    def __init__(self, import_root: Path) -> None:
        self.import_root = import_root.resolve()

    def scan(self) -> dict[str, DiscoveredIssue]:
        issues: dict[str, DiscoveredIssue] = {}
        if not self.import_root.exists():
            return issues
        for path in sorted(self.import_root.iterdir()):
            if not path.is_file() or path.name.endswith('_debug.html'):
                continue
            asset = self._parse_asset(path)
            if asset is None:
                continue
            issue = issues.setdefault(
                asset.issue_key,
                DiscoveredIssue(issue_key=asset.issue_key, published_at=issue_key_to_datetime(asset.issue_key)),
            )
            issue.assets[asset.asset_type] = asset
            if asset.title_candidate and not issue.title_candidate:
                issue.title_candidate = asset.title_candidate
        return issues

    def _parse_asset(self, path: Path) -> DiscoveredAsset | None:
        html_match = HTML_RE.match(path.name)
        pdf_match = PDF_RE.match(path.name)
        if not html_match and not pdf_match:
            return None
        issue_key = html_match.group(1) if html_match else pdf_match.group(1)
        file_bytes = path.read_bytes()
        title_candidate = self._extract_html_title(path) if html_match else None
        return DiscoveredAsset(
            issue_key=issue_key,
            asset_type=AssetType.HTML if html_match else AssetType.PDF,
            relative_path=str(path.relative_to(self.import_root)),
            checksum=hash_file_bytes(file_bytes),
            file_size=len(file_bytes),
            title_candidate=title_candidate,
        )

    def _extract_html_title(self, path: Path) -> str | None:
        soup = BeautifulSoup(path.read_text(encoding='utf-8'), 'html.parser')
        return soup.title.text.strip() if soup.title and soup.title.text else None
