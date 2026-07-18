from __future__ import annotations


def _latest_newsletter_id(client) -> int:
    response = client.get('/api/v1/newsletters/latest')
    assert response.status_code == 200
    return response.json()['id']


def test_beacon_records_read_unauthenticated(client) -> None:
    newsletter_id = _latest_newsletter_id(client)
    response = client.post(f'/api/v1/newsletters/{newsletter_id}/read')
    assert response.status_code == 200
    assert response.json() == {'recorded': True}


def test_beacon_missing_newsletter_returns_404(client) -> None:
    response = client.post('/api/v1/newsletters/999999/read')
    assert response.status_code == 404

    # 미존재 id 는 행을 만들지 않는다 — 관리자 조회가 비어 있어야 한다.
    login = client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'})
    client.headers.update({'x-csrf-token': login.json()['csrf_token']})
    overview = client.get('/api/v1/admin/read-events')
    assert overview.status_code == 200
    assert overview.json()['events'] == []


def test_admin_read_events_requires_auth(client) -> None:
    response = client.get('/api/v1/admin/read-events')
    assert response.status_code == 401


def test_admin_read_events_lists_after_beacon(csrf_client) -> None:
    newsletter_id = _latest_newsletter_id(csrf_client)
    csrf_client.post(f'/api/v1/newsletters/{newsletter_id}/read')

    response = csrf_client.get('/api/v1/admin/read-events')
    assert response.status_code == 200
    body = response.json()
    assert body['summaries']
    assert body['summaries'][0]['newsletter_id'] == newsletter_id
    assert body['summaries'][0]['total_reads'] >= 1
    assert any(event['newsletter_id'] == newsletter_id for event in body['events'])


def test_purge_requires_auth(client) -> None:
    response = client.post('/api/v1/admin/read-events/purge')
    assert response.status_code == 401


def test_purge_rejected_without_csrf_header(client) -> None:
    # 로그인은 했지만 x-csrf-token 헤더를 일부러 보내지 않음 → CSRF 거부(403).
    login = client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'})
    assert login.status_code == 200
    response = client.post('/api/v1/admin/read-events/purge')
    assert response.status_code == 403


def test_purge_deletes_with_csrf(csrf_client) -> None:
    newsletter_id = _latest_newsletter_id(csrf_client)
    csrf_client.post(f'/api/v1/newsletters/{newsletter_id}/read')

    response = csrf_client.post('/api/v1/admin/read-events/purge')
    assert response.status_code == 200
    assert response.json()['deleted'] >= 1

    after = csrf_client.get('/api/v1/admin/read-events')
    assert after.json()['events'] == []


def test_recent_reads_mine_empty_before_any_beacon(client) -> None:
    response = client.get('/api/v1/newsletters/read-events/mine')
    assert response.status_code == 200
    assert response.json() == {'items': []}
    assert response.headers['cache-control'] == 'no-store'


def test_recent_reads_mine_lists_after_beacon(client) -> None:
    latest = client.get('/api/v1/newsletters/latest').json()
    client.post(f"/api/v1/newsletters/{latest['id']}/read")

    response = client.get('/api/v1/newsletters/read-events/mine?limit=6')
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    body = response.json()
    assert len(body['items']) == 1
    assert body['items'][0]['slug'] == latest['slug']
    assert body['items'][0]['title']
    assert body['items'][0]['last_seen_at']


def test_recent_reads_mine_limit_is_clamped_not_rejected(client) -> None:
    newsletter_id = _latest_newsletter_id(client)
    client.post(f'/api/v1/newsletters/{newsletter_id}/read')

    too_low = client.get('/api/v1/newsletters/read-events/mine?limit=0')
    too_high = client.get('/api/v1/newsletters/read-events/mine?limit=999')

    assert too_low.status_code == 200
    assert too_high.status_code == 200
    assert len(too_low.json()['items']) == 1
    assert len(too_high.json()['items']) == 1
