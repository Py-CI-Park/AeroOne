"""차트 스튜디오(svc02) 검증.

- 데이터 로드/프로필(행/열/컬럼) 정확성과 인코딩·확장자 처리.
- 규칙 기반/LLM 스펙 제안과 pandas 집계 정확성, ECharts option 직렬화.
- generate 가 chart_data.csv/chart_spec.json/echarts_option.json/manifest.json 을 등록.
- 라우트: 미로그인 401, 미지원 확장자·빈 데이터·잘못된 수동 스펙 422, 소유자 산출물 다운로드.

JobStore 는 tmp 루트로 주입해 실제 저장소를 오염시키지 않는다.
"""

from __future__ import annotations

import json
import re
import zipfile
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.modules.auth.models import User
from app.modules.office_tools.api import charts
from app.modules.office_tools import upload_limits
from app.modules.office_tools.limits import UploadSizeLimitExceeded
from app.modules.office_tools.api.jobs import get_office_job_store
from app.modules.office_tools.core.job_store import OfficeJobStore
from app.modules.office_tools.services.chart import (
    auto_chart_spec,
    dataframe_profile,
    echarts_option,
    generate_chart,
    load_dataframe,
    prepare_chart,
)
from app.modules.office_tools.services.chart.schemas import ChartSpec
from app.modules.office_tools.services.chart import data_loader
from app.modules.office_tools.upload_limits import OfficeMultipartLimits

_CSV = '지역,매출\n서울,120\n부산,80\n서울,30\n대구,50\n'.encode('utf-8')


def _admin_id(app) -> int:
    with app.state.db.session() as session:
        return session.execute(select(User).where(User.username == 'admin')).scalar_one().id


# --- 데이터 로더 / 프로필 ---------------------------------------------------------

def test_load_dataframe_profiles_rows_and_columns() -> None:
    frame = load_dataframe('sales.csv', _CSV, max_rows=1000)
    profile = dataframe_profile(frame)
    assert profile['row_count'] == 4
    assert profile['column_count'] == 2
    names = {c['name'] for c in profile['columns']}
    assert names == {'지역', '매출'}
    assert next(c for c in profile['columns'] if c['name'] == '매출')['numeric'] is True


def test_load_dataframe_rejects_unsupported_and_empty() -> None:
    with pytest.raises(ValueError):
        load_dataframe('data.txt', b'x', max_rows=1000)
    with pytest.raises(ValueError):
        load_dataframe('empty.csv', b'a,b\n', max_rows=1000)


def test_load_dataframe_enforces_row_limit() -> None:
    big = ('x\n' + '\n'.join(str(i) for i in range(20))).encode('utf-8')
    with pytest.raises(ValueError):
        load_dataframe('rows.csv', big, max_rows=5)


def test_load_dataframe_reads_json_array() -> None:
    payload = json.dumps([{'a': 1, 'b': 2}, {'a': 3, 'b': 4}]).encode('utf-8')
    frame = load_dataframe('data.json', payload, max_rows=1000)
    assert list(frame.columns) == ['a', 'b']
    assert len(frame) == 2


def test_load_dataframe_reads_json_data_wrapper() -> None:
    payload = json.dumps({'data': [{'a': 1}, {'a': 2}]}).encode('utf-8')
    frame = load_dataframe('data.json', payload, max_rows=1000)

    assert list(frame['a']) == [1, 2]


