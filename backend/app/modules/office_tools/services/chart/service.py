"""차트 스튜디오(svc02) 서비스 — MVP ``svc02_chart_studio/service.py`` 포팅.

데이터 업로드를 pandas 로 집계해 브라우저 ECharts option(JSON)을 만든다. 렌더링 결정
(BUILD_CONTRACT §2.5)에 따라 서버 matplotlib SVG/PNG 산출은 제거했다. 산출물은
``chart_data.csv`` / ``chart_spec.json`` / ``echarts_option.json`` / ``manifest.json`` 뿐이며,
미리보기는 프런트 ECharts 가 option 으로 렌더한다.

AI 보조(``ai_assist``)는 활성 LLM 연결(``OpenAiCompatibleClient``)로 ChartSpec 을 제안받고,
연결이 없거나 실패하면 규칙 기반 ``auto_chart_spec`` 으로 폴백한다(경고 첨부). 수동 스펙
(``manual_spec``)이 오면 LLM 을 건너뛰고 검증만 한다.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.modules.ai.openai_client import OpenAiCompatibleClient
from app.modules.office_tools.core.job_store import OfficeJobStore

from .data_loader import dataframe_profile, load_dataframe
from .processor import echarts_option, prepare_chart
from .refine import llm_refine_chart_spec, rule_refine_chart_spec
from .schemas import ChartSpec
from .spec_builder import auto_chart_spec, llm_chart_spec


def inspect_data(
    *,
    filename: str,
    data: bytes,
    max_upload_bytes: int,
    max_data_rows: int,
) -> dict[str, Any]:
    """데이터 프로필(행/열/샘플)을 반환한다. 크기/행수 초과·미지원 확장자는 ValueError."""

    if len(data) > max_upload_bytes:
        raise ValueError('데이터 업로드가 허용 크기를 초과했습니다')
    frame = load_dataframe(filename, data, max_data_rows)
    return dataframe_profile(frame)


def _parse_spec_json(spec_json: str | None, *, label: str) -> dict[str, Any] | None:
    """스펙 JSON 문자열을 dict 로 파싱한다. 비면 None, 잘못되면 ValueError."""

    if not spec_json or not spec_json.strip():
        return None
    try:
        parsed = json.loads(spec_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f'{label} JSON 이 유효하지 않습니다: {exc}') from exc
    if not isinstance(parsed, dict):
        raise ValueError(f'{label}은(는) JSON 객체여야 합니다')
    return parsed


def _parse_manual_spec(manual_spec_json: str | None) -> dict[str, Any] | None:
    """수동 스펙 JSON 문자열을 dict 로 파싱한다. 비면 None, 잘못되면 ValueError."""

    return _parse_spec_json(manual_spec_json, label='수동 차트 스펙')


def _parse_previous_spec(previous_spec_json: str | None) -> dict[str, Any] | None:
    """직전 스펙 JSON 문자열을 dict 로 파싱한다. 비면 None, 잘못되면 ValueError."""

    return _parse_spec_json(previous_spec_json, label='직전 차트 스펙')


def _resolve_spec(
    frame,
    *,
    prompt: str,
    ai_assist: bool,
    requested_type: str | None,
    manual_spec: dict[str, Any] | None,
    previous_spec: dict[str, Any] | None,
    client: OpenAiCompatibleClient | None,
) -> tuple[ChartSpec, list[str], dict[str, Any], bool]:
    """수동 > 직전 스펙+명령(refine) > LLM 신규 > 규칙 기반 신규 순으로 스펙을 결정한다.

    (스펙, 경고, llm메타, 직전 스펙에서 리파인했는지) 를 반환한다.
    """

    columns = [str(c) for c in frame.columns]
    warnings: list[str] = []
    if manual_spec is not None:
        spec = ChartSpec.model_validate(manual_spec)
        spec.validate_columns(columns)
        if previous_spec is not None:
            warnings.append('수동 스펙과 직전 스펙이 함께 전달되어 수동 스펙을 사용했습니다.')
        return spec, warnings, {'used': False}, False

    if previous_spec is not None:
        previous = ChartSpec.model_validate(previous_spec)
        previous.validate_columns(columns)
        if ai_assist and client is not None:
            try:
                spec, meta = llm_refine_chart_spec(frame, previous, prompt, client)
                return spec, warnings, {'used': True, **meta}, True
            except Exception as exc:  # noqa: BLE001 - 폴백 신호로 흡수
                warnings.append(f'LLM 차트 리파인 실패로 규칙 기반 리파인을 사용했습니다: {exc}')
        spec, refine_warnings = rule_refine_chart_spec(previous, prompt)
        return spec, [*warnings, *refine_warnings], {'used': False}, True

    if ai_assist and client is not None:
        try:
            spec, meta = llm_chart_spec(frame, prompt, client)
            return spec, warnings, {'used': True, **meta}, False
        except Exception as exc:  # noqa: BLE001 - 폴백 신호로 흡수
            warnings.append(f'LLM 차트 추천 실패로 규칙 기반 추천을 사용했습니다: {exc}')
    elif ai_assist and client is None:
        warnings.append('AI 추천을 요청했지만 활성 LLM 연결이 없어 규칙 기반 추천을 사용했습니다.')
    return auto_chart_spec(frame, prompt, requested_type), warnings, {'used': False}, False


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def generate_chart(
    *,
    store: OfficeJobStore,
    owner_id: int,
    filename: str,
    data: bytes,
    prompt: str,
    ai_assist: bool,
    requested_type: str | None,
    manual_spec_json: str | None,
    previous_spec_json: str | None = '',
    client: OpenAiCompatibleClient | None,
    app_version: str,
    max_upload_bytes: int,
    max_data_rows: int,
) -> dict[str, Any]:
    """차트 job 을 생성한다. 산출물: chart_data.csv / chart_spec.json / echarts_option.json / manifest.json."""

    record = store.create(
        'chart',
        owner_id=owner_id,
        request_summary={
            'source_filename': Path(filename).name,
            'ai_assist': ai_assist,
            'prompt_chars': len(prompt),
        },
    )
    job_id = record['job_id']
    try:
        if len(data) > max_upload_bytes:
            raise ValueError('데이터 업로드가 허용 크기를 초과했습니다')
        manual_spec = _parse_manual_spec(manual_spec_json)
        previous_spec = _parse_previous_spec(previous_spec_json)
        frame = load_dataframe(filename, data, max_data_rows)
        profile = dataframe_profile(frame)

        spec, warnings, llm_meta, refined_from_previous = _resolve_spec(
            frame,
            prompt=prompt,
            ai_assist=ai_assist,
            requested_type=requested_type,
            manual_spec=manual_spec,
            previous_spec=previous_spec,
            client=client,
        )
        prepared = prepare_chart(frame, spec)
        warnings = list(dict.fromkeys([*warnings, *prepared.warnings]))
        option = echarts_option(spec, prepared)

        store.write_bytes(job_id, 'chart_data.csv', prepared.frame.to_csv(index=False).encode('utf-8-sig'), 'text/csv')
        store.write_text(job_id, 'chart_spec.json', spec.model_dump_json(indent=2), 'application/json')
        store.write_text(job_id, 'echarts_option.json', json.dumps(option, ensure_ascii=False, indent=2), 'application/json')
        manifest = {
            'schema_version': '1.0',
            'aeroone_version': app_version,
            'service': 'chart',
            'job_id': job_id,
            'generated_at': datetime.now(UTC).isoformat(),
            'input': {'filename': Path(filename).name, 'sha256': _sha256_bytes(data), 'profile': profile},
            'processing': {'llm': llm_meta, 'spec': spec.model_dump(), 'refined_from_previous': refined_from_previous},
            'outputs': {'render': 'browser ECharts', 'data_rows': int(len(prepared.frame))},
            'warnings': warnings,
        }
        store.write_text(job_id, 'manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2), 'application/json')
        return store.complete(
            job_id,
            warnings=warnings,
            extra={
                'title': spec.title,
                'chart_spec': spec.model_dump(),
                'echarts_option': option,
                'llm_used': bool(llm_meta.get('used')),
                'preview_url': f'/api/v1/office-tools/jobs/{job_id}/artifacts/echarts_option.json',
                'bundle_url': f'/api/v1/office-tools/jobs/{job_id}/bundle',
            },
        )
    except Exception as exc:
        store.fail(job_id, str(exc))
        raise
