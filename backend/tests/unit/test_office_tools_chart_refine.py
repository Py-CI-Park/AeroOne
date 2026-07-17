"""차트 스튜디오(svc02) 리파인(``previous_spec_json``) 검증.

- 규칙 기반 리파인: 유형/방향/정렬/상위 N/누적/무인식 경고.
- API 통합: previous_spec_json 재생성 시 이전 설정 유지 + 명령 반영, 잘못된 previous_spec
  (없는 열/비 JSON) 422, manual+previous 동시 제출 시 manual 승 + 경고, LLM 무설정 폴백.

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
from app.modules.office_tools.services.chart import generate_chart, load_dataframe
from app.modules.office_tools.services.chart.refine import (
    llm_refine_chart_spec,
    rule_refine_chart_spec,
)
from app.modules.office_tools.services.chart.schemas import ChartSpec

_CSV = '지역,매출\n서울,120\n부산,80\n서울,30\n대구,50\n'.encode('utf-8')


def _admin_id(app) -> int:
    with app.state.db.session() as session:
        return session.execute(select(User).where(User.username == 'admin')).scalar_one().id


def _base_spec() -> ChartSpec:
    return ChartSpec(
        type='bar',
        title='지역별 매출',
        x='지역',
        y=['매출'],
        aggregation='sum',
        sort='none',
        limit=30,
        orientation='vertical',
        stacked=False,
    )


# --- rule_refine_chart_spec (순수 함수) --------------------------------------------


def test_rule_refine_changes_chart_type() -> None:
    spec, warnings = rule_refine_chart_spec(_base_spec(), '선 그래프로 바꿔줘')

    assert spec.type == 'line'
    assert warnings == []


def test_rule_refine_changes_orientation() -> None:
    spec, warnings = rule_refine_chart_spec(_base_spec(), '가로 막대로 보여줘')

    assert spec.orientation == 'horizontal'
    assert warnings == []


def test_rule_refine_changes_sort_value_desc() -> None:
    spec, warnings = rule_refine_chart_spec(_base_spec(), '값 내림차순으로 큰 순 정렬해줘')

    assert spec.sort == 'value_desc'
    assert warnings == []


def test_rule_refine_changes_sort_none() -> None:
    refined_once, _ = rule_refine_chart_spec(_base_spec(), '값 내림 정렬')
    spec, warnings = rule_refine_chart_spec(refined_once, '정렬 없애')

    assert spec.sort == 'none'
    assert warnings == []


def test_rule_refine_changes_limit_top_n() -> None:
    spec, warnings = rule_refine_chart_spec(_base_spec(), '상위 5개만 보여줘')

    assert spec.limit == 5
    assert warnings == []


def test_rule_refine_clamps_limit_to_upper_bound() -> None:
    spec, warnings = rule_refine_chart_spec(_base_spec(), '상위 500개만 보여줘')

    assert spec.limit == 100
    assert warnings == []


def test_rule_refine_toggles_stacked_on_and_off() -> None:
    stacked_on, warnings_on = rule_refine_chart_spec(_base_spec(), '누적으로 쌓아줘')
    assert stacked_on.stacked is True
    assert warnings_on == []

    stacked_off, warnings_off = rule_refine_chart_spec(stacked_on, '누적 해제해줘')
    assert stacked_off.stacked is False
    assert warnings_off == []

    stacked_off_pull, warnings_pull = rule_refine_chart_spec(stacked_on, '누적 풀어줘')
    assert stacked_off_pull.stacked is False
    assert warnings_pull == []


def test_rule_refine_updates_title() -> None:
    spec, warnings = rule_refine_chart_spec(_base_spec(), '제목을 2026년 상반기 매출로 바꿔줘')

    assert spec.title == '2026년 상반기 매출'
    assert warnings == []


def test_rule_refine_keeps_previous_spec_and_warns_when_no_change_recognized() -> None:
    previous = _base_spec()
    spec, warnings = rule_refine_chart_spec(previous, '오늘 날씨 어때')

    assert spec.model_dump() == previous.model_dump()
    assert any('적용할 수 있는 차트 변경을 찾지 못했습니다' in w for w in warnings)

def test_rule_refine_does_not_false_positive_on_bare_syllables() -> None:
    # '우선'의 '선', '이름은 유지'의 '이름' 같은 부분 문자열이 유형/정렬을 뒤집으면 안 된다.
    spec, warnings = rule_refine_chart_spec(_base_spec(), '상위 5개 우선으로 보여줘')

    assert spec.type == 'bar'
    assert spec.limit == 5
    assert warnings == []

    kept, _ = rule_refine_chart_spec(_base_spec(), '파이로 바꾸고 이름은 유지해줘')
    assert kept.type == 'pie'
    assert kept.sort == _base_spec().sort

    # '온라인(으로)'의 '라인'/'라인으로' 부분 문자열이 유형을 뒤집으면 안 된다.
    online, online_warnings = rule_refine_chart_spec(_base_spec(), '온라인 채널만 상위 3개')
    assert online.type == 'bar'
    assert online.limit == 3
    assert online_warnings == []

    online_josa, _ = rule_refine_chart_spec(_base_spec(), '온라인으로 팔린 채널 상위 3개')
    assert online_josa.type == 'bar'



def test_rule_refine_does_not_mutate_previous_spec_reference() -> None:
    previous = _base_spec()
    spec, _ = rule_refine_chart_spec(previous, '선 그래프로 바꿔줘')

    assert previous.type == 'bar'
    assert spec.type == 'line'
    assert spec is not previous


# --- llm_refine_chart_spec ---------------------------------------------------------


class _FakeClient:
    model = 'fake-model'

    def __init__(self, content: str) -> None:
        self._content = content

    def chat(self, messages, temperature: float = 0.2, max_tokens: int = 1200) -> str:  # noqa: ARG002
        return self._content


def test_llm_refine_chart_spec_parses_and_validates() -> None:
    frame = load_dataframe('sales.csv', _CSV, max_rows=1000)
    fake = _FakeClient('{"type":"line","title":"추이","x":"지역","y":["매출"],"aggregation":"sum"}')

    spec, meta = llm_refine_chart_spec(frame, _base_spec(), '추이로 바꿔줘', fake)

    assert spec.type == 'line'
    assert meta == {'model': 'fake-model'}


def test_llm_refine_chart_spec_rejects_unknown_column() -> None:
    frame = load_dataframe('sales.csv', _CSV, max_rows=1000)
    fake = _FakeClient('{"type":"bar","title":"x","x":"없는열","y":["매출"]}')

    with pytest.raises(ValueError):
        llm_refine_chart_spec(frame, _base_spec(), '바꿔줘', fake)


# --- generate_chart 서비스(직접 호출) — refine 우선순위/폴백 -----------------------


def test_generate_chart_refines_previous_spec_without_llm(app, tmp_path: Path) -> None:
    store = OfficeJobStore(tmp_path / 'office_jobs')
    previous = _base_spec()
    record = generate_chart(
        store=store,
        owner_id=_admin_id(app),
        filename='sales.csv',
        data=_CSV,
        prompt='선 그래프로 바꿔주고 가로로 보여줘',
        ai_assist=False,
        requested_type=None,
        manual_spec_json='',
        previous_spec_json=previous.model_dump_json(),
        client=None,
        app_version='9.9.9',
        max_upload_bytes=10_000_000,
        max_data_rows=100_000,
    )

    assert record['status'] == 'completed'
    assert record['chart_spec']['type'] == 'line'
    assert record['chart_spec']['orientation'] == 'horizontal'
    # 직전 스펙의 x/y 설정은 유지된다.
    assert record['chart_spec']['x'] == '지역'
    assert record['chart_spec']['y'] == ['매출']


def test_generate_chart_refine_falls_back_to_rule_when_llm_fails(app, tmp_path: Path) -> None:
    store = OfficeJobStore(tmp_path / 'office_jobs')
    previous = _base_spec()

    class _FailingClient:
        model = 'fake-model'

        def chat(self, messages, temperature: float = 0.2, max_tokens: int = 1200) -> str:  # noqa: ARG002
            return 'not json at all'

    record = generate_chart(
        store=store,
        owner_id=_admin_id(app),
        filename='sales.csv',
        data=_CSV,
        prompt='선 그래프로 바꿔줘',
        ai_assist=True,
        requested_type=None,
        manual_spec_json='',
        previous_spec_json=previous.model_dump_json(),
        client=_FailingClient(),
        app_version='9.9.9',
        max_upload_bytes=10_000_000,
        max_data_rows=100_000,
    )

    assert record['status'] == 'completed'
    assert record['llm_used'] is False
    assert record['chart_spec']['type'] == 'line'
    assert any('LLM 차트 리파인 실패로 규칙 기반 리파인을 사용했습니다' in w for w in record['warnings'])


def test_generate_chart_manual_wins_over_previous_spec_with_warning(app, tmp_path: Path) -> None:
    store = OfficeJobStore(tmp_path / 'office_jobs')
    previous = _base_spec()
    manual = {'type': 'pie', 'title': '수동 스펙', 'x': '지역', 'y': ['매출']}

    record = generate_chart(
        store=store,
        owner_id=_admin_id(app),
        filename='sales.csv',
        data=_CSV,
        prompt='선 그래프로 바꿔줘',
        ai_assist=False,
        requested_type=None,
        manual_spec_json=json.dumps(manual),
        previous_spec_json=previous.model_dump_json(),
        client=None,
        app_version='9.9.9',
        max_upload_bytes=10_000_000,
        max_data_rows=100_000,
    )

    assert record['chart_spec']['type'] == 'pie'
    assert any('수동 스펙과 직전 스펙이 함께 전달되어' in w for w in record['warnings'])


def test_generate_chart_rejects_previous_spec_with_unknown_column(app, tmp_path: Path) -> None:
    store = OfficeJobStore(tmp_path / 'office_jobs')
    bad_previous = json.dumps({'type': 'bar', 'title': 'x', 'x': '없는열', 'y': ['매출']})

    with pytest.raises(ValueError):
        generate_chart(
            store=store,
            owner_id=_admin_id(app),
            filename='sales.csv',
            data=_CSV,
            prompt='선 그래프로 바꿔줘',
            ai_assist=False,
            requested_type=None,
            manual_spec_json='',
            previous_spec_json=bad_previous,
            client=None,
            app_version='9.9.9',
            max_upload_bytes=10_000_000,
            max_data_rows=100_000,
        )


def test_generate_chart_rejects_previous_spec_with_invalid_json(app, tmp_path: Path) -> None:
    store = OfficeJobStore(tmp_path / 'office_jobs')

    with pytest.raises(ValueError):
        generate_chart(
            store=store,
            owner_id=_admin_id(app),
            filename='sales.csv',
            data=_CSV,
            prompt='선 그래프로 바꿔줘',
            ai_assist=False,
            requested_type=None,
            manual_spec_json='',
            previous_spec_json='{not-json',
            client=None,
            app_version='9.9.9',
            max_upload_bytes=10_000_000,
            max_data_rows=100_000,
        )


# --- API 라우트 통합 ----------------------------------------------------------------


def test_generate_route_refines_previous_spec_and_keeps_unmentioned_fields(
    app, csrf_client: TestClient, tmp_path: Path
) -> None:
    store = OfficeJobStore(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        first = csrf_client.post(
            '/api/v1/office-tools/charts/generate',
            files={'data_file': ('sales.csv', _CSV, 'text/csv')},
            data={'prompt': '지역별 매출', 'ai_assist': 'false', 'chart_type': 'bar'},
        )
        assert first.status_code == 200
        previous_spec_json = json.dumps(first.json()['chart_spec'])

        second = csrf_client.post(
            '/api/v1/office-tools/charts/generate',
            files={'data_file': ('sales.csv', _CSV, 'text/csv')},
            data={
                'prompt': '가로 막대로 보여줘',
                'ai_assist': 'false',
                'previous_spec_json': previous_spec_json,
            },
        )
        assert second.status_code == 200
        body = second.json()
        assert body['chart_spec']['type'] == 'bar'
        assert body['chart_spec']['orientation'] == 'horizontal'
        # x/y 는 previous_spec 에서 유지된다.
        assert body['chart_spec']['x'] == first.json()['chart_spec']['x']
        assert body['chart_spec']['y'] == first.json()['chart_spec']['y']
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)


def test_generate_route_rejects_previous_spec_with_unknown_column(
    app, csrf_client: TestClient, tmp_path: Path
) -> None:
    store = OfficeJobStore(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        resp = csrf_client.post(
            '/api/v1/office-tools/charts/generate',
            files={'data_file': ('sales.csv', _CSV, 'text/csv')},
            data={
                'prompt': '바꿔줘',
                'ai_assist': 'false',
                'previous_spec_json': json.dumps({'type': 'bar', 'title': 'x', 'x': '없는열', 'y': ['매출']}),
            },
        )
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)


def test_generate_route_rejects_non_json_previous_spec(
    app, csrf_client: TestClient, tmp_path: Path
) -> None:
    store = OfficeJobStore(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        resp = csrf_client.post(
            '/api/v1/office-tools/charts/generate',
            files={'data_file': ('sales.csv', _CSV, 'text/csv')},
            data={
                'prompt': '바꿔줘',
                'ai_assist': 'false',
                'previous_spec_json': '{not-json',
            },
        )
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)


def test_generate_route_manual_spec_wins_over_previous_spec(
    app, csrf_client: TestClient, tmp_path: Path
) -> None:
    store = OfficeJobStore(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        previous = _base_spec()
        manual = {'type': 'pie', 'title': '수동 스펙', 'x': '지역', 'y': ['매출']}
        resp = csrf_client.post(
            '/api/v1/office-tools/charts/generate',
            files={'data_file': ('sales.csv', _CSV, 'text/csv')},
            data={
                'prompt': '선 그래프로 바꿔줘',
                'ai_assist': 'false',
                'manual_spec_json': json.dumps(manual),
                'previous_spec_json': previous.model_dump_json(),
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body['chart_spec']['type'] == 'pie'
        assert any('수동 스펙과 직전 스펙이 함께 전달되어' in w for w in body['warnings'])
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)


def test_generate_route_previous_spec_without_llm_config_falls_back_to_rule_refine(
    app, csrf_client: TestClient, tmp_path: Path
) -> None:
    """LLM 미설정 환경에서도 previous_spec_json + prompt 리파인은 규칙 기반으로 동작한다."""

    store = OfficeJobStore(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        previous = _base_spec()
        resp = csrf_client.post(
            '/api/v1/office-tools/charts/generate',
            files={'data_file': ('sales.csv', _CSV, 'text/csv')},
            data={
                'prompt': '누적으로 쌓아줘',
                'ai_assist': 'true',
                'previous_spec_json': previous.model_dump_json(),
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body['llm_used'] is False
        assert body['chart_spec']['stacked'] is True
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)