def test_load_dataframe_rejects_sparse_json_union_width_before_dataframe_materialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _dataframe_must_not_materialize(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError('union-width rejection must precede DataFrame materialization')

    monkeypatch.setattr(data_loader, 'MAX_CHART_DATA_COLUMNS', 1)
    monkeypatch.setattr(data_loader, '_dataframe_from_rows', _dataframe_must_not_materialize)

    message = '데이터 열 수이(가) 상한 1을(를) 초과했습니다'
    with pytest.raises(ValueError, match=re.escape(message)):
        load_dataframe('sparse.json', b'[{"a":1},{"b":2}]', max_rows=10)


def test_load_dataframe_accepts_sparse_json_at_union_width_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(data_loader, 'MAX_CHART_DATA_COLUMNS', 2)

    frame = load_dataframe('sparse.json', b'[{"a":1},{"b":2}]', max_rows=10)

    assert frame.shape == (2, 2)
    assert list(frame.columns) == ['a', 'b']


def test_load_dataframe_rejects_json_rows_before_decoding_one_over_record_or_materializing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_decoder = json.JSONDecoder
    decoded_records = 0

    class _CountingDecoder:
        def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
            self._decoder = original_decoder(*args, **kwargs)

        def raw_decode(self, token: str, index: int = 0):
            nonlocal decoded_records
            decoded_records += 1
            return self._decoder.raw_decode(token, index)

    def _full_document_load_must_not_run(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError('bounded JSON parser must not call json.loads')

    def _dataframe_must_not_materialize(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError('row-limit rejection must precede DataFrame materialization')

    monkeypatch.setattr(data_loader.json, 'JSONDecoder', _CountingDecoder)
    monkeypatch.setattr(data_loader.json, 'loads', _full_document_load_must_not_run)
    monkeypatch.setattr(data_loader, '_dataframe_from_rows', _dataframe_must_not_materialize)

    with pytest.raises(ValueError, match='데이터 행 수'):
        load_dataframe('rows.json', b'[{"a":1},{"a":2}]', max_rows=1)

    assert decoded_records <= 1


def test_load_dataframe_rejects_exact_duplicate_json_key_before_dataframe_materialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _dataframe_must_not_materialize(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError('duplicate-key rejection must precede DataFrame materialization')

    monkeypatch.setattr(data_loader, '_dataframe_from_rows', _dataframe_must_not_materialize)

    message = 'JSON 객체에 중복 키가 있습니다'
    with pytest.raises(ValueError, match=re.escape(message)):
        load_dataframe('duplicate-key.json', b'[{"a":1,"a":2}]', max_rows=10)


@pytest.mark.parametrize('constant', (b'NaN', b'Infinity', b'-Infinity', b'1e10000'))
def test_load_dataframe_rejects_nonstandard_json_constants_before_dataframe_materialization(
    monkeypatch: pytest.MonkeyPatch,
    constant: bytes,
) -> None:
    def _dataframe_must_not_materialize(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError('nonstandard constant rejection must precede DataFrame materialization')

    monkeypatch.setattr(data_loader, '_dataframe_from_rows', _dataframe_must_not_materialize)

    message = 'JSON 비표준 숫자 상수는 허용되지 않습니다'
    with pytest.raises(ValueError, match=re.escape(message)):
        load_dataframe('nonstandard-constant.json', b'[{"a":' + constant + b'}]', max_rows=10)


def test_load_dataframe_globally_reserves_generated_column_names() -> None:
    frame = load_dataframe('generated-columns.csv', b'a,a,a_2\n1,2,3\n', max_rows=10)

    assert list(frame.columns) == ['a', 'a_2', 'a_2_2']


def test_load_dataframe_rejects_json_nesting_before_record_decode_or_materialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _json_decoder_must_not_run(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError('nested JSON must be rejected before JSONDecoder materialization')

    def _dataframe_must_not_materialize(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError('nested JSON must be rejected before DataFrame materialization')

    monkeypatch.setattr(data_loader.json, 'JSONDecoder', _json_decoder_must_not_run)
    monkeypatch.setattr(data_loader, '_dataframe_from_rows', _dataframe_must_not_materialize)

    with pytest.raises(ValueError, match='JSON 셀은 문자열, 숫자, 불리언 또는 null'):
        load_dataframe('nested.json', b'[{"a":{"b":{"c":1}}}]', max_rows=10)


@pytest.mark.parametrize(
    ('limit_name', 'limit', 'payload', 'message'),
    (
        (
            'MAX_CHART_DATA_COLUMNS',
            2,
            b'a,b,c\n1,2,3\n',
            '데이터 열 수이(가) 상한 2을(를) 초과했습니다',
        ),
        (
            'MAX_CHART_DATA_CELL_CHARS',
            4,
            b'a\n12345\n',
            'CSV 셀 문자 수이(가) 상한 4을(를) 초과했습니다',
        ),
        (
            'MAX_CHART_DECODED_CHARS',
            10,
            b'a\n123456789\n',
            'CSV 해독 문자 수이(가) 상한 10을(를) 초과했습니다',
        ),
    ),
)
def test_load_dataframe_rejects_csv_preallocation_limits_before_dataframe_materialization(
    monkeypatch: pytest.MonkeyPatch,
    limit_name: str,
    limit: int,
    payload: bytes,
    message: str,
) -> None:
    def _dataframe_must_not_materialize(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError('CSV limit rejection must precede DataFrame materialization')

    monkeypatch.setattr(data_loader, limit_name, limit)
    monkeypatch.setattr(data_loader, '_dataframe_from_rows', _dataframe_must_not_materialize)

    with pytest.raises(ValueError, match=re.escape(message)):
        load_dataframe('bounded.csv', payload, max_rows=10)


@pytest.mark.parametrize(
    ('limit_name', 'limit', 'payload', 'message'),
    (
        (
            'MAX_CHART_DATA_COLUMNS',
            1,
            b'[{"a":1,"b":2}]',
            '데이터 열 수',
        ),
        (
            'MAX_CHART_DATA_CELL_CHARS',
            4,
            b'[{"a":"12345"}]',
            'JSON 문자열 문자 수',
        ),
    ),
)
def test_load_dataframe_rejects_json_limits_before_dataframe_materialization(
    monkeypatch: pytest.MonkeyPatch,
    limit_name: str,
    limit: int,
    payload: bytes,
    message: str,
) -> None:
    def _dataframe_must_not_materialize(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError('JSON limit rejection must precede DataFrame materialization')

    monkeypatch.setattr(data_loader, limit_name, limit)
    monkeypatch.setattr(data_loader, '_dataframe_from_rows', _dataframe_must_not_materialize)

    with pytest.raises(ValueError, match=re.escape(message)):
        load_dataframe('bounded.json', payload, max_rows=10)

def test_load_dataframe_rejects_many_duplicate_json_keys_before_decode_or_materialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    limit = 128
    payload = b'[{' + b','.join(b'"a":1' for _ in range(limit + 1)) + b'}]'

    def _json_decoder_must_not_run(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError('duplicate-key rejection must precede JSONDecoder materialization')

    def _dataframe_must_not_materialize(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError('duplicate-key rejection must precede DataFrame materialization')

    monkeypatch.setattr(data_loader, 'MAX_CHART_DATA_COLUMNS', limit)
    monkeypatch.setattr(data_loader.json, 'JSONDecoder', _json_decoder_must_not_run)
    monkeypatch.setattr(data_loader, '_dataframe_from_rows', _dataframe_must_not_materialize)

    message = f'데이터 열 수이(가) 상한 {limit:,}을(를) 초과했습니다'
    with pytest.raises(ValueError, match=re.escape(message)):
        load_dataframe('duplicate-keys.json', payload, max_rows=10)


@pytest.mark.parametrize(
    'payload',
    (
        b'[{"a":{"nested":1}}]',
        b'[{"a":[1]}]',
    ),
    ids=('object_cell', 'array_cell'),
)
def test_load_dataframe_rejects_nested_json_cell_containers_before_dataframe_materialization(
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes,
) -> None:
    def _dataframe_must_not_materialize(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError('nested-cell rejection must precede DataFrame materialization')

    def _json_decoder_must_not_run(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError('nested-cell rejection must precede JSONDecoder materialization')

    monkeypatch.setattr(data_loader.json, 'JSONDecoder', _json_decoder_must_not_run)

    monkeypatch.setattr(data_loader, '_dataframe_from_rows', _dataframe_must_not_materialize)

    message = 'JSON 셀은 문자열, 숫자, 불리언 또는 null 이어야 합니다'
    with pytest.raises(ValueError, match=re.escape(message)):
        load_dataframe('nested-cell.json', payload, max_rows=10)


_OOXML_SPREADSHEET_NAMESPACE = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
_OOXML_CONTENT_TYPES_NAMESPACE = 'http://schemas.openxmlformats.org/package/2006/content-types'


def _valid_xlsx_bytes(openpyxl, rows: list[tuple[object, ...]] | None = None) -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = 'Data'
    for row in rows or [('label', 'value'), ('one', 1), ('two', 2)]:
        sheet.append(row)
    payload = BytesIO()
    workbook.save(payload)
    workbook.close()
    return payload.getvalue()


def _rewrite_valid_xlsx(
    payload: bytes,
    *,
    replacements: dict[str, bytes] | None = None,
    additions: list[tuple[str, bytes]] | None = None,
    compression_overrides: dict[str, int] | None = None,
) -> bytes:
    rewritten = BytesIO()
    with zipfile.ZipFile(BytesIO(payload)) as source, zipfile.ZipFile(rewritten, 'w') as destination:
        for info in source.infolist():
            destination.writestr(
                info,
                (replacements or {}).get(info.filename, source.read(info)),
                compress_type=(compression_overrides or {}).get(info.filename, info.compress_type),
            )
        for name, data in additions or []:
            destination.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
    return rewritten.getvalue()


def _xlsx_member_infos(payload: bytes) -> list[zipfile.ZipInfo]:
    with zipfile.ZipFile(BytesIO(payload)) as archive:
        return archive.infolist()


def _xlsx_member_bytes(payload: bytes, name: str) -> bytes:
    with zipfile.ZipFile(BytesIO(payload)) as archive:
        return archive.read(name)


def _count_ooxml_elements(xml: bytes, *names: str) -> int:
    root = ElementTree.fromstring(xml)
    return sum(element.tag.rsplit('}', 1)[-1] in names for element in root.iter())


def _load_workbook_must_not_run(*args, **kwargs):  # noqa: ANN002, ANN003
    raise AssertionError('XLSX preflight rejection must precede openpyxl.load_workbook')


def test_load_dataframe_rejects_xlsx_compressed_size_before_bytesio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _bytesio_must_not_run(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError('compressed-size rejection must precede BytesIO materialization')

    limit = 3
    monkeypatch.setattr(data_loader, 'MAX_CHART_XLSX_COMPRESSED_BYTES', limit)
    monkeypatch.setattr(data_loader, 'BytesIO', _bytesio_must_not_run)

    message = 'ZIP 압축 업로드 총 용량 상한을 초과했습니다'
    with pytest.raises(UploadSizeLimitExceeded, match=re.escape(message)):
        load_dataframe('oversized.xlsx', b'1234', max_rows=10)


def test_load_dataframe_rejects_valid_xlsx_entry_limit_before_zipfile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    openpyxl = pytest.importorskip('openpyxl')
    base = _valid_xlsx_bytes(openpyxl)
    baseline_entries = len(_xlsx_member_infos(base))
    payload = _rewrite_valid_xlsx(
        base,
        additions=[('custom/one-extra.xml', b'<extra xmlns="urn:test"/>')],
    )

    def _zipfile_must_not_be_created(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError('central-directory entry limit must precede ZipFile creation')

    monkeypatch.setattr(data_loader, 'MAX_CHART_XLSX_ENTRIES', baseline_entries)
    monkeypatch.setattr(data_loader.zipfile, 'ZipFile', _zipfile_must_not_be_created)

    message = f'ZIP 안 파일 수가 {baseline_entries}개를 초과했습니다'
    with pytest.raises(ValueError, match=re.escape(message)):
        load_dataframe('entries.xlsx', payload, max_rows=10)


def test_load_dataframe_rejects_valid_xlsx_unsafe_name_before_zipfile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    openpyxl = pytest.importorskip('openpyxl')
    payload = _rewrite_valid_xlsx(
        _valid_xlsx_bytes(openpyxl),
        additions=[('../unsafe.xml', b'<extra xmlns="urn:test"/>')],
    )

    def _zipfile_must_not_be_created(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError('unsafe-name preflight must precede ZipFile creation')

    monkeypatch.setattr(data_loader.zipfile, 'ZipFile', _zipfile_must_not_be_created)
    message = 'XLSX 에 안전하지 않은 ZIP 멤버 이름이 있습니다'
    with pytest.raises(ValueError, match=re.escape(message)):
        load_dataframe('unsafe-name.xlsx', payload, max_rows=10)


def test_load_dataframe_rejects_valid_xlsx_expanded_size_before_load_workbook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    openpyxl = pytest.importorskip('openpyxl')
    base = _valid_xlsx_bytes(openpyxl)
    baseline_expanded_bytes = sum(info.file_size for info in _xlsx_member_infos(base))
    payload = _rewrite_valid_xlsx(
        base,
        additions=[('custom/one-extra.bin', b'x' * 64)],
    )
    limit = baseline_expanded_bytes + 63

    monkeypatch.setattr(data_loader, 'MAX_CHART_XLSX_EXPANDED_BYTES', limit)
    monkeypatch.setattr(openpyxl, 'load_workbook', _load_workbook_must_not_run)

    message = f'XLSX ZIP 총 확장 바이트이(가) 상한 {limit:,}을(를) 초과했습니다'
    with pytest.raises(ValueError, match=re.escape(message)):
        load_dataframe('expanded.xlsx', payload, max_rows=10)


def test_load_dataframe_rejects_valid_xlsx_compression_ratio_before_load_workbook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    openpyxl = pytest.importorskip('openpyxl')
    base = _valid_xlsx_bytes(openpyxl)
    baseline_ratio_limit = max(
        (info.file_size + info.compress_size - 1) // info.compress_size
        for info in _xlsx_member_infos(base)
        if info.file_size
    )
    payload = _rewrite_valid_xlsx(
        base,
        additions=[('custom/highly-compressed.bin', b'x' * (256 * 1024))],
    )

    monkeypatch.setattr(data_loader, 'MAX_CHART_XLSX_COMPRESSION_RATIO', baseline_ratio_limit)
    monkeypatch.setattr(openpyxl, 'load_workbook', _load_workbook_must_not_run)

    message = (
        f'XLSX ZIP 압축률이(가) 상한 {baseline_ratio_limit:,}을(를) 초과했습니다'
    )
    with pytest.raises(ValueError, match=re.escape(message)):
        load_dataframe('compressed.xlsx', payload, max_rows=10)


def test_load_dataframe_rejects_unsupported_xlsx_compression_before_load_workbook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    openpyxl = pytest.importorskip('openpyxl')
    payload = _rewrite_valid_xlsx(
        _valid_xlsx_bytes(openpyxl),
        compression_overrides={'xl/styles.xml': zipfile.ZIP_BZIP2},
    )
    monkeypatch.setattr(openpyxl, 'load_workbook', _load_workbook_must_not_run)

    message = '지원하지 않는 ZIP 압축 방식입니다'
    with pytest.raises(ValueError, match=re.escape(message)):
        load_dataframe('unsupported-compression.xlsx', payload, max_rows=10)


@pytest.mark.parametrize(
    'kind',
    ('shared_strings', 'styles', 'content_types'),
)
def test_load_dataframe_rejects_valid_xlsx_metadata_before_load_workbook(
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
) -> None:
    openpyxl = pytest.importorskip('openpyxl')
    base = _valid_xlsx_bytes(openpyxl)

    if kind == 'shared_strings':
        member_name = 'xl/sharedStrings.xml'
        member_xml = (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            b'count="2" uniqueCount="2"><si><t>one</t></si><si><t>two</t></si></sst>'
        )
        payload = _rewrite_valid_xlsx(base, additions=[(member_name, member_xml)])
        limit_name = 'MAX_CHART_XLSX_SHARED_STRINGS'
        limit = 1
        message = 'XLSX 공유 문자열 수이(가) 상한 1을(를) 초과했습니다'
    elif kind == 'styles':
        member_name = 'xl/styles.xml'
        original = _xlsx_member_bytes(base, member_name)
        root = ElementTree.fromstring(original)
        cell_xfs = next(
            element
            for element in root
            if element.tag.rsplit('}', 1)[-1] == 'cellXfs'
        )
        ElementTree.SubElement(cell_xfs, f'{{{_OOXML_SPREADSHEET_NAMESPACE}}}xf')
        payload = _rewrite_valid_xlsx(
            base,
            replacements={
                member_name: ElementTree.tostring(root, encoding='utf-8', xml_declaration=True),
            },
        )
        limit_name = 'MAX_CHART_XLSX_STYLE_RECORDS'
        limit = _count_ooxml_elements(
            original,
            *data_loader._XLSX_STYLE_ALLOCATION_TAGS,
        )
        message = f'XLSX 스타일 수이(가) 상한 {limit:,}을(를) 초과했습니다'
    else:
        member_name = '[Content_Types].xml'
        original = _xlsx_member_bytes(base, member_name)
        root = ElementTree.fromstring(original)
        ElementTree.SubElement(
            root,
            f'{{{_OOXML_CONTENT_TYPES_NAMESPACE}}}Override',
            {
                'PartName': '/custom/metadata.xml',
                'ContentType': 'application/xml',
            },
        )
        payload = _rewrite_valid_xlsx(
            base,
            replacements={
                member_name: ElementTree.tostring(root, encoding='utf-8', xml_declaration=True),
            },
        )
        limit_name = 'MAX_CHART_XLSX_CONTENT_TYPES'
        limit = _count_ooxml_elements(original, 'Default', 'Override')
        message = f'XLSX 콘텐츠 형식 수이(가) 상한 {limit:,}을(를) 초과했습니다'

    monkeypatch.setattr(data_loader, limit_name, limit)
    if kind == 'styles':
        baseline = load_dataframe('metadata-baseline.xlsx', base, max_rows=10)
        assert baseline.shape == (2, 2)
    monkeypatch.setattr(openpyxl, 'load_workbook', _load_workbook_must_not_run)

    with pytest.raises(ValueError, match=re.escape(message)):
        load_dataframe('metadata.xlsx', payload, max_rows=10)


def test_load_dataframe_accepts_valid_xlsx_at_exact_metadata_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    openpyxl = pytest.importorskip('openpyxl')
    payload = _valid_xlsx_bytes(openpyxl)
    styles = _xlsx_member_bytes(payload, 'xl/styles.xml')
    content_types = _xlsx_member_bytes(payload, '[Content_Types].xml')

    monkeypatch.setattr(
        data_loader,
        'MAX_CHART_XLSX_STYLE_RECORDS',
        _count_ooxml_elements(
            styles,
            *data_loader._XLSX_STYLE_ALLOCATION_TAGS,
        ),
    )
    monkeypatch.setattr(
        data_loader,
        'MAX_CHART_XLSX_NUMBER_FORMATS',
        _count_ooxml_elements(styles, 'numFmt'),
    )
    monkeypatch.setattr(
        data_loader,
        'MAX_CHART_XLSX_CONTENT_TYPES',
        _count_ooxml_elements(content_types, 'Default', 'Override'),
    )

    frame = load_dataframe('exact-metadata.xlsx', payload, max_rows=2)

    assert frame.to_dict(orient='records') == [{'label': 'one', 'value': 1}, {'label': 'two', 'value': 2}]


def test_load_dataframe_rejects_xlsx_physical_rows_before_load_workbook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    openpyxl = pytest.importorskip('openpyxl')
    max_rows = 2
    payload = _valid_xlsx_bytes(
        openpyxl,
        rows=[('label', 'value'), ('one', 1), ('two', 2), ('three', 3), ('four', 4)],
    )
    monkeypatch.setattr(openpyxl, 'load_workbook', _load_workbook_must_not_run)

    with pytest.raises(ValueError, match='XLSX 워크시트 행 좌표'):
        load_dataframe('rows.xlsx', payload, max_rows=max_rows)


@pytest.mark.parametrize('payload_kind', ('f', 'v', 'is'))
def test_load_dataframe_rejects_duplicate_direct_xlsx_cell_payload_before_load_workbook(
    monkeypatch: pytest.MonkeyPatch,
    payload_kind: str,
) -> None:
    openpyxl = pytest.importorskip('openpyxl')
    base = _valid_xlsx_bytes(openpyxl)
    member_name = 'xl/worksheets/sheet1.xml'
    root = ElementTree.fromstring(_xlsx_member_bytes(base, member_name))
    cell = next(
        element
        for element in root.iter()
        if element.tag.rsplit('}', 1)[-1] == 'c'
    )
    payload_tag = f'{{{_OOXML_SPREADSHEET_NAMESPACE}}}{payload_kind}'
    cell.append(ElementTree.Element(payload_tag))
    cell.append(ElementTree.Element(payload_tag))
    payload = _rewrite_valid_xlsx(
        base,
        replacements={
            member_name: ElementTree.tostring(root, encoding='utf-8', xml_declaration=True),
        },
    )
    monkeypatch.setattr(openpyxl, 'load_workbook', _load_workbook_must_not_run)

    message = f'XLSX 셀 {payload_kind} 페이로드가 중복되었습니다'
    with pytest.raises(ValueError, match=re.escape(message)):
        load_dataframe('duplicate-cell-payload.xlsx', payload, max_rows=10)


def test_load_dataframe_rejects_repeated_xlsx_cell_before_load_workbook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    openpyxl = pytest.importorskip('openpyxl')
    base = _valid_xlsx_bytes(openpyxl)
    member_name = 'xl/worksheets/sheet1.xml'
    root = ElementTree.fromstring(_xlsx_member_bytes(base, member_name))
    sheet_data = next(
        element for element in root.iter() if element.tag.rsplit('}', 1)[-1] == 'sheetData'
    )
    first_row = next(
        element for element in sheet_data if element.tag.rsplit('}', 1)[-1] == 'row'
    )
    first_row.insert(
        1,
        ElementTree.Element(
            f'{{{_OOXML_SPREADSHEET_NAMESPACE}}}c',
            {'r': 'A1'},
        ),
    )
    payload = _rewrite_valid_xlsx(
        base,
        replacements={
            member_name: ElementTree.tostring(root, encoding='utf-8', xml_declaration=True),
        },
    )
    monkeypatch.setattr(openpyxl, 'load_workbook', _load_workbook_must_not_run)

    message = 'XLSX 워크시트 셀 좌표가 정렬되지 않았습니다'
    with pytest.raises(ValueError, match=re.escape(message)):
        load_dataframe('repeated-cell.xlsx', payload, max_rows=10)


def test_load_dataframe_rejects_duplicate_xlsx_relationship_id_before_load_workbook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    openpyxl = pytest.importorskip('openpyxl')
    base = _valid_xlsx_bytes(openpyxl)
    member_name = 'xl/_rels/workbook.xml.rels'
    root = ElementTree.fromstring(_xlsx_member_bytes(base, member_name))
    relationship = next(
        element for element in root if element.tag.rsplit('}', 1)[-1] == 'Relationship'
    )
    root.append(ElementTree.Element(relationship.tag, dict(relationship.attrib)))
    payload = _rewrite_valid_xlsx(
        base,
        replacements={
            member_name: ElementTree.tostring(root, encoding='utf-8', xml_declaration=True),
        },
    )
    monkeypatch.setattr(openpyxl, 'load_workbook', _load_workbook_must_not_run)

    message = 'XLSX 워크시트 관계 ID가 중복되었습니다'
    with pytest.raises(ValueError, match=re.escape(message)):
        load_dataframe('duplicate-relationship.xlsx', payload, max_rows=10)


def test_load_dataframe_rejects_ambiguous_xlsx_relationship_id_before_load_workbook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    openpyxl = pytest.importorskip('openpyxl')
    base = _valid_xlsx_bytes(openpyxl)
    member_name = 'xl/workbook.xml'
    root = ElementTree.fromstring(_xlsx_member_bytes(base, member_name))
    sheet = next(
        element for element in root.iter() if element.tag.rsplit('}', 1)[-1] == 'sheet'
    )
    sheet.set('id', 'ambiguous-id')
    payload = _rewrite_valid_xlsx(
        base,
        replacements={
            member_name: ElementTree.tostring(root, encoding='utf-8', xml_declaration=True),
        },
    )
    monkeypatch.setattr(openpyxl, 'load_workbook', _load_workbook_must_not_run)

    message = 'XLSX 워크시트 관계 ID가 모호합니다'
    with pytest.raises(ValueError, match=re.escape(message)):
        load_dataframe('ambiguous-relationship.xlsx', payload, max_rows=10)


def test_load_dataframe_rejects_repeated_xlsx_style_child_before_load_workbook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    openpyxl = pytest.importorskip('openpyxl')
    base = _valid_xlsx_bytes(openpyxl)
    member_name = 'xl/styles.xml'
    original = _xlsx_member_bytes(base, member_name)
    root = ElementTree.fromstring(original)
    fonts = next(
        element for element in root if element.tag.rsplit('}', 1)[-1] == 'fonts'
    )
    font = next(
        element for element in fonts if element.tag.rsplit('}', 1)[-1] == 'font'
    )
    fonts.append(ElementTree.Element(font.tag, dict(font.attrib)))
    payload = _rewrite_valid_xlsx(
        base,
        replacements={
            member_name: ElementTree.tostring(root, encoding='utf-8', xml_declaration=True),
        },
    )
    limit = _count_ooxml_elements(original, *data_loader._XLSX_STYLE_ALLOCATION_TAGS)
    monkeypatch.setattr(data_loader, 'MAX_CHART_XLSX_STYLE_RECORDS', limit)
    monkeypatch.setattr(openpyxl, 'load_workbook', _load_workbook_must_not_run)

    message = f'XLSX 스타일 수이(가) 상한 {limit:,}을(를) 초과했습니다'
    with pytest.raises(ValueError, match=re.escape(message)):
        load_dataframe('repeated-style.xlsx', payload, max_rows=10)


# --- 집계 정확성 -----------------------------------------------------------------

def test_prepare_chart_sum_aggregation_groups_by_x() -> None:
    frame = load_dataframe('sales.csv', _CSV, max_rows=1000)
    spec = ChartSpec(type='bar', title='지역별', x='지역', y=['매출'], aggregation='sum', sort='value_desc')
    prepared = prepare_chart(frame, spec)
    totals = dict(zip([str(c) for c in prepared.categories], prepared.series[0]['data']))
    # 서울 120 + 30 = 150, 부산 80, 대구 50 → value_desc 정렬로 서울이 선두.
    assert totals['서울'] == 150
    assert totals['부산'] == 80
    assert prepared.categories[0] == '서울'


def test_prepare_chart_count_aggregation() -> None:
    frame = load_dataframe('sales.csv', _CSV, max_rows=1000)
    spec = ChartSpec(type='bar', title='건수', x='지역', y=[], aggregation='count')
    prepared = prepare_chart(frame, spec)
    counts = dict(zip([str(c) for c in prepared.categories], prepared.series[0]['data']))
    assert counts['서울'] == 2
    assert counts['부산'] == 1


def test_echarts_option_shapes_bar_axes() -> None:
    frame = load_dataframe('sales.csv', _CSV, max_rows=1000)
    spec = auto_chart_spec(frame, prompt='지역별 매출 비교', requested_type='bar')
    option = echarts_option(spec, prepare_chart(frame, spec))
    assert option['series'][0]['type'] == 'bar'
    assert option['xAxis']['type'] == 'category'
    assert option['animation'] is False


def test_echarts_option_pie_uses_name_value_pairs() -> None:
    frame = load_dataframe('sales.csv', _CSV, max_rows=1000)
    spec = ChartSpec(type='pie', title='구성비', x='지역', y=['매출'], aggregation='sum')
    option = echarts_option(spec, prepare_chart(frame, spec))
    assert option['series'][0]['type'] == 'pie'
    assert all({'name', 'value'} <= set(item) for item in option['series'][0]['data'])


# --- 다계열(그룹/누적/다중 y) — '화려한 차트' ------------------------------------

_GROUP_CSV = '지역,채널,매출\n서울,온라인,10\n서울,오프라인,5\n부산,온라인,7\n부산,오프라인,3\n'.encode('utf-8')


def test_grouped_bar_produces_one_series_per_group_without_stack() -> None:
    frame = load_dataframe('g.csv', _GROUP_CSV, max_rows=1000)
    spec = ChartSpec(type='bar', title='그룹', x='지역', y=['매출'], group='채널', aggregation='sum', stacked=False)
    option = echarts_option(spec, prepare_chart(frame, spec))
    assert {s['name'] for s in option['series']} == {'온라인', '오프라인'}
    assert all('stack' not in s for s in option['series'])


def test_stacked_bar_sets_stack_on_every_series() -> None:
    frame = load_dataframe('s.csv', _GROUP_CSV, max_rows=1000)
    spec = ChartSpec(type='bar', title='누적', x='지역', y=['매출'], group='채널', aggregation='sum', stacked=True)
    option = echarts_option(spec, prepare_chart(frame, spec))
    assert len(option['series']) == 2
    assert all(s.get('stack') == 'total' for s in option['series'])


def test_multi_y_line_produces_multiple_series() -> None:
    csv = 'month,A,B,C\n2026-01,1,2,3\n2026-02,4,5,6\n'.encode('utf-8')
    frame = load_dataframe('m.csv', csv, max_rows=1000)
    spec = ChartSpec(type='line', title='다계열', x='month', y=['A', 'B', 'C'], aggregation='none', sort='x_asc')
    option = echarts_option(spec, prepare_chart(frame, spec))
    assert [s['name'] for s in option['series']] == ['A', 'B', 'C']
    assert all(s['type'] == 'line' for s in option['series'])


def test_single_series_stacked_does_not_set_stack() -> None:
    # 단일 계열에 stacked=True 여도 stack 을 붙이지 않는다(누적은 다계열에서만 의미).
    frame = load_dataframe('sales.csv', _CSV, max_rows=1000)
    spec = ChartSpec(type='bar', title='단일', x='지역', y=['매출'], aggregation='sum', stacked=True)
    option = echarts_option(spec, prepare_chart(frame, spec))
    assert all('stack' not in s for s in option['series'])


def test_stacked_area_makes_stacked_line_series_with_areastyle() -> None:
    csv = 'month,ch,v\n2026-01,A,10\n2026-01,B,5\n2026-02,A,12\n2026-02,B,6\n'.encode('utf-8')
    frame = load_dataframe('a.csv', csv, max_rows=1000)
    spec = ChartSpec(type='area', title='누적영역', x='month', y=['v'], group='ch', aggregation='sum', stacked=True, sort='x_asc')
    option = echarts_option(spec, prepare_chart(frame, spec))
    assert len(option['series']) == 2
    assert all(s['type'] == 'line' for s in option['series'])
    assert all('areaStyle' in s for s in option['series'])
    assert all(s.get('stack') == 'total' for s in option['series'])


# --- 스펙 검증 -------------------------------------------------------------------

def test_chart_spec_rejects_missing_column() -> None:
    frame = load_dataframe('sales.csv', _CSV, max_rows=1000)
    spec = ChartSpec(type='bar', title='x', x='없는열', y=['매출'])
    with pytest.raises(ValueError):
        spec.validate_columns([str(c) for c in frame.columns])


def test_auto_chart_spec_prefers_prompt_type() -> None:
    frame = load_dataframe('sales.csv', _CSV, max_rows=1000)
    spec = auto_chart_spec(frame, prompt='매출 분포 히스토그램', requested_type=None)
    assert spec.type == 'histogram'


# --- generate_chart 서비스(직접 호출) --------------------------------------------

def test_generate_chart_registers_artifacts(app, tmp_path: Path) -> None:
    store = OfficeJobStore(tmp_path / 'office_jobs')
    record = generate_chart(
        store=store,
        owner_id=_admin_id(app),
        filename='sales.csv',
        data=_CSV,
        prompt='지역별 매출',
        ai_assist=False,
        requested_type='bar',
        manual_spec_json='',
        client=None,
        app_version='9.9.9',
        max_upload_bytes=10_000_000,
        max_data_rows=100_000,
    )
    assert record['status'] == 'completed'
    assert record['llm_used'] is False
    assert record['echarts_option']['series'][0]['type'] == 'bar'
    filenames = {a['filename'] for a in record['artifacts']}
    assert {'chart_data.csv', 'chart_spec.json', 'echarts_option.json', 'manifest.json'} <= filenames


def test_generate_chart_ai_assist_without_client_warns(app, tmp_path: Path) -> None:
    store = OfficeJobStore(tmp_path / 'office_jobs')
    record = generate_chart(
        store=store,
        owner_id=_admin_id(app),
        filename='sales.csv',
        data=_CSV,
        prompt='지역별 매출',
        ai_assist=True,
        requested_type=None,
        manual_spec_json='',
        client=None,
        app_version='9.9.9',
        max_upload_bytes=10_000_000,
        max_data_rows=100_000,
    )
    assert any('활성 LLM 연결이 없어' in w for w in record['warnings'])


class _FakeClient:
    model = 'fake-model'

    def __init__(self, content: str) -> None:
        self._content = content

    def chat(self, messages, temperature: float = 0.2, max_tokens: int = 1200) -> str:  # noqa: ARG002
        return self._content


def test_generate_chart_uses_llm_spec_when_available(app, tmp_path: Path) -> None:
    store = OfficeJobStore(tmp_path / 'office_jobs')
    fake = _FakeClient('{"type":"line","title":"추이","x":"지역","y":["매출"],"aggregation":"sum"}')
    record = generate_chart(
        store=store,
        owner_id=_admin_id(app),
        filename='sales.csv',
        data=_CSV,
        prompt='추이',
        ai_assist=True,
        requested_type=None,
        manual_spec_json='',
        client=fake,
        app_version='9.9.9',
        max_upload_bytes=10_000_000,
        max_data_rows=100_000,
    )
    assert record['llm_used'] is True
    assert record['chart_spec']['type'] == 'line'


def test_generate_chart_manual_spec_validates_columns(app, tmp_path: Path) -> None:
    store = OfficeJobStore(tmp_path / 'office_jobs')
    with pytest.raises(ValueError):
        generate_chart(
            store=store,
            owner_id=_admin_id(app),
            filename='sales.csv',
            data=_CSV,
            prompt='',
            ai_assist=False,
            requested_type=None,
            manual_spec_json='{"type":"bar","title":"x","x":"없는열","y":["매출"]}',
            client=None,
            app_version='9.9.9',
            max_upload_bytes=10_000_000,
            max_data_rows=100_000,
        )


@pytest.mark.parametrize(
    'path',
    (
        '/api/v1/office-tools/charts/inspect',
        '/api/v1/office-tools/charts/generate',
    ),
)
@pytest.mark.parametrize(
    'content_type',
    (
        b'application/x-www-form-urlencoded',
        b'application/octet-stream',
    ),
    ids=('urlencoded', 'raw'),
)
def test_chart_ingress_stops_chunked_non_multipart_overflow_before_starlette_or_downstream(
    app,
    office_ingress_harness,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    content_type: bytes,
) -> None:
    from starlette.requests import Request

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
        {'type': 'http.request', 'body': b'data', 'more_body': True},
        {'type': 'http.request', 'body': b'=123', 'more_body': True},
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
def test_chart_ingress_accepts_exact_total_then_truthfully_rejects_non_multipart_media_type(
    app,
    office_ingress_harness,
    monkeypatch: pytest.MonkeyPatch,
    content_type: bytes,
) -> None:
    from starlette.requests import Request

    path = '/api/v1/office-tools/charts/inspect'
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


def test_chart_ingress_returns_json_413_before_starlette_stages_chunked_file(
    app,
    office_ingress_harness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = '/api/v1/office-tools/charts/inspect'
    body = office_ingress_harness.multipart_body(
        [
            (
                b'Content-Disposition: form-data; name="data_file"; filename="data.csv"',
                b'12345',
            )
        ],
        boundary=b'chart-ingress-boundary',
        content_type=b'text/csv',
    )
    office_ingress_harness.set_limits(
        app,
        {
            path: OfficeMultipartLimits(
                max_total_bytes=len(body),
                max_file_bytes=4,
                max_files=1,
            )
        },
    )

    from starlette import formparsers

    staged_files: list[object] = []

    def _unexpected_spooled_file(*args, **kwargs):  # noqa: ANN002, ANN003
        staged_files.append((args, kwargs))
        raise AssertionError('the multipart parser must not stage an over-limit file')

    replay_files: list[object] = []
    original_replay_file = upload_limits.SpooledTemporaryFile

    def _recording_replay_file(*args, **kwargs):  # noqa: ANN002, ANN003
        replay_file = original_replay_file(*args, **kwargs)
        replay_files.append(replay_file)
        return replay_file

    monkeypatch.setattr(upload_limits, 'SpooledTemporaryFile', _recording_replay_file)
    monkeypatch.setattr(formparsers, 'SpooledTemporaryFile', _unexpected_spooled_file)
    sentinel = {'type': 'http.request', 'body': b'sentinel-must-remain-unread', 'more_body': False}
    receive_messages = [
        {'type': 'http.request', 'body': body, 'more_body': True},
        sentinel,
    ]
    status, response = office_ingress_harness.request(
        app,
        path=path,
        headers=[
            (b'content-type', b'multipart/form-data; boundary=chart-ingress-boundary'),
        ],
        receive_messages=receive_messages,
    )

    assert status == 413
    assert response == {'detail': '업로드 파일이 허용 크기를 초과했습니다'}
    assert receive_messages == [sentinel]
    assert staged_files == []
    assert replay_files and all(getattr(replay_file, 'closed') for replay_file in replay_files)


def test_chart_ingress_does_not_count_large_ordinary_form_fields_as_files(
    app,
    office_ingress_harness,
) -> None:
    path = '/api/v1/office-tools/charts/inspect'
    body = office_ingress_harness.multipart_body(
        [(b'Content-Disposition: form-data; name="comment"', b'ordinary-field-is-larger-than-the-file-limit')],
        boundary=b'chart-ingress-boundary',
        content_type=b'text/csv',
    )
    office_ingress_harness.set_limits(
        app,
        {
            path: OfficeMultipartLimits(
                max_total_bytes=len(body),
                max_file_bytes=1,
                max_files=1,
            )
        },
    )

    status, _ = office_ingress_harness.request(
        app,
        path=path,
        headers=[(b'content-type', b'multipart/form-data; boundary=chart-ingress-boundary')],
        receive_messages=[{'type': 'http.request', 'body': body, 'more_body': False}],
    )

    assert status == 401


@pytest.mark.parametrize(
    'content_disposition',
    (
        b"Content-Disposition: form-data; name=\"data_file\"; filename*=UTF-8''d%C3%A1ta%2Ecsv",
        b"Content-Disposition: form-data; name=\"data_file\"; "
        b"filename*0*=UTF-8''d%C3%A1ta%2E; filename*1*=csv",
    ),
    ids=('percent_escaped_filename_star', 'rfc2231_filename_continuation'),
)
@pytest.mark.parametrize(
    'content_type',
    (
        b"multipart/form-data; boundary*=us-ascii''chart-ingress-boundary",
        b"multipart/form-data; boundary*0*=us-ascii''chart-ingress-; boundary*1*=boundary",
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
def test_chart_ingress_honors_rfc2231_boundary_forms_at_exact_and_one_over_limits(
    app,
    office_ingress_harness,
    content_disposition: bytes,
    content_type: bytes,
    limit_case: str,
    expected_status: int,
    expected_detail: str,
) -> None:
    path = '/api/v1/office-tools/charts/inspect'
    data = b'label,value\none,1\n'
    body = office_ingress_harness.multipart_body(
        [(content_disposition, data)],
        boundary=b'chart-ingress-boundary',
        content_type=b'text/csv',
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


def test_chart_ingress_accepts_exact_file_count_before_forwarding_to_the_real_app(
    app,
    office_ingress_harness,
) -> None:
    path = '/api/v1/office-tools/charts/inspect'
    file_data = b'a\n1\n'
    body = office_ingress_harness.multipart_body(
        [
            (b'Content-Disposition: form-data; name="data_file"; filename="one.csv"', file_data),
            (b'Content-Disposition: form-data; name="data_file"; filename="two.csv"', file_data),
        ],
        boundary=b'chart-ingress-boundary',
        content_type=b'text/csv',
    )
    office_ingress_harness.set_limits(
        app,
        {
            path: OfficeMultipartLimits(
                max_total_bytes=len(body),
                max_file_bytes=len(file_data),
                max_files=2,
            )
        },
    )

    status, _ = office_ingress_harness.request(
        app,
        path=path,
        headers=[(b'content-type', b'multipart/form-data; boundary=chart-ingress-boundary')],
        receive_messages=[{'type': 'http.request', 'body': body, 'more_body': False}],
    )

    assert status == 401


def test_chart_ingress_rejects_one_over_file_count_before_downstream_parsing(
    app,
    office_ingress_harness,
) -> None:
    path = '/api/v1/office-tools/charts/inspect'
    file_data = b'a\n1\n'
    body = office_ingress_harness.multipart_body(
        [
            (b'Content-Disposition: form-data; name="data_file"; filename="one.csv"', file_data),
            (b'Content-Disposition: form-data; name="data_file"; filename="two.csv"', file_data),
            (b'Content-Disposition: form-data; name="data_file"; filename="three.csv"', file_data),
        ],
        boundary=b'chart-ingress-boundary',
        content_type=b'text/csv',
    )
    office_ingress_harness.set_limits(
        app,
        {
            path: OfficeMultipartLimits(
                max_total_bytes=len(body),
                max_file_bytes=len(file_data),
                max_files=2,
            )
        },
    )

    status, response = office_ingress_harness.request(
        app,
        path=path,
        headers=[(b'content-type', b'multipart/form-data; boundary=chart-ingress-boundary')],
        receive_messages=[{'type': 'http.request', 'body': body, 'more_body': False}],
    )

    assert status == 413
    assert response == {'detail': '업로드 파일 수가 허용 상한을 초과했습니다'}
# --- 라우트(HTTP) ----------------------------------------------------------------

def test_inspect_requires_login(client: TestClient) -> None:
    resp = client.post(
        '/api/v1/office-tools/charts/inspect',
        files={'data_file': ('sales.csv', _CSV, 'text/csv')},
    )
    assert resp.status_code == 401


def test_inspect_route_returns_profile(csrf_client: TestClient) -> None:
    resp = csrf_client.post(
        '/api/v1/office-tools/charts/inspect',
        files={'data_file': ('sales.csv', _CSV, 'text/csv')},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body['row_count'] == 4
    assert body['column_count'] == 2


def test_inspect_route_rejects_bad_extension(csrf_client: TestClient) -> None:
    resp = csrf_client.post(
        '/api/v1/office-tools/charts/inspect',
        files={'data_file': ('data.txt', b'x', 'text/plain')},
    )
    assert resp.status_code == 422


def test_inspect_route_rejects_oversized_data_with_413(
    csrf_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(charts, 'MAX_CHART_UPLOAD_BYTES', 4)

    resp = csrf_client.post(
        '/api/v1/office-tools/charts/inspect',
        files={'data_file': ('sales.csv', b'a,b\n1,2\n', 'text/csv')},
    )

    assert resp.status_code == 413


def test_generate_route_returns_option_and_artifacts(app, csrf_client: TestClient, tmp_path: Path) -> None:
    store = OfficeJobStore(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        resp = csrf_client.post(
            '/api/v1/office-tools/charts/generate',
            files={'data_file': ('sales.csv', _CSV, 'text/csv')},
            data={'prompt': '지역별 매출', 'ai_assist': 'false', 'chart_type': 'bar'},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body['echarts_option']['series'][0]['type'] == 'bar'
        assert body['preview_url'].endswith('/echarts_option.json')
        # 소유자는 산출물을 내려받는다.
        art = csrf_client.get(f"/api/v1/office-tools/jobs/{body['job_id']}/artifacts/echarts_option.json")
        assert art.status_code == 200
        assert 'series' in art.json()
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)


def test_generate_route_rejects_empty_data(app, csrf_client: TestClient, tmp_path: Path) -> None:
    store = OfficeJobStore(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        resp = csrf_client.post(
            '/api/v1/office-tools/charts/generate',
            files={'data_file': ('empty.csv', b'a,b\n', 'text/csv')},
            data={'ai_assist': 'false'},
        )
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)
