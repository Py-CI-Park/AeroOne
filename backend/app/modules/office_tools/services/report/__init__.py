"""보고서 스튜디오(svc01) 서비스 패키지.

Markdown → 사내 표준 HTML 보고서 변환을 이미지 임베드/AI 편집/오프라인 렌더 4개
모듈로 나눠 담는다(작은 파일 원칙). 라우트는 ``generate_report`` 만 쓴다.
"""

from __future__ import annotations

from .assets import embed_markdown_images, unpack_asset_zip
from .enhancer import EnhancementResult, enhance_markdown
from .renderer import markdown_to_body, render_report_html
from .service import generate_report

__all__ = [
    'embed_markdown_images',
    'unpack_asset_zip',
    'EnhancementResult',
    'enhance_markdown',
    'markdown_to_body',
    'render_report_html',
    'generate_report',
]
