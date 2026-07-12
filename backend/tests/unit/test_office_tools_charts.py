"""차트 스튜디오(svc02) 검증.

- 데이터 로드/프로필(행/열/컬럼) 정확성과 인코딩·확장자 처리.
- 규칙 기반/LLM 스펙 제안과 pandas 집계 정확성, ECharts option 직렬화.
- generate 가 chart_data.csv/chart_spec.json/echarts_option.json/manifest.json 을 등록.
- 라우트: 미로그인 401, 미지원 확장자·빈 데이터·잘못된 수동 스펙 422, 소유자 산출물 다운로드.

JobStore 는 tmp 루트로 주입해 실제 저장소를 오염시키지 않는다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.modules.auth.models import User
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
