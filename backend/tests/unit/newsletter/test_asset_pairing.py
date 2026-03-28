from app.modules.newsletter.services.file_discovery_service import FileDiscoveryService


def test_issue_key_pairing_uses_same_date_for_html_and_pdf(test_paths) -> None:
    service = FileDiscoveryService(test_paths['import_root'])

    issues = service.scan()

    assert len(issues) == 1
    issue = issues['20260206']
    assert set(asset.asset_type.value for asset in issue.assets.values()) == {'html', 'pdf'}
