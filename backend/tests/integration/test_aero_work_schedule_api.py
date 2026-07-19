"""Aero Work 일정 REST — 실 앱 HTTP 스택(라우팅·CSRF·인증·소유자 스코프) 통합 검증."""

from __future__ import annotations


def test_schedule_anonymous_rejected(client) -> None:
    assert client.get('/api/v1/aero-work/schedule/events').status_code == 401


def test_schedule_mutation_requires_csrf(client) -> None:
    login = client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'})
    assert login.status_code == 200
    resp = client.post(
        '/api/v1/aero-work/schedule/events',
        json={'title': 'x', 'starts_at': '2026-07-20T10:00:00'},
    )
    assert resp.status_code == 403


def test_schedule_crud_and_range_flow(csrf_client) -> None:
    created = csrf_client.post(
        '/api/v1/aero-work/schedule/events',
        json={
            'title': '주간 회의',
            'starts_at': '2026-07-20T10:00:00',
            'ends_at': '2026-07-20T11:00:00',
            'location': '3층 회의실',
        },
    )
    assert created.status_code == 201, created.text
    event = created.json()
    assert event['title'] == '주간 회의'
    event_id = event['id']

    listing = csrf_client.get('/api/v1/aero-work/schedule/events')
    assert listing.status_code == 200
    assert any(item['id'] == event_id for item in listing.json()['events'])

    in_range = csrf_client.get(
        '/api/v1/aero-work/schedule/events',
        params={'start': '2026-07-20T00:00:00', 'end': '2026-07-21T00:00:00'},
    )
    assert any(item['id'] == event_id for item in in_range.json()['events'])

    out_of_range = csrf_client.get(
        '/api/v1/aero-work/schedule/events',
        params={'start': '2026-08-01T00:00:00', 'end': '2026-08-02T00:00:00'},
    )
    assert all(item['id'] != event_id for item in out_of_range.json()['events'])

    patched = csrf_client.patch(
        f'/api/v1/aero-work/schedule/events/{event_id}', json={'title': '확정 주간 회의'}
    )
    assert patched.status_code == 200
    assert patched.json()['title'] == '확정 주간 회의'

    deleted = csrf_client.delete(f'/api/v1/aero-work/schedule/events/{event_id}')
    assert deleted.status_code == 204
    assert csrf_client.get('/api/v1/aero-work/schedule/events').json()['events'] == []


def test_schedule_rejects_reversed_range(csrf_client) -> None:
    resp = csrf_client.post(
        '/api/v1/aero-work/schedule/events',
        json={'title': '역전', 'starts_at': '2026-07-20T12:00:00', 'ends_at': '2026-07-20T10:00:00'},
    )
    assert resp.status_code == 400


def test_schedule_update_missing_returns_404(csrf_client) -> None:
    resp = csrf_client.patch('/api/v1/aero-work/schedule/events/999999', json={'title': 'nope'})
    assert resp.status_code == 404
