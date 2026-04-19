def test_create_category_and_tag(csrf_client) -> None:
    category_response = csrf_client.post('/api/v1/admin/categories', json={'name': '공지', 'description': '공지'})
    tag_response = csrf_client.post('/api/v1/admin/tags', json={'name': '중요'})

    assert category_response.status_code == 200
    assert tag_response.status_code == 200
    assert category_response.json()['slug'] == '공지'
    assert tag_response.json()['slug'] == '중요'
