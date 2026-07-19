"""Aero Work 실행기록 REST — 행위 자동 기록 + 최신순 조회 통합 검증."""

from __future__ import annotations

from pathlib import Path


def test_activity_anonymous_rejected(client) -> None:
    assert client.get('/api/v1/aero-work/activity').status_code == 401


def test_schedule_actions_are_recorded(csrf_client) -> None:
    created = csrf_client.post(
        '/api/v1/aero-work/schedule/events',
        json={'title': '주간 회의', 'starts_at': '2026-07-20T10:00:00'},
    )
    assert created.status_code == 201
    event_id = created.json()['id']
    assert csrf_client.patch(
        f'/api/v1/aero-work/schedule/events/{event_id}', json={'title': '확정 주간 회의'}
    ).status_code == 200
    assert csrf_client.delete(f'/api/v1/aero-work/schedule/events/{event_id}').status_code == 204

    activity = csrf_client.get('/api/v1/aero-work/activity')
    assert activity.status_code == 200
    items = activity.json()['activities']
    assert [item['kind'] for item in items[:3]] == ['schedule.delete', 'schedule.update', 'schedule.create']
    assert '주간 회의' in items[2]['summary']


def test_knowledge_register_is_recorded(csrf_client, tmp_path: Path) -> None:
    root = tmp_path / 'kb'
    root.mkdir()
    (root / 'note.md').write_text('hello', encoding='utf-8')
    resp = csrf_client.post(
        '/api/v1/aero-work/knowledge/folders', json={'name': '사내 규정', 'path': str(root)}
    )
    assert resp.status_code == 201

    items = csrf_client.get('/api/v1/aero-work/activity').json()['activities']
    assert items[0]['kind'] == 'knowledge.register'
    assert '사내 규정' in items[0]['summary']
