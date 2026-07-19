"""지식폴더 파일 → 평문 텍스트 추출.

P2 코어는 텍스트/마크다운/HTML/CSV 등 텍스트 계열만 다룬다. PDF/DOCX/HWPX 본문 추출은
후속(P3 HWPX 파이프라인과 함께) 범위다 — ``docs/dev_plan/aero-work-plan.md`` §2.1 위험 항목.
"""

from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

SUPPORTED_SUFFIXES = frozenset(
    {'.txt', '.md', '.markdown', '.mdx', '.html', '.htm', '.csv', '.tsv', '.log', '.rst', '.json'}
)
_HTML_SUFFIXES = frozenset({'.html', '.htm'})


def is_supported(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_SUFFIXES


def extract_text(path: Path) -> str:
    """지원 파일에서 평문을 추출한다. HTML 은 script/style 제거 후 텍스트만 남긴다."""

    suffix = path.suffix.lower()
    raw = path.read_text(encoding='utf-8', errors='replace')
    if suffix in _HTML_SUFFIXES:
        soup = BeautifulSoup(raw, 'html.parser')
        for tag in soup(['script', 'style']):
            tag.decompose()
        return soup.get_text(separator='\n')
    return raw
