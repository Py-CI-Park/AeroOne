from __future__ import annotations

from bs4 import BeautifulSoup

from app.modules.shared.storage.service import StorageService

HTML_CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; frame-ancestors 'self'; base-uri 'none'; form-action 'none'"


class HtmlRenderService:
    def __init__(self, storage_service: StorageService) -> None:
        self.storage_service = storage_service

    def render(self, relative_path: str) -> str:
        # 로컬 Newsletter/output 의 HTML 은 운영자 자신의 파이프라인(Newsletter_AI)
        # 산출물 = 신뢰 콘텐츠다. 최신 산출물은 <script> 로 본문(기사 카드)을
        # innerHTML 주입하는 JS 렌더 방식이라, sanitize 로 <script> 를 제거하면
        # 본문이 통째로 사라진다. 따라서 신뢰 콘텐츠는 원본 그대로 서빙하고,
        # 격리는 프론트엔드의 sandbox iframe(allow-scripts, 별 문서)에 맡긴다.
        # (sanitize_html 은 신뢰도가 낮은 Markdown 변환 경로에서 계속 사용한다.)
        return self.storage_service.read_external_text(relative_path)

    def sanitize_html(self, html: str) -> str:
        soup = BeautifulSoup(html, 'html.parser')
        for tag in soup.find_all(['script', 'iframe', 'object', 'embed', 'base', 'form', 'link']):
            tag.decompose()
        for tag in soup.find_all(True):
            for attr in list(tag.attrs.keys()):
                if attr.lower().startswith('on'):
                    del tag.attrs[attr]
            if tag.name == 'a' and tag.get('href'):
                href = tag.get('href', '')
                if href.startswith(('http://', 'https://', 'mailto:', '#')):
                    tag['target'] = '_blank'
                    tag['rel'] = 'noopener noreferrer'
                else:
                    del tag.attrs['href']
            elif tag.has_attr('src'):
                src = tag.get('src', '')
                if not src.startswith('data:'):
                    del tag.attrs['src']
        return str(soup)
