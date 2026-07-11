"""다이어그램 스튜디오(svc03) 검증.

- Mermaid 소스 생성(규칙 기반 폴백)과 유형별 시작 문법.
- 금지 지시어(click/javascript:/<script>/<iframe>/%%{init) 및 유형 불일치 거부.
- 잘못된 diagram_type 은 라우트에서 422.
- AI 보조를 켜도 활성 연결이 없으면 폴백 + 경고. 활성 연결(모킹)은 llm_used 경로.
- 산출물(diagram.mmd/spec/manifest)은 job 소유자에게만 열린다(상위 라우터 로그인).

JobStore 는 tmp 루트로 주입해 실제 저장소를 오염시키지 않는다.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.modules.auth.models import User
from app.modules.office_tools.api import diagrams as diagrams_api
from app.modules.office_tools.api.jobs import get_office_job_store
from app.modules.office_tools.core.job_store import OfficeJobStore
from app.modules.office_tools.schemas import DiagramGenerateRequest
from app.modules.office_tools.security import validate_mermaid
from app.modules.office_tools.services.diagram_service import (
    build_fallback_spec,
    generate_diagram,
)


def _admin_id(app) -> int:
    with app.state.db.session() as session:
        return session.execute(select(User).where(User.username == 'admin')).scalar_one().id


# --- 서버 검증: validate_mermaid -------------------------------------------------

@pytest.mark.parametrize(
    'source',
    [
        'flowchart TD\n    A --> B\n    click A "http://x"',
        'flowchart TD\n    A["javascript:alert(1)"] --> B',
        'flowchart TD\n    <script>alert(1)</script>',
        'flowchart TD\n    <iframe src="x"></iframe>',
        '%%{init: {"theme":"dark"}}%%\nflowchart TD\n    A --> B',
    ],
)
def test_validate_mermaid_rejects_forbidden(source: str) -> None:
    with pytest.raises(ValueError):
        validate_mermaid(source, 'flowchart')


def test_validate_mermaid_rejects_type_mismatch() -> None:
    # sequence 소스를 flowchart 로 요청 → 거부.
    with pytest.raises(ValueError):
        validate_mermaid('sequenceDiagram\n    A->>B: hi', 'flowchart')


def test_validate_mermaid_passes_matching_type() -> None:
    source, warnings = validate_mermaid('flowchart TD\n    A --> B', 'flowchart')
    assert source.startswith('flowchart TD')
    assert warnings == []


# --- 규칙 기반 폴백 ---------------------------------------------------------------

def test_fallback_flowchart_from_arrows() -> None:
    spec = build_fallback_spec('수집 -> 정제 -> 발행', 'flowchart')
    assert spec.mermaid.startswith('flowchart TD')
    assert 'N1' in spec.mermaid and 'N2' in spec.mermaid


def test_fallback_sequence_and_state() -> None:
    seq = build_fallback_spec('사용자 -> 서버: 요청\n서버 -> DB: 조회', 'sequence')
    assert seq.mermaid.startswith('sequenceDiagram')
    st = build_fallback_spec('로그인\n조회\n종료', 'state')
    assert st.mermaid.startswith('stateDiagram-v2')


def test_fallback_gantt_requires_valid_rows() -> None:
    with pytest.raises(ValueError):
        build_fallback_spec('설계와 개발을 한다', 'gantt')
    ok = build_fallback_spec('설계 | 2026-07-01 | 5d\n개발 | 2026-07-06 | 10d', 'gantt')
    assert ok.mermaid.startswith('gantt')


# --- generate_diagram 서비스(직접 호출, 소유권/폴백 경고) --------------------------

def test_generate_diagram_without_client_warns(app, tmp_path: Path) -> None:
    store = OfficeJobStore(tmp_path / 'office_jobs')
    request = DiagramGenerateRequest(description='A -> B -> C', diagram_type='flowchart', ai_assist=True)
    record = generate_diagram(store=store, owner_id=_admin_id(app), request=request, client=None, app_version='9.9.9')
    assert record['status'] == 'completed'
    assert record['mermaid'].startswith('flowchart TD')
    assert any('활성 LLM 연결이 없어' in w for w in record['warnings'])
    filenames = {a['filename'] for a in record['artifacts']}
    assert {'diagram.mmd', 'diagram_spec.json', 'manifest.json'} <= filenames


class _FakeClient:
    def __init__(self, content: str) -> None:
        self._content = content

    def chat(self, messages, temperature: float = 0.2, max_tokens: int = 1200) -> str:  # noqa: ARG002
        return self._content


def test_generate_diagram_uses_llm_when_available(app, tmp_path: Path) -> None:
    store = OfficeJobStore(tmp_path / 'office_jobs')
    fake = _FakeClient('{"title":"흐름","mermaid":"flowchart LR\\n    A --> B"}')
    request = DiagramGenerateRequest(description='설명', diagram_type='flowchart', ai_assist=True)
    record = generate_diagram(store=store, owner_id=_admin_id(app), request=request, client=fake, app_version='9.9.9')
    assert record['mermaid'].startswith('flowchart LR')
    assert record['warnings'] == []


def test_generate_diagram_falls_back_when_llm_returns_forbidden(app, tmp_path: Path) -> None:
    store = OfficeJobStore(tmp_path / 'office_jobs')
    fake = _FakeClient('{"title":"x","mermaid":"flowchart TD\\n    click A"}')
    request = DiagramGenerateRequest(description='A -> B', diagram_type='flowchart', ai_assist=True)
    record = generate_diagram(store=store, owner_id=_admin_id(app), request=request, client=fake, app_version='9.9.9')
    # 금지 지시어 → 폴백 규칙 기반 + 경고. 최종 소스에는 click 이 없어야 한다.
    assert 'click' not in record['mermaid']
    assert any('규칙 기반' in w for w in record['warnings'])


# --- 라우트(HTTP) ----------------------------------------------------------------

def test_generate_requires_login(client: TestClient) -> None:
    resp = client.post('/api/v1/office-tools/diagrams/generate', json={'description': 'A -> B'})
    assert resp.status_code == 401


def test_generate_route_returns_mermaid(app, csrf_client: TestClient, tmp_path: Path) -> None:
    store = OfficeJobStore(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        resp = csrf_client.post(
            '/api/v1/office-tools/diagrams/generate',
            json={'description': '수집 -> 정제 -> 발행', 'diagram_type': 'flowchart', 'ai_assist': False},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body['mermaid'].startswith('flowchart TD')
        assert body['diagram_type'] == 'flowchart'
        assert body['preview_url'].endswith('/diagram.mmd')
        # 소유자는 산출물을 내려받는다.
        art = csrf_client.get(f"/api/v1/office-tools/jobs/{body['job_id']}/artifacts/diagram.mmd")
        assert art.status_code == 200
        assert art.text.startswith('flowchart TD')
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)


def test_generate_route_rejects_invalid_type(csrf_client: TestClient) -> None:
    resp = csrf_client.post(
        '/api/v1/office-tools/diagrams/generate',
        json={'description': 'A -> B', 'diagram_type': 'mindmap'},
    )
    assert resp.status_code == 422


def test_generate_route_rejects_bad_gantt(app, csrf_client: TestClient, tmp_path: Path) -> None:
    store = OfficeJobStore(tmp_path / 'office_jobs')
    app.dependency_overrides[get_office_job_store] = lambda: store
    try:
        resp = csrf_client.post(
            '/api/v1/office-tools/diagrams/generate',
            json={'description': '유효행 없음', 'diagram_type': 'gantt', 'ai_assist': False},
        )
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.pop(get_office_job_store, None)
