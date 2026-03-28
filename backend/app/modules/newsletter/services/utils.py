from __future__ import annotations

from datetime import UTC, datetime
import re
import unicodedata


def slugify(value: str, *, fallback: str = 'item') -> str:
    normalized = unicodedata.normalize('NFKC', value).strip().lower()
    normalized = re.sub(r'[^\w\s-]', '', normalized)
    normalized = re.sub(r'[-\s]+', '-', normalized).strip('-')
    return normalized or fallback


def issue_key_to_datetime(issue_key: str) -> datetime:
    return datetime.strptime(issue_key, '%Y%m%d').replace(tzinfo=UTC)
