def test_html_content_endpoint_returns_csp_header(csrf_client, client) -> None:
    csrf_client.post('/api/v1/admin/newsletters/sync')

    response = client.get('/api/v1/newsletters/2/content/html')

    assert response.status_code == 200
    assert 'Content-Security-Policy' in response.headers
    assert '<script' not in response.json()['content_html']


def test_markdown_content_endpoint_returns_rendered_html(client) -> None:
    response = client.get('/api/v1/newsletters/1/content/markdown')

    assert response.status_code == 200
    assert '<h1>' in response.json()['content_html']


def test_pdf_content_endpoint_returns_pdf(csrf_client, client) -> None:
    csrf_client.post('/api/v1/admin/newsletters/sync')

    response = client.get('/api/v1/newsletters/2/content/pdf')

    assert response.status_code == 200
    assert response.headers['content-type'].startswith('application/pdf')
