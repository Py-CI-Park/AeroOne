"""다이어그램 스튜디오(svc03) 서비스 — 설명을 Mermaid 소스로 변환한다.

MVP ``tools/svc03_diagram_studio`` 의 ``generator.py`` + ``service.py`` 를 AeroOne 로
이식하되, 이번 빌드의 렌더링 결정(BUILD_CONTRACT §2.5)에 맞춰 다음을 바꾼다.

- 서버 ``cairosvg`` PNG export 제거 — 브라우저가 Mermaid→SVG/PNG 로 렌더한다.
  따라서 산출물은 ``diagram.mmd``(소스) + ``diagram_spec.json`` + ``manifest.json`` 뿐.
- ``preview.build_mermaid_preview``(벤더 mermaid.min.js) 미사용 — 프런트가 렌더한다.
- LLM 은 ``OpenAiCompatibleClient.chat`` 을 통해 Mermaid 를 제안하고, 활성 연결이
  없거나 실패하면 규칙 기반 ``build_fallback_spec`` 으로 폴백한다(경고 첨부).

모든 소스는 브라우저에 넘기기 전에 ``security.validate_mermaid`` 로 실행 지시어
(click/javascript:/<script>/<iframe>/%%{init)를 차단한다.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any

from app.modules.ai.openai_client import OpenAiCompatibleClient
from app.modules.office_tools.core.job_store import OfficeJobStore
from app.modules.office_tools.schemas import DiagramGenerateRequest, DiagramSpec
from app.modules.office_tools.security import validate_mermaid

_MAX_STEPS = 30
_LLM_SYSTEM_PROMPT = (
    '당신은 사내 업무 다이어그램 설계기다. 설명을 Mermaid 문법으로 구조화하고 JSON 객체 하나만 반환한다.\n'
    '허용 diagram_type과 시작 문법: flowchart(flowchart TD/LR), sequence(sequenceDiagram),'
    ' state(stateDiagram-v2), gantt(gantt).\n'
    '반드시 요청받은 유형만 사용한다. click, href, 외부 URL, init directive, HTML, JavaScript를 생성하지 않는다.\n'
    '설명에 없는 담당자, 수치, 날짜, 시스템을 임의로 추가하지 않는다. 불명확한 내용은 단순한 단계로 보존한다.\n'
    '스키마: {"title":"...","mermaid":"..."}. raw reasoning은 반환하지 않는다.'
)


def _label(text: str, limit: int = 90) -> str:
    """노드 라벨을 Mermaid 안전 문자로 정리한다(따옴표/대괄호/중괄호 제거)."""

    cleaned = re.sub(r'\s+', ' ', text.strip())[:limit]
    for src, dst in (('"', "'"), ('[', '('), (']', ')'), ('{', '('), ('}', ')')):
        cleaned = cleaned.replace(src, dst)
    return cleaned or '단계'


def _steps(description: str) -> list[str]:
    """설명을 결정적 규칙으로 단계 목록화한다(화살표 → 목록/줄 → 문장 순)."""

    arrow_parts = [p.strip() for p in re.split(r'\s*(?:--?>|→|⇒)\s*', description) if p.strip()]
    if len(arrow_parts) >= 2:
        return arrow_parts[:_MAX_STEPS]
    lines = [
        re.sub(r'^\s*(?:[-*•]|\d+[.)])\s*', '', line).strip()
        for line in description.splitlines()
        if line.strip()
    ]
    lines = [line for line in lines if line]
    if len(lines) >= 2:
        return lines[:_MAX_STEPS]
    sentences = [p.strip() for p in re.split(r'[.;。]\s*', description) if p.strip()]
    return sentences[:20] or [description.strip()]


def _flowchart(steps: list[str]) -> str:
    lines = ['flowchart TD']
    lines += [f'    N{i}["{_label(step)}"]' for i, step in enumerate(steps, start=1)]
    lines += [f'    N{i} --> N{i + 1}' for i in range(1, len(steps))]
    return '\n'.join(lines)


def _sequence(steps: list[str]) -> str:
    lines = ['sequenceDiagram', '    autonumber']
    parsed = 0
    for step in steps:
        match = re.match(r'\s*([^:>-]+)\s*(?:--?>|→)\s*([^:]+?)\s*:\s*(.+)', step)
        if match:
            sender, receiver, message = (_label(g) for g in match.groups())
            lines.append(f'    {sender}->>{receiver}: {message}')
            parsed += 1
    if not parsed:
        lines += ['    participant 사용자', '    participant AeroOne']
        for step in steps:
            lines.append(f'    사용자->>AeroOne: {_label(step)}')
            lines.append('    AeroOne-->>사용자: 처리 결과')
    return '\n'.join(lines)


def _state(steps: list[str]) -> str:
    lines = ['stateDiagram-v2', '    [*] --> S1']
    for i, step in enumerate(steps, start=1):
        lines.append(f'    state "{_label(step)}" as S{i}')
        if i < len(steps):
            lines.append(f'    S{i} --> S{i + 1}')
    lines.append(f'    S{len(steps)} --> [*]')
    return '\n'.join(lines)


def _gantt(description: str, title: str) -> str:
    tasks: list[list[str]] = []
    for line in description.splitlines():
        parts = [p.strip() for p in line.split('|')]
        if len(parts) >= 3 and re.fullmatch(r'\d{4}-\d{2}-\d{2}', parts[1]) and re.fullmatch(r'\d+[dhw]', parts[2]):
            tasks.append(parts[:3])
    if not tasks:
        raise ValueError("규칙 기반 Gantt 입력은 '업무명 | YYYY-MM-DD | 5d' 형식의 행이 필요합니다.")
    lines = ['gantt', f'    title {_label(title)}', '    dateFormat YYYY-MM-DD', '    section 계획']
    for i, (name, start, duration) in enumerate(tasks[:_MAX_STEPS], start=1):
        lines.append(f'    {_label(name)} :t{i}, {start}, {duration}')
    return '\n'.join(lines)


def build_fallback_spec(description: str, diagram_type: str, title: str = '') -> DiagramSpec:
    """LLM 없이 결정적 규칙으로 Mermaid 를 만든다. 의미 추론이 아닌 구조화만 한다."""

    resolved_title = title.strip() or '업무 다이어그램'
    if diagram_type == 'gantt':
        source = _gantt(description, resolved_title)
    else:
        steps = _steps(description)
        builders = {'flowchart': _flowchart, 'sequence': _sequence, 'state': _state}
        source = builders[diagram_type](steps)
    source, warnings = validate_mermaid(source, diagram_type)
    return DiagramSpec(diagram_type=diagram_type, title=resolved_title, mermaid=source, warnings=warnings)


def _extract_json(text: str) -> dict[str, Any]:
    """LLM 응답에서 첫 JSON 객체를 파싱한다(코드펜스/잡음 허용)."""

    candidate = text.strip()
    if candidate.startswith('```'):
        candidate = re.sub(r'^```[a-zA-Z0-9]*\s*|\s*```$', '', candidate).strip()
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', candidate, flags=re.S)
        if not match:
            raise ValueError('LLM 응답에서 JSON 객체를 찾지 못했습니다')
        return json.loads(match.group(0))


def build_llm_spec(
    request: DiagramGenerateRequest,
    client: OpenAiCompatibleClient,
) -> DiagramSpec:
    """활성 LLM 연결로 Mermaid 를 제안받아 검증한다. 실패 시 예외 → 라우트가 폴백."""

    user = json.dumps(
        {
            'diagram_type': request.diagram_type,
            'title': request.title or '업무 다이어그램',
            'description': request.description,
        },
        ensure_ascii=False,
        indent=2,
    )
    content = client.chat(
        [
            {'role': 'system', 'content': _LLM_SYSTEM_PROMPT},
            {'role': 'user', 'content': user},
        ],
        max_tokens=3500,
    )
    payload = _extract_json(content)
    mermaid = payload.get('mermaid')
    if not isinstance(mermaid, str) or not mermaid.strip():
        raise ValueError('LLM 응답에 mermaid 소스가 없습니다')
    title = request.title.strip() or str(payload.get('title') or '업무 다이어그램')
    source, warnings = validate_mermaid(mermaid, request.diagram_type)
    return DiagramSpec(diagram_type=request.diagram_type, title=title, mermaid=source, warnings=warnings)


def _resolve_spec(
    request: DiagramGenerateRequest,
    client: OpenAiCompatibleClient | None,
) -> tuple[DiagramSpec, list[str], bool]:
    """LLM 우선, 실패/미설정 시 규칙 기반. (스펙, 경고, llm사용여부) 반환."""

    warnings: list[str] = []
    if request.ai_assist and client is not None:
        try:
            spec = build_llm_spec(request, client)
            return spec, warnings, True
        except Exception as exc:  # noqa: BLE001 - 폴백 신호로 흡수
            warnings.append(f'LLM 다이어그램 생성 실패로 규칙 기반 생성을 사용했습니다: {exc}')
    elif request.ai_assist and client is None:
        warnings.append('AI 생성을 요청했지만 활성 LLM 연결이 없어 규칙 기반 생성을 사용했습니다.')
    spec = build_fallback_spec(request.description, request.diagram_type, request.title)
    return spec, warnings, False


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def generate_diagram(
    *,
    store: OfficeJobStore,
    owner_id: int,
    request: DiagramGenerateRequest,
    client: OpenAiCompatibleClient | None,
    app_version: str,
) -> dict[str, Any]:
    """다이어그램 job 을 생성한다. 산출물: diagram.mmd / diagram_spec.json / manifest.json."""

    record = store.create(
        'diagram',
        owner_id=owner_id,
        request_summary={
            'diagram_type': request.diagram_type,
            'ai_assist': request.ai_assist,
            'description_chars': len(request.description),
        },
    )
    job_id = record['job_id']
    try:
        spec, warnings, llm_used = _resolve_spec(request, client)
        warnings = list(dict.fromkeys([*warnings, *spec.warnings]))
        source_path = store.write_text(job_id, 'diagram.mmd', spec.mermaid + '\n', 'text/plain')
        store.write_text(job_id, 'diagram_spec.json', spec.model_dump_json(indent=2), 'application/json')
        manifest = {
            'schema_version': '1.0',
            'aeroone_version': app_version,
            'service': 'diagram',
            'job_id': job_id,
            'generated_at': datetime.now(UTC).isoformat(),
            'input': {
                'description_sha256': _sha256_text(request.description),
                'diagram_type': request.diagram_type,
            },
            'processing': {'llm_used': llm_used, 'security_level': 'strict'},
            'outputs': {'mmd': source_path.name, 'render': 'browser SVG/PNG'},
            'warnings': warnings,
        }
        store.write_text(job_id, 'manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2), 'application/json')
        return store.complete(
            job_id,
            warnings=warnings,
            extra={
                'title': spec.title,
                'llm_used': llm_used,
                'diagram_type': request.diagram_type,
                'mermaid': spec.mermaid,
                'preview_url': f'/api/v1/office-tools/jobs/{job_id}/artifacts/diagram.mmd',
                'bundle_url': f'/api/v1/office-tools/jobs/{job_id}/bundle',
            },
        )
    except Exception as exc:
        store.fail(job_id, str(exc))
        raise
