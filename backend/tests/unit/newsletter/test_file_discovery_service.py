from app.modules.newsletter.models.newsletter import AssetType
from app.modules.newsletter.services.file_discovery_service import FileDiscoveryService


def test_scan_pairs_html_and_pdf_and_ignores_debug(test_paths) -> None:
    service = FileDiscoveryService(test_paths['import_root'])

    issues = service.scan()

    assert list(issues.keys()) == ['20260206']
    issue = issues['20260206']
    assert AssetType.HTML in issue.assets
    assert AssetType.PDF in issue.assets
    assert all(not asset.relative_path.endswith('_debug.html') for asset in issue.assets.values())
    assert issue.title_candidate == '테스트 뉴스레터'


def test_scan_returns_empty_when_import_root_is_missing(tmp_path) -> None:
    service = FileDiscoveryService(tmp_path / 'missing-import-root')

    assert service.scan() == {}
