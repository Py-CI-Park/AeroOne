def test_sync_endpoint_imports_newsletters(csrf_client) -> None:
    response = csrf_client.post('/api/v1/admin/newsletters/sync')

    assert response.status_code == 200
    payload = response.json()
    assert payload['created'] == 1
    assert payload['issues'] == 1
