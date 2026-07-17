"""Civil Aircraft 대시보드 v1.8 번들 무결성·정합 회귀.

이 스위트는 v1.8 릴리스 세트가 내부적으로 일관됨을 강제한다:
- SHA256SUMS_v1.8.txt 가 저장소 실재 파일의 실제 해시와 일치(자기 자신은 제외)하고 누락/잉여가 없다.
- 경량 메타(civil-aircraft-meta.v1.8.js)가 전체 데이터의 순수 파생물이다(build_civil_meta 로 재계산해 비교).
- 실행 번들에 v1.7 잔재 파일명이 남지 않았다(역사 baseline 문서는 예외).
- v1.8 상호작용/프리셋/측면 후퇴각/지연로딩 마커가 소스에 실재한다.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path

import pytest

_BUNDLE = Path(__file__).resolve().parents[2] / 'app/modules/reports/civil_aircraft_dashboard'
_SHA_FILE = _BUNDLE / 'SHA256SUMS_v1.8.txt'


def _load_build_meta_module():
    path = Path(__file__).resolve().parents[2] / 'scripts/build_civil_meta.py'
    spec = importlib.util.spec_from_file_location('build_civil_meta', path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha_entries() -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in _SHA_FILE.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        digest, rel = line.split('  ', 1)
        entries[rel] = digest
    return entries


def test_sha256sums_v18_matches_actual_repo_files() -> None:
    entries = _sha_entries()
    # 매니페스트에 나열된 모든 파일이 실재하고 해시가 일치한다.
    for rel, digest in entries.items():
        target = _BUNDLE / rel
        assert target.is_file(), f'SHA256SUMS_v1.8 lists a missing file: {rel}'
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        assert actual == digest, f'hash mismatch for {rel}'
    # 저장소 실재 번들 파일(매니페스트 자기 자신 제외)이 모두 매니페스트에 있다 — 잉여/누락 0.
    present = {
        p.relative_to(_BUNDLE).as_posix()
        for p in _BUNDLE.rglob('*')
        if p.is_file() and p.name != 'SHA256SUMS_v1.8.txt'
    }
    listed = set(entries)
    assert present == listed, f'manifest drift — only-in-repo={present - listed}, only-in-manifest={listed - present}'


def test_meta_bundle_is_pure_derivation_of_full_data() -> None:
    module = _load_build_meta_module()
    data = json.loads((_BUNDLE / 'data/Civil_Aircraft_Data_v1.8.json').read_text(encoding='utf-8'))
    expected = module.build_meta(data)

    js = (_BUNDLE / 'assets/js/civil-aircraft-meta.v1.8.js').read_text(encoding='utf-8')
    match = re.search(r'window\.CIVIL_AIRCRAFT_META=(\{.*\});', js, re.DOTALL)
    assert match, 'meta bundle must assign window.CIVIL_AIRCRAFT_META'
    committed = json.loads(match.group(1))

    # 커밋된 메타가 전체 데이터에서 재계산한 값과 정확히 일치(손편집 시 실패).
    assert committed == expected
    assert committed['version'] == '1.8'
    assert committed['counts']['aircraftCount'] == len(data['aircraft'])


def test_runtime_data_js_and_json_share_metadata_version() -> None:
    jsond = json.loads((_BUNDLE / 'data/Civil_Aircraft_Data_v1.8.json').read_text(encoding='utf-8'))
    js = (_BUNDLE / 'assets/js/civil-aircraft-data.v1.8.js').read_text(encoding='utf-8').strip()
    assert js.startswith('window.CIVIL_AIRCRAFT_DATA=')
    embedded = json.loads(js[len('window.CIVIL_AIRCRAFT_DATA='):].rstrip(';'))
    # 다운로드 JSON 과 런타임 JS 데이터의 metadata 가 동일해야 화면 버전 표기가 어긋나지 않는다.
    assert embedded['metadata']['version'] == jsond['metadata']['version'] == '1.8'
    assert len(embedded['aircraft']) == len(jsond['aircraft']) == 65


def test_no_v17_named_runtime_artifacts_remain() -> None:
    # 역사 baseline 문서(sources/baseline/V1.x_*)만 v1.7 이름을 유지할 수 있다.
    stale = [
        p.relative_to(_BUNDLE).as_posix()
        for p in _BUNDLE.rglob('*')
        if p.is_file() and 'v1.7' in p.name.lower() and 'baseline' not in p.parts
    ]
    assert not stale, f'stale v1.7 runtime artifacts: {stale}'


def test_v18_feature_markers_present_in_source() -> None:
    svg = (_BUNDLE / 'assets/js/aircraft-svg.v1.8.js').read_text(encoding='utf-8')
    dash = (_BUNDLE / 'assets/js/dashboard.v1.8.js').read_text(encoding='utf-8')
    index = (_BUNDLE / 'index.html').read_text(encoding='utf-8')

    # 프리셋: 최소 8종 이상의 패밀리 오버라이드 + resolveParams 병합.
    assert 'FAMILY_PRESETS' in svg and 'function resolveParams' in svg
    preset_keys = re.findall(r"'([^']+)':\{wing", svg)
    assert len(preset_keys) >= 8, f'expected >=8 silhouette presets, got {preset_keys}'
    # 측면 후퇴각 반영.
    assert 'wingSweepDeg' in svg and 'swp=' in svg
    # 상호작용 훅(실루엣 data-aircraft-id) + 대시보드 bindScale.
    assert 'silhouette-hit' in svg and 'data-aircraft-id' in svg
    assert 'function bindScale' in dash and "getElementById('scaleSavePng')" in dash
    # 지연 로딩: 포털은 메타+포털만 로드하고 전체 데이터 스크립트를 포함하지 않는다.
    assert 'civil-aircraft-meta.v1.8.js' in index and 'portal.v1.8.js' in index
    assert 'civil-aircraft-data' not in index


@pytest.mark.parametrize('doc', ['CHANGELOG_v1.8.md', 'REVISION_v1.8.md', 'BUILD_INTEGRITY_v1.8.json', 'README_v1.8.md'])
def test_v18_release_doc_set_present(doc: str) -> None:
    assert (_BUNDLE / doc).is_file(), f'missing v1.8 release doc: {doc}'
