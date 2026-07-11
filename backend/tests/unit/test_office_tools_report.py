"""보고서 스튜디오(svc01) 검증.

- Markdown → sanitize HTML 생성(제목 유도, 이미지 base64 임베드).
- ``<script>``/이벤트 핸들러 제거(sanitize), 오프라인 순도(외부 리소스 0).
- AI 편집 시 원문에 없는 수치가 생기면 해당 조각 폐기(수치 환각 차단).
- job artifact(source/md/html/manifest) 등록, 소유자만 다운로드.
- 잘못된 확장자/ai_mode 는 라우트에서 422, 미로그인은 401.

JobStore 는 tmp 루트로 주입해 실제 저장소를 오염시키지 않는다.
"""

from __future__ import annotations

import base64
import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.modules.auth.models import User
from app.modules.office_tools.api.jobs import get_office_job_store
from app.modules.office_tools.core.job_store import OfficeJobStore
from app.modules.office_tools.services.report import (
    enhance_markdown,
    generate_report,
    markdown_to_body,
)

# 1x1 투명 PNG(테스트용 최소 이미지).
_PNG_BYTES = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
)


def _admin_id(app) -> int:
    with app.state.db.session() as session:
        return session.execute(select(User).where(User.username == 'admin')).scalar_one().id


# --- 렌더 경로: markdown → sanitize HTML -----------------------------------------

def test_markdown_to_body_strips_script_and_handlers() -> None:
    body = markdown_to_body('# 제목\n\n<script>alert(1)</script>\n\n<a href="x" onclick="evil()">링크</a>')
    assert '<script' not in body.lower()
    assert 'onclick' not in body.lower()
    assert '<h1' in body.lower()


# --- 수치 환각 차단(enhancer) ----------------------------------------------------

class _FakeClient:
    def __init__(self, content: str) -> None:
        self._content = content

    def chat(self, messages, temperature: float = 0.2, max_tokens: int = 1200) -> str:  # noqa: ARG002
        return self._content


def test_enhance_drops_chunk_with_new_numbers() -> None:
    # 원문에는 없는 수치(999)를 편집 결과가 도입 → 해당 조각 폐기 + 경고.
    fake = _FakeClient('{"markdown": "## 요약\\n매출 999억으로 성장했다.", "warnings": []}')
    result = enhance_markdown('## 요약\n매출이 성장했다.', 'polish', fake)
    assert '999' not in result.markdown
    assert any('수치' in w for w in result.warnings)


def test_enhance_without_client_keeps_original_with_warning() -> None:
    result = enhance_markdown('## 본문\n내용', 'executive', None)
    assert result.markdown.strip() == '## 본문\n내용'
    assert result.llm_used is False
    assert any('활성 LLM 연결이 없어' in w for w in result.warnings)


def test_enhance_none_mode_is_passthrough() -> None:
    result = enhance_markdown('# 그대로', 'none', _FakeClient('{"markdown":"바뀜"}'))
    assert result.markdown == '# 그대로'
    assert result.llm_used is False


# --- generate_report 서비스(직접 호출) -------------------------------------------

def test_generate_report_produces_offline_html(app, tmp_path: Path) -> None:
    store = OfficeJobStore(tmp_path / 'office_jobs')
    record = generate_report(
        store=store,
        owner_id=_admin_id(app),
        markdown_filename='입력.md',
        markdown_bytes='# 분기 보고\n\n본문입니다.'.encode('utf-8'),
        assets={},
        title='',
        subtitle='요약',
        document_version='1.0',
        tags='분기',
        ai_mode='none',
        client=None,
        app_version='9.9.9',
        max_upload_bytes=10_000_000,
        max_markdown_chars=200_000,
    )
    assert record['status'] == 'completed'
    # 제목은 첫 # 헤더에서 유도된다.
    assert record['title'] == '분기 보고'
    filenames = {a['filename'] for a in record['artifacts']}
    assert {'source_original.md', 'aeroone_report.md', 'aeroone_report.html', 'manifest.json'} <= filenames
    # 자립형 HTML + 외부 리소스 0.
    assert record['html'].startswith('<!doctype html>')
    assert 'https://' not in record['html']


