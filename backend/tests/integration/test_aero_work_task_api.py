"""Aero Work 할 일 REST의 인증·CSRF·CRUD·소유자 격리 통합 검증."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.modules.auth.repositories import UserRepository


def test_task_anonymous_rejected(client) -> None:
    assert client.get('/api/v1/aero-work/tasks').status_code == 401


def test_task_mutation_requires_csrf(client) -> None:
    assert client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'}).status_code == 200
    assert client.post('/api/v1/aero-work/tasks', json={'title': '초안'}).status_code == 403


def test_task_crud_roundtrip(csrf_client) -> None:
    created = csrf_client.post('/api/v1/aero-work/tasks', json={'title': '예산 보고서', 'due_date': '2026-07-21', 'tags': '예산'})
    assert created.status_code == 201, created.text
    task = created.json()
    assert task['status'] == 'todo'
    task_id = task['id']

    patched = csrf_client.patch(f'/api/v1/aero-work/tasks/{task_id}', json={'status': 'done'})
    assert patched.status_code == 200
    assert patched.json()['done_at'] is not None
    assert [item['id'] for item in csrf_client.get('/api/v1/aero-work/tasks', params={'status': 'done'}).json()['tasks']] == [task_id]
    assert csrf_client.delete(f'/api/v1/aero-work/tasks/{task_id}').status_code == 204
    assert csrf_client.get('/api/v1/aero-work/tasks').json()['tasks'] == []


def test_task_other_user_isolation(app, csrf_client) -> None:
    created = csrf_client.post('/api/v1/aero-work/tasks', json={'title': '관리자 업무'})
    task_id = created.json()['id']
    with app.state.db.session() as session:
        UserRepository(session).create(username='task-user', password_hash=hash_password('password'), role='user')
    other = TestClient(app)
    login = other.post('/api/v1/auth/login', json={'username': 'task-user', 'password': 'password'})
    other.headers.update({'x-csrf-token': login.json()['csrf_token']})
    assert other.get('/api/v1/aero-work/tasks').json()['tasks'] == []
    assert other.patch(f'/api/v1/aero-work/tasks/{task_id}', json={'status': 'done'}).status_code == 404
    assert other.delete(f'/api/v1/aero-work/tasks/{task_id}').status_code == 404
