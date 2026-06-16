from __future__ import annotations

from bs4 import BeautifulSoup

from app.modules.shared.storage.service import StorageService

HTML_CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; frame-ancestors 'self'; base-uri 'none'; form-action 'none'"

def sanitize_html_fragment(html: str) -> str:
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup.find_all(['script', 'iframe', 'object', 'embed', 'base', 'form', 'link']):
        tag.decompose()
    for tag in soup.find_all(True):
        for attr in list(tag.attrs.keys()):
            if attr.lower().startswith('on'):
                del tag.attrs[attr]
        if tag.name == 'a' and tag.get('href'):
            href = tag.get('href', '')
            if href.startswith(('http://', 'https://', 'mailto:')):
                tag['target'] = '_blank'
                tag['rel'] = 'noopener noreferrer'
            elif href.startswith('#'):
                tag.attrs.pop('target', None)
                tag.attrs.pop('rel', None)
            else:
                del tag.attrs['href']
        elif tag.has_attr('src'):
            src = tag.get('src', '')
            if not src.startswith('data:'):
                del tag.attrs['src']
    return str(soup)


class HtmlRenderService:
    def __init__(self, storage_service: StorageService) -> None:
        self.storage_service = storage_service

    def render(self, relative_path: str) -> str:
        # 로컬 _database/newsletter 의 HTML 은 운영자 자신의 파이프라인(Newsletter_AI)
        # 산출물 = 신뢰 콘텐츠다. 최신 산출물은 <script> 로 본문(기사 카드)을
        # innerHTML 주입하는 JS 렌더 방식이라 인라인 스크립트/스타일/콘텐츠는
        # 그대로 보존한다. 다만 폐쇄망 순도를 위해 "외부로 자동 요청을 내보내는"
        # 참조만 차단한다(외부 폰트 <link>, 외부 src). 격리는 프론트엔드의
        # sandbox iframe(allow-scripts, 별 문서)이 담당한다.
        # (sanitize_html 은 신뢰도가 낮은 Markdown 변환 경로에서 계속 사용한다.)
        html = self.storage_service.read_external_text(relative_path)
        return self.strip_external_resources(html)

    def strip_external_resources(self, html: str) -> str:
        soup = BeautifulSoup(html, 'html.parser')
        # 외부 스타일/폰트 <link>(preconnect 포함)는 외부 요청만 유발하고 본문과
        # 무관하므로 제거. 인라인 <style> 은 보존되어 레이아웃은 유지된다.
        for tag in soup.find_all('link'):
            tag.decompose()
        # 외부 절대 URL(src)을 가리키는 자동 로드 리소스의 src 를 제거해 요청을
        # 차단한다. data:/상대경로는 둔다. 인라인 <script>(src 없음)는 보존되어
        # 본문 주입 JS 가 그대로 동작한다.
        for tag in soup.find_all(src=True):
            src = (tag.get('src') or '').strip().lower()
            if src.startswith(('http://', 'https://', '//')):
                del tag.attrs['src']
        # 외부 <a> 링크는 사용자 클릭으로만 이동하므로 보존하되 새 탭 + noopener.
        # 같은 문서 내부 목차(#...)는 현재 iframe/새 창 안에서 스크롤해야 하므로 target 을 붙이지 않는다.
        for anchor in soup.find_all('a', href=True):
            href = anchor.get('href', '')
            if href.startswith(('http://', 'https://', 'mailto:')):
                anchor['target'] = '_blank'
                anchor['rel'] = 'noopener noreferrer'
            elif href.startswith('#'):
                anchor.attrs.pop('target', None)
                anchor.attrs.pop('rel', None)
        return str(soup)

    def sanitize_html(self, html: str) -> str:
        return sanitize_html_fragment(html)
