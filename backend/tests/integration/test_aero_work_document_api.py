"""Aero Work 문서작성(HWPX) REST — 실 앱 HTTP 스택 + 다운로드 + 기록 통합 검증."""

from __future__ import annotations

import io
import zipfile


def test_document_anonymous_rejected(client) -> None:
    resp = client.post('/api/v1/aero-work/document/hwpx', json={'title': 'x', 'body': 'y'})
    assert resp.status_code == 401


def test_document_requires_csrf(client) -> None:
    assert client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'}).status_code == 200
    resp = client.post('/api/v1/aero-work/document/hwpx', json={'title': 'x', 'body': 'y'})
    assert resp.status_code == 403


def test_document_generates_valid_hwpx_and_records(csrf_client) -> None:
    resp = csrf_client.post(
        '/api/v1/aero-work/document/hwpx',
        json={'title': '출장 결과 보고', 'body': '대전 방문함.\n특이사항 없음.'},
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers['content-type'] == 'application/hwp+zip'
    assert 'attachment' in resp.headers['content-disposition']

    archive = zipfile.ZipFile(io.BytesIO(resp.content))
    assert archive.infolist()[0].filename == 'mimetype'
    assert archive.read('mimetype').decode('utf-8') == 'application/hwp+zip'
    assert '출장 결과 보고' in archive.read('Contents/section0.xml').decode('utf-8')

    activities = csrf_client.get('/api/v1/aero-work/activity').json()['activities']
    assert activities[0]['kind'] == 'document.generate'
    assert '출장 결과 보고' in activities[0]['summary']
