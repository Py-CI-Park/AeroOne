from __future__ import annotations

from bs4 import BeautifulSoup

from app.modules.shared.storage.service import StorageService

HTML_CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; frame-ancestors 'self'; base-uri 'none'; form-action 'none'"


class HtmlRenderService:
    def __init__(self, storage_service: StorageService) -> None:
        self.storage_service = storage_service

    def render(self, relative_path: str) -> str:
        html = self.storage_service.read_external_text(relative_path)
        return self.sanitize_html(html)

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
