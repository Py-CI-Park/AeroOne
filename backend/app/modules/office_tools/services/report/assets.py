"""보고서 이미지 자산 처리 — MVP ``svc01/assets.py`` 를 AeroOne 로 포팅.

두 가지 일을 한다.

1. ``unpack_asset_zip``: 업로드된 ZIP 에서 이미지 파일만 청크로 안전하게 추출한다(경로 탈출/
   심볼릭 링크/파일 수/멤버·총 용량·압축률 상한). 폐쇄망에서 신뢰할 수 없는 압축 폭탄을 방어한다.
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
import zlib
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import PurePosixPath
from tempfile import SpooledTemporaryFile
from typing import BinaryIO

from app.modules.office_tools.limits import (
    MAX_REPORT_ASSET_TOTAL_BYTES,
    MAX_ZIP_CENTRAL_DIRECTORY_BYTES,
    OFFICE_STREAM_CHUNK_BYTES,
    UploadSizeLimitExceeded,
    ZipPreflight,
    preflight_zip_central_directory as _preflight_zip_central_directory,
    require_utf8_filename_within_limit,
)
from app.modules.office_tools.security import sanitize_svg

IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'}
UPLOAD_READ_CHUNK_BYTES = OFFICE_STREAM_CHUNK_BYTES
MAX_EMBEDDED_IMAGE_REFERENCES = 200
MAX_EMBEDDED_REPORT_BYTES = 50 * 1024 * 1024
MAX_ASSET_REFERENCE_BYTES = 4 * 1024
_UPLOAD_SPOOL_MAX_BYTES = 1024 * 1024
_IMAGE_RE = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
_ENCODED_PATH_SEPARATOR_RE = re.compile(r'%(?:25)*(?:2[fF]|5[cC]|00|3[aA])')
_RESIDUAL_ENCODED_TRAVERSAL_RE = re.compile(
    r'(?:^|/)(?:(?:\.|%(?:25)*2[eE])){1,2}(?=/|$)'
)
_INVALID_PERCENT_ESCAPE_RE = re.compile(r'%(?![0-9A-Fa-f]{2})')


def _unsafe_asset_path(value: str) -> bool:
    path = PurePosixPath(value)
    return (
        not value
        or '\x00' in value
        or '\\' in value
        or value.startswith('/')
        or re.match(r'^[A-Za-z]:', value) is not None
        or '..' in path.parts
        or path.is_absolute()
    )


def _canonicalize_asset_path(value: str) -> str:
    """상대 POSIX 자산 키를 정규화하고 경로 탈출을 거부한다."""
    candidate = str(PurePosixPath(value))
    if _unsafe_asset_path(value) or _unsafe_asset_path(candidate):
        raise ValueError('자산에 안전하지 않은 경로가 있습니다')
    return candidate


def _reject_residual_encoded_path_controls(decoded: str) -> None:
    """Reject controls that would only become paths after a second decode."""
    _canonicalize_asset_path(decoded)
    if (
        _ENCODED_PATH_SEPARATOR_RE.search(decoded)
        or _RESIDUAL_ENCODED_TRAVERSAL_RE.search(decoded)
    ):
        raise ValueError('자산에 안전하지 않은 경로가 있습니다')


def canonical_asset_name(name: str) -> str:
    """Keep ZIP member names literal while rejecting encoded path controls."""
    canonical = _canonicalize_asset_path(name)
    if (
        _ENCODED_PATH_SEPARATOR_RE.search(canonical)
        or _RESIDUAL_ENCODED_TRAVERSAL_RE.search(canonical)
    ):
        raise ValueError('자산에 안전하지 않은 경로가 있습니다')
    return canonical

def preflight_zip_central_directory(
    source: BinaryIO,
    *,
    max_files: int,
    max_compressed_bytes: int,
    max_filename_bytes: int,
    max_central_directory_bytes: int,
    canonicalize_filename: Callable[[str], str] | None = None,
    filename_limit_message: str = '자산 파일명 바이트 상한을 초과했습니다',
) -> ZipPreflight:
    """Preserve report asset defaults over the shared ZIP metadata preflight."""
    return _preflight_zip_central_directory(
        source,
        max_files=max_files,
        max_compressed_bytes=max_compressed_bytes,
        max_filename_bytes=max_filename_bytes,
        max_central_directory_bytes=max_central_directory_bytes,
        canonicalize_filename=canonicalize_filename or canonical_asset_name,
        filename_limit_message=filename_limit_message,
    )



def _require_asset_reference_within_limit(value: str) -> None:
    try:
        _bounded_utf8_byte_count(
            value,
            maximum=MAX_ASSET_REFERENCE_BYTES,
            limit_message='이미지 자산 참조 바이트 상한을 초과했습니다',
        )
    except UnicodeEncodeError as exc:
        raise ValueError('이미지 자산 참조는 UTF-8로 표현할 수 있어야 합니다') from exc


def _bounded_utf8_byte_count(value: str, *, maximum: int, limit_message: str) -> int:
    """Count UTF-8 bytes without materializing an encoded whole string."""
    total = 0
    for index, character in enumerate(value):
        code_point = ord(character)
        if 0xD800 <= code_point <= 0xDFFF:
            raise UnicodeEncodeError(
                'utf-8',
                value,
                index,
                index + 1,
                'surrogates not allowed',
            )
        if code_point < 0x80:
            total += 1
        elif code_point < 0x800:
            total += 2
        elif code_point < 0x10000:
            total += 3
        else:
            total += 4
        if total > maximum:
            raise ValueError(limit_message)
    return total


def _normalize_key(name: str) -> str:
    """Decode one raw Markdown path exactly once and require its asset key."""
    raw_path = name.split('#', 1)[0].split('?', 1)[0]
    _require_asset_reference_within_limit(raw_path)
    if _INVALID_PERCENT_ESCAPE_RE.search(raw_path):
        raise ValueError('자산에 안전하지 않은 경로가 있습니다')
    try:
        decoded = urllib.parse.unquote(raw_path, encoding='utf-8', errors='strict')
    except UnicodeDecodeError as exc:
        raise ValueError('자산에 안전하지 않은 경로가 있습니다') from exc
    _reject_residual_encoded_path_controls(decoded)
    return _canonicalize_asset_path(decoded)




@dataclass
class AssetNameRegistry:
    """요청 전체에서 자산 키·멤버 수·파일명 바이트 상한을 단조롭게 관리한다."""

    max_members: int
    max_filename_bytes: int
    member_count: int = 0
    canonical_keys: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if self.max_members < 1:
            raise ValueError('자산 멤버 수 상한은 1 이상이어야 합니다')
        if self.max_filename_bytes < 1:
            raise ValueError('자산 파일명 바이트 상한은 1 이상이어야 합니다')

    @property
    def remaining_members(self) -> int:
        return self.max_members - self.member_count

    def reserve(self, names: list[str]) -> None:
        if self.member_count + len(names) > self.max_members:
            raise ValueError(f'보고서 자산 멤버 수가 {self.max_members}개를 초과했습니다')

        pending: set[str] = set()
        for name in names:
            require_utf8_filename_within_limit(
                name,
                self.max_filename_bytes,
                limit_message='자산 파일명 바이트 상한을 초과했습니다',
                invalid_limit_message='자산 파일명 바이트 상한은 1 이상이어야 합니다',
                non_utf8_message='자산 파일명은 UTF-8로 표현할 수 있어야 합니다',
            )
            if name in pending or name in self.canonical_keys:
                raise ValueError('중복된 자산 canonical key가 있습니다')
            pending.add(name)

        self.member_count += len(names)
        self.canonical_keys.update(pending)



def _copy_bounded_stream(
    source: BinaryIO,
    destination: BinaryIO,
    *,
    max_bytes: int,
    limit_message: str = '업로드가 크기 상한을 초과했습니다',
) -> None:
    """스트림을 ``max_bytes + 1``까지만 읽어 대상에 복사한다."""
    if max_bytes < 0:
        raise ValueError('업로드 크기 상한은 0 이상이어야 합니다')

    total = 0
    while True:
        remaining = max_bytes + 1 - total
        chunk = source.read(min(UPLOAD_READ_CHUNK_BYTES, remaining))
        if not chunk:
            return
        total += len(chunk)
        if total > max_bytes:
            raise UploadSizeLimitExceeded(limit_message)
        destination.write(chunk)


@contextmanager
def staged_bounded_stream(
    source: BinaryIO,
    *,
    max_bytes: int,
    limit_message: str = '업로드가 크기 상한을 초과했습니다',
) -> Iterator[BinaryIO]:
    """크기가 검증된 업로드를 작은 스풀 파일로 제공한다."""
    with SpooledTemporaryFile(max_size=_UPLOAD_SPOOL_MAX_BYTES, mode='w+b') as staged:
        _copy_bounded_stream(
            source,
            staged,
            max_bytes=max_bytes,
            limit_message=limit_message,
        )
        staged.seek(0)
        yield staged


def read_bounded_bytes(source: BinaryIO, *, max_bytes: int) -> bytes:
    """스트림을 상한 확인 뒤에만 바이트로 materialize한다."""
    with staged_bounded_stream(source, max_bytes=max_bytes) as staged:
        return staged.read()




def _read_zip_member(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    *,
    current_total: int,
    max_member_bytes: int,
    max_total_bytes: int,
) -> tuple[bytes, int]:
    """멤버 하나를 상한을 넘지 않는 청크로 해제한다."""
    member_total = 0
    with SpooledTemporaryFile(max_size=_UPLOAD_SPOOL_MAX_BYTES, mode='w+b') as staged:
        with archive.open(info) as member:
            while True:
                member_remaining = max_member_bytes + 1 - member_total
                total_remaining = max_total_bytes + 1 - current_total
                chunk = member.read(min(UPLOAD_READ_CHUNK_BYTES, member_remaining, total_remaining))
                if not chunk:
                    staged.seek(0)
                    return staged.read(), current_total
                member_total += len(chunk)
                current_total += len(chunk)
                if member_total > max_member_bytes:
                    raise ValueError('ZIP 멤버 압축 해제 용량 상한을 초과했습니다')
                if current_total > max_total_bytes:
                    raise ValueError('ZIP 압축 해제 총 용량 상한을 초과했습니다')
                staged.write(chunk)


def unpack_asset_zip(
    data: bytes | BinaryIO,
    *,
    max_files: int = 200,
    max_total_bytes: int = MAX_REPORT_ASSET_TOTAL_BYTES,
    max_member_bytes: int = 20 * 1024 * 1024,
    max_compression_ratio: int = 100,
    max_compressed_bytes: int = 20 * 1024 * 1024,
    max_filename_bytes: int = 1024,
    max_central_directory_bytes: int = MAX_ZIP_CENTRAL_DIRECTORY_BYTES,
    member_registry: AssetNameRegistry | None = None,
) -> dict[str, bytes]:
    """ZIP 에서 이미지만 청크 추출하며 요청 공유 멤버 registry를 단조롭게 소비한다."""
    if (
        max_files < 1
        or max_total_bytes < 1
        or max_member_bytes < 1
        or max_compression_ratio < 1
        or max_compressed_bytes < 1
        or max_filename_bytes < 1
        or max_central_directory_bytes < 1
    ):
        raise ValueError('ZIP 용량 상한은 1 이상이어야 합니다')

    if isinstance(data, bytes):
        if len(data) > max_compressed_bytes:
            raise UploadSizeLimitExceeded('ZIP 압축 업로드 총 용량 상한을 초과했습니다')
        source = BytesIO(data)
    else:
        source = data
    registry = member_registry or AssetNameRegistry(max_files, max_filename_bytes)
    assets: dict[str, bytes] = {}
    total = 0
    try:
        preflight = preflight_zip_central_directory(
            source,
            max_files=max_files,
            max_compressed_bytes=max_compressed_bytes,
            max_filename_bytes=max_filename_bytes,
            max_central_directory_bytes=max_central_directory_bytes,
            canonicalize_filename=canonical_asset_name,
            filename_limit_message='자산 파일명 바이트 상한을 초과했습니다',
        )
        registry.reserve([member.canonical_name for member in preflight.members])
        with zipfile.ZipFile(source) as archive:
            infos = archive.infolist()
            if len(infos) != len(preflight.members):
                raise ValueError('ZIP 파일이 손상되었거나 읽을 수 없습니다')

            members: list[tuple[zipfile.ZipInfo, str]] = []
            for info, member in zip(infos, preflight.members, strict=True):
                if info.filename != member.filename or info.is_dir() != member.is_directory:
                    raise ValueError('ZIP 파일이 손상되었거나 읽을 수 없습니다')
                if not member.is_directory:
                    members.append((info, member.canonical_name))

            for info, name in members:
                suffix = PurePosixPath(name).suffix.lower()
                if suffix not in IMAGE_SUFFIXES:
                    continue
                if info.file_size > max_member_bytes:
                    raise ValueError('ZIP 멤버 압축 해제 용량 상한을 초과했습니다')
                if total + info.file_size > max_total_bytes:
                    raise ValueError('ZIP 압축 해제 총 용량 상한을 초과했습니다')
                if info.file_size and (
                    not info.compress_size
                    or info.file_size > info.compress_size * max_compression_ratio
                ):
                    raise ValueError('ZIP 압축률이 안전 상한을 초과했습니다')

                raw, total = _read_zip_member(
                    archive,
                    info,
                    current_total=total,
                    max_member_bytes=max_member_bytes,
                    max_total_bytes=max_total_bytes,
                )
                assets[name] = raw
    except (zipfile.BadZipFile, EOFError, NotImplementedError, zlib.error) as exc:
        raise ValueError('ZIP 파일이 손상되었거나 읽을 수 없습니다') from exc
    return assets


def embed_markdown_images(
    markdown_text: str,
    assets: dict[str, bytes],
    *,
    max_image_references: int = MAX_EMBEDDED_IMAGE_REFERENCES,
    max_embedded_bytes: int = MAX_EMBEDDED_REPORT_BYTES,
) -> tuple[str, list[str], int]:
    """이미지 참조·최종 Markdown 바이트 상한을 확인한 뒤 data URI로 치환한다."""
    if max_image_references < 1 or max_embedded_bytes < 1:
        raise ValueError('임베드 보고서 상한은 1 이상이어야 합니다')

    normalized: dict[str, bytes] = {}
    for name, data in assets.items():
        key = canonical_asset_name(name)
        if key in normalized:
            raise ValueError('중복된 자산 canonical key가 있습니다')
        normalized[key] = data

    final_bytes = _bounded_utf8_byte_count(
        markdown_text,
        maximum=max_embedded_bytes,
        limit_message='임베드 보고서 최종 용량 상한을 초과했습니다',
    )

    warnings: list[str] = []
    prepared_assets: dict[str, tuple[str, bytes]] = {}
    encoded_uris: dict[str, str] = {}
    replacements: dict[tuple[int, int], str] = {}
    embedded = 0
    references = 0

    for match in _IMAGE_RE.finditer(markdown_text):
        references += 1
        if references > max_image_references:
            raise ValueError(f'이미지 참조 수가 {max_image_references}개를 초과했습니다')

        alt = match.group(1)
        raw_target = match.group(2)
        target = raw_target.strip()
        _require_asset_reference_within_limit(target)
        path_token = target
        title_suffix = ''
        title_match = re.match(r"^(?:<([^>]+)>|([^\s]+))(\s+['\"].*['\"])?$", target)
        if title_match:
            path_token = title_match.group(1) or title_match.group(2) or target
            title_suffix = title_match.group(3) or ''
        if re.match(r'^(?:https?://|data:|#)', path_token, flags=re.I):
            continue

        try:
            key = _normalize_key(path_token)
        except ValueError:
            warnings.append(f'안전하지 않은 이미지 자산 경로입니다: {path_token}')
            continue
        selected = key if key in normalized else None
        if not selected:
            warnings.append(f'이미지 자산을 찾지 못했습니다: {path_token}')
            continue

        prepared = prepared_assets.get(selected)
        if prepared is None:
            raw = normalized[selected]
            suffix = PurePosixPath(selected).suffix.lower()
            if suffix == '.svg':
                raw = sanitize_svg(raw.decode('utf-8', errors='strict')).encode('utf-8')
                mime = 'image/svg+xml'
            else:
                mime = mimetypes.guess_type(selected)[0] or 'application/octet-stream'
            prepared = (mime, raw)
            prepared_assets[selected] = prepared

        mime, raw = prepared
        uri_prefix = f'data:{mime};base64,'
        uri_bytes = len(uri_prefix) + 4 * ((len(raw) + 2) // 3)
        alt_bytes = _bounded_utf8_byte_count(
            alt,
            maximum=max_embedded_bytes,
            limit_message='임베드 보고서 최종 용량 상한을 초과했습니다',
        )
        raw_target_bytes = _bounded_utf8_byte_count(
            raw_target,
            maximum=max_embedded_bytes,
            limit_message='임베드 보고서 최종 용량 상한을 초과했습니다',
        )
        title_suffix_bytes = _bounded_utf8_byte_count(
            title_suffix,
            maximum=max_embedded_bytes,
            limit_message='임베드 보고서 최종 용량 상한을 초과했습니다',
        )
        replacement_bytes = alt_bytes + uri_bytes + title_suffix_bytes + len('![]()')
        original_bytes = alt_bytes + raw_target_bytes + len('![]()')
        final_bytes += replacement_bytes - original_bytes
        if final_bytes > max_embedded_bytes:
            raise ValueError('임베드 보고서 최종 용량 상한을 초과했습니다')

        uri = encoded_uris.get(selected)
        if uri is None:
            uri = f'{uri_prefix}{base64.b64encode(raw).decode("ascii")}'
            encoded_uris[selected] = uri
        replacements[(match.start(), match.end())] = f'![{alt}]({uri}{title_suffix})'
        embedded += 1

    def _replace(match: re.Match[str]) -> str:
        return replacements.get((match.start(), match.end()), match.group(0))

    return _IMAGE_RE.sub(_replace, markdown_text), list(dict.fromkeys(warnings)), embedded
