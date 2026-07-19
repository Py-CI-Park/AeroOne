"""최신본 판별 — 날짜·버전·'최종' 표식 기반 단위 검증."""

from __future__ import annotations

from app.modules.aero_work.version_ranker import mark_latest


def _hits(*paths: str) -> list[dict]:
    return [
        {'folder_id': 1, 'folder_name': 'kb', 'rel_path': p, 'chunk_index': 0, 'content': 'x', 'score': 0.5}
        for p in paths
    ]


def _latest(hits: list[dict]) -> list[str]:
    return [hit['rel_path'] for hit in hits if hit['is_latest']]


def test_latest_by_date() -> None:
    hits = _hits('성과평가_20260101.md', '성과평가_20260715.md', '성과평가_20250101.md')
    mark_latest(hits)
    assert _latest(hits) == ['성과평가_20260715.md']


def test_latest_by_version_number() -> None:
    hits = _hits('보고서 v1.md', '보고서 v3.md', '보고서 v2.md')
    mark_latest(hits)
    assert _latest(hits) == ['보고서 v3.md']


def test_final_keyword_wins() -> None:
    hits = _hits('예산안.md', '예산안_최종.md')
    mark_latest(hits)
    assert _latest(hits) == ['예산안_최종.md']


def test_single_document_not_marked() -> None:
    hits = _hits('단일문서.md')
    mark_latest(hits)
    assert _latest(hits) == []


def test_distinct_base_names_are_separate_groups() -> None:
    hits = _hits('예산_v1.md', '성과_v2.md')
    mark_latest(hits)
    assert _latest(hits) == []  # 각 그룹이 단일 판본이라 미표시
