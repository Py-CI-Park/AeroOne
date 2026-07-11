"""보고서 이미지 자산 처리 — MVP ``svc01/assets.py`` 를 AeroOne 로 포팅.

두 가지 일을 한다.

1. ``unpack_asset_zip``: 업로드된 ZIP 에서 이미지 파일만 안전하게 추출한다(경로 탈출/
   파일 수/총 용량 상한). 폐쇄망에서 신뢰할 수 없는 압축 폭탄을 방어한다.
2. ``embed_markdown_images``: Markdown 의 ``![alt](path)`` 참조를 실제 자산의
   base64 ``data:`` URI 로 치환한다. 외부(http/https)·이미 data:· 앵커(#) 참조는
   그대로 둔다. SVG 는 ``security.sanitize_svg`` 로 정제한 뒤 임베드한다.

산출 HTML 은 이미지가 문서 안에 인라인되므로 외부 요청이 없다(폐쇄망 순도).
"""

from __future__ import annotations

import base64
import mimetypes
import re
import urllib.parse
import zipfile
from io import BytesIO
from pathlib import PurePosixPath

from app.modules.office_tools.security import sanitize_svg

IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'}
_IMAGE_RE = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')


def _normalize_key(name: str) -> str:
    """자산 키/경로를 POSIX 상대경로로 정규화한다(백슬래시/쿼리/선행 ./ 제거)."""

    decoded = urllib.parse.unquote(name).replace('\\', '/')
    decoded = decoded.split('#', 1)[0].split('?', 1)[0]
    while decoded.startswith('./'):
        decoded = decoded[2:]
    return str(PurePosixPath(decoded)).lstrip('/')


def unpack_asset_zip(
    data: bytes,
    *,
    max_files: int = 200,
    max_total_bytes: int = 50 * 1024 * 1024,
) -> dict[str, bytes]:
    """ZIP 에서 이미지 파일만 추출한다. 경로 탈출/파일 수/총 용량 위반 시 ``ValueError``."""

    assets: dict[str, bytes] = {}
    total = 0
    with zipfile.ZipFile(BytesIO(data)) as archive:
        infos = [info for info in archive.infolist() if not info.is_dir()]
        if len(infos) > max_files:
            raise ValueError(f'ZIP 안 파일 수가 {max_files}개를 초과했습니다')
        for info in infos:
            name = _normalize_key(info.filename)
            if name.startswith('../') or '/../' in name:
                raise ValueError('ZIP 에 안전하지 않은 경로가 있습니다')
            suffix = PurePosixPath(name).suffix.lower()
            if suffix not in IMAGE_SUFFIXES:
                continue
            raw = archive.read(info)
            total += len(raw)
            if total > max_total_bytes:
                raise ValueError('ZIP 압축 해제 총 용량 상한을 초과했습니다')
            assets[name] = raw
    return assets


def embed_markdown_images(markdown_text: str, assets: dict[str, bytes]) -> tuple[str, list[str], int]:
    """Markdown 이미지 참조를 자산의 base64 data URI 로 치환한다.

    반환은 ``(치환된 Markdown, 경고 목록, 임베드한 이미지 수)``.
    """

    normalized: dict[str, bytes] = {}
    basename_index: dict[str, list[str]] = {}
    for name, data in assets.items():
        key = _normalize_key(name)
        normalized[key] = data
        basename_index.setdefault(PurePosixPath(key).name, []).append(key)

    warnings: list[str] = []
    embedded = 0

    def _replace(match: re.Match[str]) -> str:
        nonlocal embedded
        alt = match.group(1)
        target = match.group(2).strip()
        path_token = target
        title_suffix = ''
        title_match = re.match(r"^(?:<([^>]+)>|([^\s]+))(\s+['\"].*['\"])?$", target)
        if title_match:
            path_token = title_match.group(1) or title_match.group(2) or target
            title_suffix = title_match.group(3) or ''
        if re.match(r'^(?:https?://|data:|#)', path_token, flags=re.I):
            return match.group(0)

        key = _normalize_key(path_token)
        selected = key if key in normalized else None
        if not selected:
            candidates = basename_index.get(PurePosixPath(key).name, [])
            if len(candidates) == 1:
                selected = candidates[0]
        if not selected:
            warnings.append(f'이미지 자산을 찾지 못했습니다: {path_token}')
            return match.group(0)

        raw = normalized[selected]
        suffix = PurePosixPath(selected).suffix.lower()
        if suffix == '.svg':
            raw = sanitize_svg(raw.decode('utf-8', errors='strict')).encode('utf-8')
            mime = 'image/svg+xml'
        else:
            mime = mimetypes.guess_type(selected)[0] or 'application/octet-stream'
        uri = f'data:{mime};base64,{base64.b64encode(raw).decode("ascii")}'
        embedded += 1
        return f'![{alt}]({uri}{title_suffix})'

    return _IMAGE_RE.sub(_replace, markdown_text), list(dict.fromkeys(warnings)), embedded