def test_generate_report_embeds_image_as_data_uri(app, tmp_path: Path) -> None:
    store = OfficeJobStore(tmp_path / 'office_jobs')
    record = generate_report(
        store=store,
        owner_id=_admin_id(app),
        markdown_filename='report.md',
        markdown_bytes='# 사진\n\n![그림](pic.png)'.encode('utf-8'),
        assets={'pic.png': _PNG_BYTES},
        title='사진 보고',
        subtitle='',
        document_version='',
        tags='',
        ai_mode='none',
        client=None,
        app_version='9.9.9',
        max_upload_bytes=10_000_000,
        max_markdown_chars=200_000,
    )
    assert 'data:image/png;base64,' in record['html']


def test_generate_report_rejects_oversized_markdown(app, tmp_path: Path) -> None:
    store = OfficeJobStore(tmp_path / 'office_jobs')
    with pytest.raises(ValueError):
        generate_report(
            store=store,
            owner_id=_admin_id(app),
            markdown_filename='big.md',
            markdown_bytes=b'# x\n' + b'a' * 100,
            assets={},
            title='',
            subtitle='',
            document_version='',
            tags='',
            ai_mode='none',
            client=None,
            app_version='9.9.9',
            max_upload_bytes=10,
            max_markdown_chars=200_000,
        )


# --- 라우트(HTTP) ----------------------------------------------------------------

def test_generate_requires_login(client: TestClient) -> None:
    resp = client.post(
        '/api/v1/office-tools/reports/generate',
        files={'markdown_file': ('a.md', b'# hi', 'text/markdown')},
    )
    assert resp.status_code == 401


def test_generate_route_returns_report(app, csrf_client: TestClient, tmp_path: Path) -> None:
    store = OfficeJobStore(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        resp = csrf_client.post(
            '/api/v1/office-tools/reports/generate',
            files={'markdown_file': ('report.md', '# 제목\n\n본문'.encode('utf-8'), 'text/markdown')},
            data={'ai_mode': 'none', 'subtitle': '부제'},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body['title'] == '제목'
        assert body['preview_url'].endswith('/aeroone_report.html')
        assert body['html'].startswith('<!doctype html>')
        # 소유자는 HTML 산출물을 내려받는다.
        art = csrf_client.get(f"/api/v1/office-tools/jobs/{body['job_id']}/artifacts/aeroone_report.html")
        assert art.status_code == 200
        assert art.text.startswith('<!doctype html>')
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)


def test_generate_route_rejects_bad_extension(csrf_client: TestClient) -> None:
    resp = csrf_client.post(
        '/api/v1/office-tools/reports/generate',
        files={'markdown_file': ('report.exe', b'x', 'application/octet-stream')},
        data={'ai_mode': 'none'},
    )
    assert resp.status_code == 422


def test_generate_route_rejects_bad_ai_mode(csrf_client: TestClient) -> None:
    resp = csrf_client.post(
        '/api/v1/office-tools/reports/generate',
        files={'markdown_file': ('report.md', b'# hi', 'text/markdown')},
        data={'ai_mode': 'wrong-mode'},
    )
    assert resp.status_code == 422


def test_generate_route_accepts_image_zip(app, csrf_client: TestClient, tmp_path: Path) -> None:
    store = OfficeJobStore(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr('pic.png', _PNG_BYTES)
    try:
        resp = csrf_client.post(
            '/api/v1/office-tools/reports/generate',
            files={
                'markdown_file': ('report.md', '# 사진\n\n![x](pic.png)'.encode('utf-8'), 'text/markdown'),
                'assets': ('images.zip', buffer.getvalue(), 'application/zip'),
            },
            data={'ai_mode': 'none'},
        )
        assert resp.status_code == 200
        assert 'data:image/png;base64,' in resp.json()['html']
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)
