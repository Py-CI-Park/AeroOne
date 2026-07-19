"""문서 최종 저장 승인 상태기계 — 요청→대기(다운로드 409)→승인→다운로드 통합 검증."""

from __future__ import annotations

import io
import zipfile


def test_save_request_requires_auth(client) -> None:
    assert client.post('/api/v1/aero-work/document/save-request', json={'title': 'x'}).status_code == 401


def test_approval_flow(csrf_client) -> None:
    created = csrf_client.post(
        '/api/v1/aero-work/document/save-request',
        json={'title': '협조 요청', 'body': '자료 제출 협조', 'format': 'official'},
    )
    assert created.status_code == 201, created.text
    doc = created.json()
    assert doc['status'] == 'pending'
    doc_id = doc['id']

    listing = csrf_client.get('/api/v1/aero-work/document/saved').json()['documents']
    assert listing[0]['id'] == doc_id and listing[0]['status'] == 'pending'

    blocked = csrf_client.get(f'/api/v1/aero-work/document/saved/{doc_id}/download')
    assert blocked.status_code == 409  # 승인 전 다운로드 차단(승인형 정책)

    approved = csrf_client.post(f'/api/v1/aero-work/document/saved/{doc_id}/approve')
    assert approved.status_code == 200 and approved.json()['status'] == 'approved'

    downloaded = csrf_client.get(f'/api/v1/aero-work/document/saved/{doc_id}/download')
    assert downloaded.status_code == 200
    section = zipfile.ZipFile(io.BytesIO(downloaded.content)).read('Contents/section0.xml').decode('utf-8')
    assert '수신' in section and '1. 자료 제출 협조' in section  # 시행문 위계 적용

    activities = [a['kind'] for a in csrf_client.get('/api/v1/aero-work/activity').json()['activities'][:3]]
    assert 'document.approve' in activities and 'document.save_request' in activities

    assert csrf_client.delete(f'/api/v1/aero-work/document/saved/{doc_id}').status_code == 204
    assert csrf_client.get('/api/v1/aero-work/document/saved').json()['documents'] == []
