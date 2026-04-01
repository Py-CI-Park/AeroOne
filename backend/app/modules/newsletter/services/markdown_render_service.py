from __future__ import annotations

import markdown

from app.modules.newsletter.services.html_render_service import HtmlRenderService
from app.modules.shared.storage.service import StorageService


class MarkdownRenderService:
    def __init__(self, storage_service: StorageService, html_render_service: HtmlRenderService | None = None) -> None:
        self.storage_service = storage_service
        self.html_render_service = html_render_service or HtmlRenderService(storage_service)

    def render(self, relative_path: str) -> str:
        markdown_text = self.storage_service.read_managed_text(relative_path)
        rendered = markdown.markdown(markdown_text, extensions=['tables', 'fenced_code', 'sane_lists'])
        return self.html_render_service.sanitize_html(rendered)
