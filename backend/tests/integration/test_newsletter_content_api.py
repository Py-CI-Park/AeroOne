from app.modules.newsletter.models.newsletter import AssetType, NewsletterAsset


def test_html_content_endpoint_returns_csp_header(csrf_client, client) -> None:
    csrf_client.post('/api/v1/admin/newsletters/sync')

    response = client.get('/api/v1/newsletters/2/content/html')

    assert response.status_code == 200
    assert 'Content-Security-Policy' in response.headers
    # 신뢰 로컬 HTML 은 원본 그대로 서빙 — JS 렌더 본문이 살도록 <script> 보존.
    assert '<script' in response.json()['content_html']


def test_html_content_endpoint_returns_404_when_import_file_is_missing(csrf_client, client) -> None:
    csrf_client.post('/api/v1/admin/newsletters/sync')
    with client.app.state.db.session() as session:
        asset = session.query(NewsletterAsset).filter(NewsletterAsset.asset_type == AssetType.HTML).first()
        assert asset is not None
        newsletter_id = asset.newsletter_id
        asset.file_path = 'newsletter_20990101_missing.html'
        session.commit()

    response = client.get(f'/api/v1/newsletters/{newsletter_id}/content/html')

    assert response.status_code == 404
    assert response.json()['detail'] == 'Newsletter asset file is missing from the import/storage directory'


def test_download_endpoint_returns_404_when_import_file_is_missing(csrf_client, client) -> None:
    csrf_client.post('/api/v1/admin/newsletters/sync')
    with client.app.state.db.session() as session:
        asset = session.query(NewsletterAsset).filter(NewsletterAsset.asset_type == AssetType.PDF).first()
        assert asset is not None
        newsletter_id = asset.newsletter_id
        asset.file_path = 'Aerospace Daily News_20990101_missing.pdf'
        session.commit()

    response = client.get(f'/api/v1/newsletters/{newsletter_id}/download/pdf')

    assert response.status_code == 404
    assert response.json()['detail'] == 'Newsletter asset file is missing from the import/storage directory'


def test_markdown_content_endpoint_returns_rendered_html(client) -> None:
    response = client.get('/api/v1/newsletters/1/content/markdown')

    assert response.status_code == 200
    assert '<h1>' in response.json()['content_html']


def test_markdown_storage_file_is_not_publicly_static_served(client) -> None:
    response = client.get('/storage/markdown/newsletters/sample-welcome.md')

    assert response.status_code == 404


def test_pdf_content_endpoint_returns_pdf(csrf_client, client) -> None:
    csrf_client.post('/api/v1/admin/newsletters/sync')

    response = client.get('/api/v1/newsletters/2/content/pdf')

    assert response.status_code == 200
    assert response.headers['content-type'].startswith('application/pdf')
