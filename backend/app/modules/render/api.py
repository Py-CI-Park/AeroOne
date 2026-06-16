from __future__ import annotations

import markdown
from fastapi import APIRouter

from app.modules.newsletter.services.html_render_service import sanitize_html_fragment
from app.modules.render.schemas import RenderRequest

router = APIRouter()


@router.post('')
def render_text(request: RenderRequest) -> dict[str, str]:
    # 순수 텍스트 -> 서버 sanitize HTML. 저장소/파일 접근 0 (StorageService 미사용),
    # path-guard 표면을 넓히지 않는다. markdown 경로는 뉴스레터와 동일한 확장으로
    # 변환 후 sanitize 하고, html 경로는 바로 sanitize 한다.
    if request.type == 'markdown':
        rendered = markdown.markdown(request.text, extensions=['tables', 'fenced_code', 'sane_lists'])
        return {'html': sanitize_html_fragment(rendered)}
    return {'html': sanitize_html_fragment(request.text)}
