def test_login_sets_session_and_csrf_cookie(client) -> None:
    response = client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'})

    assert response.status_code == 200
    assert 'csrf_token' in response.cookies
    set_cookie = response.headers.get('set-cookie', '')
    assert 'httponly' in set_cookie.lower()


def test_admin_route_requires_auth(client) -> None:
    response = client.get('/api/v1/admin/newsletters')
    assert response.status_code == 401
