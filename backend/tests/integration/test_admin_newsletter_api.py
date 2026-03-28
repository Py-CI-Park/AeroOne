def test_admin_update_newsletter_metadata(csrf_client, client) -> None:
    csrf_client.post('/api/v1/admin/newsletters/sync')

    response = csrf_client.patch('/api/v1/admin/newsletters/2', json={'title': '수정된 제목', 'description': '수정됨'})
    assert response.status_code == 200
    detail = client.get('/api/v1/newsletters/newsletter-20260206')
    assert detail.status_code == 200
    assert detail.json()['title'] == '수정된 제목'


def test_admin_create_markdown_newsletter(csrf_client) -> None:
    response = csrf_client.post(
        '/api/v1/admin/newsletters',
        json={
            'title': '새 Markdown',
            'summary': '요약',
            'markdown_body': '# 새 문서\n\n본문',
            'source_type': 'markdown',
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['slug'] == '새-markdown'
    assert payload['default_asset_type'] == 'markdown'
