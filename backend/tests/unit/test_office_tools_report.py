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
import stat
import struct
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.modules.auth.models import User
from app.modules.office_tools.api import reports
from app.modules.office_tools.api.jobs import get_office_job_store
from app.modules.office_tools.core.job_store import OfficeJobStore
from app.modules.office_tools.limits import require_utf8_filename_within_limit
from app.modules.office_tools.upload_limits import OfficeMultipartLimits
from app.modules.office_tools.services.report import (
    embed_markdown_images,
    enhance_markdown,
    generate_report,
    markdown_to_body,
)
from app.modules.office_tools.services.report import assets as report_assets
from app.modules.office_tools.services.report.assets import (
    UploadSizeLimitExceeded,
    read_bounded_bytes,
    unpack_asset_zip,
)

# 1x1 투명 PNG(테스트용 최소 이미지).
_PNG_BYTES = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
)


class _RecordingStream(io.BytesIO):
    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.read_sizes: list[int] = []

    def read(self, size: int = -1) -> bytes:
        self.read_sizes.append(size)
        return super().read(size)

class _FailingSeekStream:
    def __init__(
        self,
        error_type: type[OSError] | type[RuntimeError],
    ) -> None:
        self._error_type = error_type

    def seek(self, offset: int, whence: int = 0) -> int:
        raise self._error_type('stream is unavailable')

class _MisleadingUpload:
    def __init__(self, filename: str, data: bytes) -> None:
        self.filename = filename
        self.size = 0
        self.file = _RecordingStream(data)


def test_read_bounded_bytes_allows_exact_limit_with_bounded_reads() -> None:
    stream = _RecordingStream(b'abcd')

    assert read_bounded_bytes(stream, max_bytes=4) == b'abcd'
    assert stream.read_sizes
    assert all(0 < size <= 5 for size in stream.read_sizes)


def test_read_bounded_bytes_rejects_over_limit_without_unbounded_read() -> None:
    stream = _RecordingStream(b'abcde')

    with pytest.raises(UploadSizeLimitExceeded):
        read_bounded_bytes(stream, max_bytes=4)

    assert stream.read_sizes
    assert all(0 < size <= 5 for size in stream.read_sizes)


def test_collect_assets_rejects_misleading_upload_size() -> None:
    upload = _MisleadingUpload('image.png', b'abcde')

    with pytest.raises(UploadSizeLimitExceeded):
        reports._collect_assets([upload], max_upload_bytes=4, max_total_bytes=4)

    assert upload.file.read_sizes
    assert all(0 < size <= 5 for size in upload.file.read_sizes)


def test_unpack_asset_zip_rejects_compression_bomb() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('bomb.svg', b'x' * 4096)

    with pytest.raises(ValueError, match='압축률'):
        unpack_asset_zip(
            buffer.getvalue(),
            max_member_bytes=8192,
            max_total_bytes=8192,
            max_compression_ratio=10,
        )


def test_unpack_asset_zip_rejects_unsafe_path_and_symlink() -> None:
    path_buffer = io.BytesIO()
    with zipfile.ZipFile(path_buffer, 'w') as archive:
        archive.writestr('../image.png', b'x')
    with pytest.raises(ValueError, match='안전하지 않은 경로'):
        unpack_asset_zip(path_buffer.getvalue())

    symlink_buffer = io.BytesIO()
    info = zipfile.ZipInfo('image-link.png')
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(symlink_buffer, 'w') as archive:
        archive.writestr(info, b'')
    with pytest.raises(ValueError, match='심볼릭 링크'):
        unpack_asset_zip(symlink_buffer.getvalue())

