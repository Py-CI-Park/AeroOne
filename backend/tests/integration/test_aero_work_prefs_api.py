"""사용자 LLM 프로필 — GET/PUT 왕복·검증·기록 통합 검증."""

from __future__ import annotations


def test_prefs_anonymous_rejected(client) -> None:
    assert client.get('/api/v1/aero-work/prefs').status_code == 401


def test_prefs_roundtrip_and_activity(csrf_client) -> None:
    assert csrf_client.get('/api/v1/aero-work/prefs').json()['llm_mode'] == 'default'

    updated = csrf_client.put('/api/v1/aero-work/prefs', json={'llm_mode': 'local'})
    assert updated.status_code == 200, updated.text
    assert updated.json()['llm_mode'] == 'local'
    assert csrf_client.get('/api/v1/aero-work/prefs').json()['llm_mode'] == 'local'

    activities = csrf_client.get('/api/v1/aero-work/activity').json()['activities']
    assert activities[0]['kind'] == 'settings.llm_mode'

    back = csrf_client.put('/api/v1/aero-work/prefs', json={'llm_mode': 'default'})
    assert back.json()['llm_mode'] == 'default'


def test_prefs_rejects_unknown_mode(csrf_client) -> None:
    resp = csrf_client.put('/api/v1/aero-work/prefs', json={'llm_mode': 'cloud'})
    assert resp.status_code == 422
