def test_list_endpoint_returns_imported_and_markdown_newsletters(csrf_client, client) -> None:
    csrf_client.post('/api/v1/admin/newsletters/sync')

    response = client.get('/api/v1/newsletters')

    assert response.status_code == 200
    payload = response.json()
    slugs = {item['slug'] for item in payload}
    assert 'newsletter-20260206' in slugs
    assert 'markdown-welcome' in slugs
    assert all('_debug' not in item['slug'] for item in payload)


def test_detail_endpoint_returns_available_assets(csrf_client, client) -> None:
    csrf_client.post('/api/v1/admin/newsletters/sync')

    response = client.get('/api/v1/newsletters/newsletter-20260206')

    assert response.status_code == 200
    payload = response.json()
    asset_types = {asset['asset_type'] for asset in payload['available_assets']}
    assert asset_types == {'html', 'pdf'}
    assert payload['default_asset_type'] == 'html'