def test_unpack_asset_zip_rejects_central_directory_amplification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr('image.png', _PNG_BYTES)

    def _zipfile_must_not_be_created(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError('central-directory preflight must run before ZipFile creation')

    monkeypatch.setattr(report_assets.zipfile, 'ZipFile', _zipfile_must_not_be_created)
    with pytest.raises(ValueError, match='중앙 디렉터리'):
        unpack_asset_zip(buffer.getvalue(), max_central_directory_bytes=1)

def test_unpack_asset_zip_rejects_huge_zip64_record_offset() -> None:
    payload = struct.pack(
        '<4sIQI',
        b'PK\x06\x07',
        0,
        0xFFFFFFFFFFFFFFFF,
        1,
    ) + struct.pack(
        '<4sHHHHIIH',
        b'PK\x05\x06',
        0,
        0,
        0xFFFF,
        0xFFFF,
        0xFFFFFFFF,
        0xFFFFFFFF,
        0,
    )

    with pytest.raises(ValueError, match='ZIP64'):
        unpack_asset_zip(payload)


def test_unpack_asset_zip_rejects_oversized_bytes_before_bytesio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _bytesio_must_not_be_created(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError('oversized bytes must be rejected before BytesIO construction')

    monkeypatch.setattr(report_assets, 'BytesIO', _bytesio_must_not_be_created)

    with pytest.raises(UploadSizeLimitExceeded, match='ZIP 압축 업로드 총 용량'):
        unpack_asset_zip(b'abcde', max_compressed_bytes=4)


@pytest.mark.parametrize('error_type', (OSError, RuntimeError))
def test_unpack_asset_zip_preserves_operational_stream_errors(
    error_type: type[OSError] | type[RuntimeError],
) -> None:
    with pytest.raises(error_type, match='stream is unavailable'):
        unpack_asset_zip(_FailingSeekStream(error_type))


def test_asset_filename_utf8_limit_is_shared_by_registry_and_preflight() -> None:
    filename = '한.png'
    filename_bytes = 7
    require_utf8_filename_within_limit(
        filename,
        filename_bytes,
        limit_message='shared filename limit',
    )
    with pytest.raises(ValueError, match='shared filename limit'):
        require_utf8_filename_within_limit(
            filename,
            filename_bytes - 1,
            limit_message='shared filename limit',
        )

    registry = report_assets.AssetNameRegistry(1, filename_bytes)
    registry.reserve([filename])
    with pytest.raises(ValueError, match='자산 파일명 바이트 상한'):
        report_assets.AssetNameRegistry(1, filename_bytes - 1).reserve([filename])

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr(filename, _PNG_BYTES)

    assert unpack_asset_zip(buffer.getvalue(), max_filename_bytes=filename_bytes) == {
        filename: _PNG_BYTES
    }
    with pytest.raises(ValueError, match='자산 파일명 바이트 상한'):
        unpack_asset_zip(buffer.getvalue(), max_filename_bytes=filename_bytes - 1)

def test_unpack_asset_zip_rejects_double_encoded_traversal() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr('%252e%252e%252fimage.png', _PNG_BYTES)

    with pytest.raises(ValueError, match='안전하지 않은 경로'):
        unpack_asset_zip(buffer.getvalue())
    nul_buffer = io.BytesIO()
    with zipfile.ZipFile(nul_buffer, 'w') as archive:
        archive.writestr('null.png', _PNG_BYTES)
    nul_payload = nul_buffer.getvalue().replace(b'null.png', b'nul\x00.png')

    with pytest.raises(ValueError, match='안전하지 않은 경로'):
        unpack_asset_zip(nul_payload)


def test_asset_names_keep_literal_percent_encoding_and_reject_encoded_path_controls() -> None:
    assert report_assets.canonical_asset_name('literal%2Epng') == 'literal%2Epng'

    for unsafe_name in (
        '%25252e%25252e%25252fimage.png',
        '.%252e%252fimage.png',
        'C%253a%255ctemp.png',
        'folder%25252fimage.png',
        'image%252500.png',
    ):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr(unsafe_name, _PNG_BYTES)
        with pytest.raises(ValueError, match='안전하지 않은 경로'):
            unpack_asset_zip(buffer.getvalue())


def test_embed_markdown_images_decodes_once_and_rejects_remaining_encoded_escape() -> None:
    embedded, warnings, count = embed_markdown_images(
        '![그림](images%2Fpic.png)',
        {'images/pic.png': _PNG_BYTES},
    )

    assert count == 1
    assert warnings == []
    assert 'data:image/png;base64,' in embedded

    unsafe_markdown = '![그림](%252e%252e%252fpic.png)'
    embedded, warnings, count = embed_markdown_images(unsafe_markdown, {'pic.png': _PNG_BYTES})
    assert embedded == unsafe_markdown
    assert count == 0
    assert any('안전하지 않은' in warning for warning in warnings)


@pytest.mark.parametrize(
    'reference',
    (
        '%FF.png',
        '%C3%28.png',
        '%E2%82.png',
    ),
    ids=('invalid_lead_byte', 'invalid_continuation', 'truncated_sequence'),
)
def test_embed_markdown_images_rejects_malformed_utf8_percent_references(reference: str) -> None:
    markdown = f'![그림]({reference})'

    embedded, warnings, count = embed_markdown_images(markdown, {'image.png': _PNG_BYTES})

    assert embedded == markdown
    assert count == 0
    assert warnings == [f'안전하지 않은 이미지 자산 경로입니다: {reference}']


def test_embed_markdown_images_caches_repeated_image_and_enforces_budgets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    original_encode = report_assets.base64.b64encode

    def _recording_encode(data: bytes) -> bytes:
        nonlocal calls
        calls += 1
        return original_encode(data)

    monkeypatch.setattr(report_assets.base64, 'b64encode', _recording_encode)
    markdown = '![첫](pic.png)\n![둘](pic.png)'
    embedded, warnings, count = embed_markdown_images(markdown, {'pic.png': _PNG_BYTES})

    assert warnings == []
    assert count == 2
    assert embedded.count('data:image/png;base64,') == 2
    assert calls == 1

    with pytest.raises(ValueError, match='이미지 참조 수'):
        embed_markdown_images(markdown, {'pic.png': _PNG_BYTES}, max_image_references=1)
    calls_before_output_budget = calls
    with pytest.raises(ValueError, match='최종 용량'):
        embed_markdown_images('![x](pic.png)', {'pic.png': _PNG_BYTES}, max_embedded_bytes=20)
    assert calls == calls_before_output_budget
@pytest.mark.parametrize(
    ('max_embedded_bytes', 'raises_limit'),
    (
        (6, False),
        (5, True),
    ),
    ids=('exact_utf8_bytes', 'one_over_utf8_bytes'),
)
def test_embed_markdown_images_enforces_initial_utf8_byte_budget(
    max_embedded_bytes: int,
    raises_limit: bool,
) -> None:
    markdown = '한글'

    if raises_limit:
        with pytest.raises(ValueError, match='최종 용량'):
            embed_markdown_images(markdown, {}, max_embedded_bytes=max_embedded_bytes)
    else:
        assert embed_markdown_images(markdown, {}, max_embedded_bytes=max_embedded_bytes) == (
            markdown,
            [],
            0,
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


def test_generate_route_rejects_oversized_markdown_with_413(
    csrf_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(reports, 'MAX_REPORT_UPLOAD_BYTES', 4)

    resp = csrf_client.post(
        '/api/v1/office-tools/reports/generate',
        files={'markdown_file': ('report.md', b'# 123', 'text/markdown')},
        data={'ai_mode': 'none'},
    )

    assert resp.status_code == 413


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

def test_generate_route_applies_compressed_budget_across_zip_parts_with_413(
    csrf_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr('pic.png', _PNG_BYTES)
    payload = buffer.getvalue()
    monkeypatch.setattr(reports, 'MAX_REPORT_ASSET_COMPRESSED_BYTES', len(payload) * 2 - 1)
    monkeypatch.setattr(reports, 'MAX_REPORT_UPLOAD_BYTES', len(payload) + 1)
    monkeypatch.setattr(reports, 'MAX_REPORT_ASSET_TOTAL_BYTES', len(_PNG_BYTES) * 2 + 1)
    monkeypatch.setattr(reports, 'MAX_REPORT_ASSET_UPLOADS', 2)

    resp = csrf_client.post(
        '/api/v1/office-tools/reports/generate',
        files=[
            ('markdown_file', ('report.md', b'# report', 'text/markdown')),
            ('assets', ('first.zip', payload, 'application/zip')),
            ('assets', ('second.zip', payload, 'application/zip')),
        ],
        data={'ai_mode': 'none'},
    )

    assert resp.status_code == 413
    assert resp.json()['detail'] == '보고서 자산 압축 업로드 총 용량 상한을 초과했습니다'


def test_generate_route_rejects_duplicate_canonical_key_across_zip_parts_with_422(
    csrf_client: TestClient,
) -> None:
    first_buffer = io.BytesIO()
    with zipfile.ZipFile(first_buffer, 'w') as archive:
        archive.writestr('pic.png', _PNG_BYTES)
    second_buffer = io.BytesIO()
    with zipfile.ZipFile(second_buffer, 'w') as archive:
        archive.writestr('./pic.png', _PNG_BYTES)

    resp = csrf_client.post(
        '/api/v1/office-tools/reports/generate',
        files=[
            ('markdown_file', ('report.md', b'# report', 'text/markdown')),
            ('assets', ('first.zip', first_buffer.getvalue(), 'application/zip')),
            ('assets', ('second.zip', second_buffer.getvalue(), 'application/zip')),
        ],
        data={'ai_mode': 'none'},
    )

    assert resp.status_code == 422
    assert '중복된 자산 canonical key' in resp.json()['detail']


@pytest.mark.parametrize(
    'content_type',
    (
        b'application/x-www-form-urlencoded',
        b'application/octet-stream',
    ),
    ids=('urlencoded', 'raw'),
)
def test_report_ingress_stops_chunked_non_multipart_overflow_before_starlette_or_downstream(
    app,
    office_ingress_harness,
    monkeypatch: pytest.MonkeyPatch,
    content_type: bytes,
) -> None:
    from starlette.requests import Request

    path = '/api/v1/office-tools/reports/generate'
    form_calls: list[object] = []

    async def _form_must_not_run(*args, **kwargs):  # noqa: ANN002, ANN003
        form_calls.append((args, kwargs))
        raise AssertionError('non-multipart overflow must not reach Starlette form parsing')

    monkeypatch.setattr(Request, 'form', _form_must_not_run)
    office_ingress_harness.set_limits(
        app,
        {path: OfficeMultipartLimits(max_total_bytes=4, max_file_bytes=4, max_files=1)},
    )
    sentinel = {'type': 'http.request', 'body': b'sentinel-must-remain-unread', 'more_body': False}
    receive_messages = [
        {'type': 'http.request', 'body': b'ai_', 'more_body': True},
        {'type': 'http.request', 'body': b'mode=none', 'more_body': True},
        sentinel,
    ]

    status, response = office_ingress_harness.request(
        app,
        path=path,
        headers=[
            (b'content-type', content_type),
            (b'transfer-encoding', b'chunked'),
        ],
        receive_messages=receive_messages,
    )

    assert status == 413
    assert response == {'detail': '업로드 전체 크기가 허용 상한을 초과했습니다'}
    assert receive_messages == [sentinel]
    assert form_calls == []


@pytest.mark.parametrize(
    'content_type',
    (
        b'application/x-www-form-urlencoded',
        b'application/octet-stream',
    ),
    ids=('urlencoded', 'raw'),
)
def test_report_ingress_accepts_exact_total_then_truthfully_rejects_non_multipart_media_type(
    app,
    office_ingress_harness,
    monkeypatch: pytest.MonkeyPatch,
    content_type: bytes,
) -> None:
    from starlette.requests import Request

    path = '/api/v1/office-tools/reports/generate'
    form_calls: list[object] = []

    async def _form_must_not_run(*args, **kwargs):  # noqa: ANN002, ANN003
        form_calls.append((args, kwargs))
        raise AssertionError('non-multipart media rejection must precede Starlette form parsing')

    monkeypatch.setattr(Request, 'form', _form_must_not_run)
    office_ingress_harness.set_limits(
        app,
        {path: OfficeMultipartLimits(max_total_bytes=4, max_file_bytes=4, max_files=1)},
    )
    receive_messages = [{'type': 'http.request', 'body': b'abcd', 'more_body': False}]

    status, response = office_ingress_harness.request(
        app,
        path=path,
        headers=[(b'content-type', content_type)],
        receive_messages=receive_messages,
    )

    assert status == 415
    assert response == {'detail': 'multipart/form-data 요청만 지원합니다'}
    assert receive_messages == []
    assert form_calls == []


@pytest.mark.parametrize(
    'content_disposition',
    (
        b"Content-Disposition: form-data; name=\"markdown_file\"; filename*=UTF-8''r%C3%A9port%2Emd",
        b"Content-Disposition: form-data; name=\"markdown_file\"; "
        b"filename*0*=UTF-8''r%C3%A9port%2E; filename*1*=md",
    ),
    ids=('percent_escaped_filename_star', 'rfc2231_filename_continuation'),
)
@pytest.mark.parametrize(
    'content_type',
    (
        b"multipart/form-data; boundary*=us-ascii''report-ingress-boundary",
        b"multipart/form-data; boundary*0*=us-ascii''report-ingress-; boundary*1*=boundary",
    ),
    ids=('boundary_star', 'boundary_continuation'),
)
@pytest.mark.parametrize(
    ('limit_case', 'expected_status', 'expected_detail'),
    (
        ('exact', 401, 'Authentication required'),
        ('file_one_over', 413, '업로드 파일이 허용 크기를 초과했습니다'),
        ('total_one_over', 413, '업로드 전체 크기가 허용 상한을 초과했습니다'),
    ),
)
def test_report_ingress_honors_rfc2231_boundary_forms_at_exact_and_one_over_limits(
    app,
    office_ingress_harness,
    content_disposition: bytes,
    content_type: bytes,
    limit_case: str,
    expected_status: int,
    expected_detail: str,
) -> None:
    path = '/api/v1/office-tools/reports/generate'
    data = b'# bounded report\n'
    body = office_ingress_harness.multipart_body(
        [(content_disposition, data)],
        boundary=b'report-ingress-boundary',
        content_type=b'application/octet-stream',
    )
    office_ingress_harness.set_limits(
        app,
        {
            path: OfficeMultipartLimits(
                max_total_bytes=len(body) - int(limit_case == 'total_one_over'),
                max_file_bytes=len(data) - int(limit_case == 'file_one_over'),
                max_files=1,
            )
        },
    )

    status, response = office_ingress_harness.request(
        app,
        path=path,
        headers=[(b'content-type', content_type)],
        receive_messages=[{'type': 'http.request', 'body': body, 'more_body': False}],
    )

    assert status == expected_status
    assert response == {'detail': expected_detail}


@pytest.mark.parametrize(
    ('file_count', 'max_files', 'expected_status', 'expected_detail'),
    (
        (2, 2, 401, 'Authentication required'),
        (3, 2, 413, '업로드 파일 수가 허용 상한을 초과했습니다'),
    ),
    ids=('exact', 'one_over'),
)
def test_report_ingress_enforces_exact_and_one_over_file_count(
    app,
    office_ingress_harness,
    file_count: int,
    max_files: int,
    expected_status: int,
    expected_detail: str,
) -> None:
    path = '/api/v1/office-tools/reports/generate'
    data = b'# report\n'
    parts = [
        (
            f'Content-Disposition: form-data; name="assets"; filename="asset-{index}.zip"'.encode(
                'ascii'
            ),
            data,
        )
        for index in range(file_count)
    ]
    body = office_ingress_harness.multipart_body(
        parts,
        boundary=b'report-ingress-boundary',
        content_type=b'application/octet-stream',
    )
    office_ingress_harness.set_limits(
        app,
        {
            path: OfficeMultipartLimits(
                max_total_bytes=len(body),
                max_file_bytes=len(data),
                max_files=max_files,
            )
        },
    )

    status, response = office_ingress_harness.request(
        app,
        path=path,
        headers=[
            (b'content-type', b'multipart/form-data; boundary=report-ingress-boundary')
        ],
        receive_messages=[{'type': 'http.request', 'body': body, 'more_body': False}],
    )

    assert status == expected_status
    assert response == {'detail': expected_detail}
