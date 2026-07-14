"""Dependency-free bounds and ZIP preflight helpers shared by Office uploads."""

from __future__ import annotations

import stat
import struct
from collections.abc import Callable
from dataclasses import dataclass
from typing import BinaryIO

OFFICE_STREAM_CHUNK_BYTES = 64 * 1024
MAX_ZIP_CENTRAL_DIRECTORY_BYTES = 2 * 1024 * 1024
MAX_REPORT_ASSET_TOTAL_BYTES = 50 * 1024 * 1024
SUPPORTED_ZIP_COMPRESSION_METHODS = frozenset({0, 8})


class UploadSizeLimitExceeded(ValueError):
    """An Office upload exceeded a byte limit while being streamed."""


@dataclass(frozen=True)
class ZipMemberPreflight:
    """Validated central-directory metadata for one ZIP member."""

    filename: str
    canonical_name: str
    is_directory: bool


@dataclass(frozen=True)
class ZipPreflight:
    """Validated ZIP central-directory members."""

    members: tuple[ZipMemberPreflight, ...]


def bounded_decimal(value: bytes, *, maximum: int) -> int:
    """Parse an ASCII decimal only after proving it fits ``maximum``.

    Comparing normalized decimal text avoids constructing arbitrarily large
    Python integers from untrusted request headers.
    """
    if maximum < 0:
        raise ValueError('decimal maximum must not be negative')
    if not value or any(character < 0x30 or character > 0x39 for character in value):
        raise ValueError('invalid decimal value')

    normalized = value.lstrip(b'0') or b'0'
    maximum_text = str(maximum).encode('ascii')
    if len(normalized) > len(maximum_text) or (
        len(normalized) == len(maximum_text) and normalized > maximum_text
    ):
        raise OverflowError('decimal value exceeds its maximum')
    return int(normalized)


def _read_at(source: BinaryIO, offset: int, size: int) -> bytes:
    source.seek(offset)
    data = source.read(size)
    if len(data) != size:
        raise ValueError('ZIP 파일이 손상되었거나 읽을 수 없습니다')
    return data


def require_utf8_filename_within_limit(
    name: str,
    max_filename_bytes: int,
    *,
    limit_message: str,
    invalid_limit_message: str = 'ZIP 파일명 바이트 상한은 1 이상이어야 합니다',
    non_utf8_message: str = 'ZIP 파일명이 UTF-8로 표현될 수 없습니다',
) -> None:
    """Require a filename's UTF-8 representation to fit its byte limit."""
    if max_filename_bytes < 1:
        raise ValueError(invalid_limit_message)
    filename_bytes = 0
    try:
        for index, character in enumerate(name):
            code_point = ord(character)
            if 0xD800 <= code_point <= 0xDFFF:
                raise UnicodeEncodeError(
                    'utf-8',
                    name,
                    index,
                    index + 1,
                    'surrogates not allowed',
                )
            if code_point < 0x80:
                filename_bytes += 1
            elif code_point < 0x800:
                filename_bytes += 2
            elif code_point < 0x10000:
                filename_bytes += 3
            else:
                filename_bytes += 4
            if filename_bytes > max_filename_bytes:
                raise ValueError(limit_message)
    except UnicodeEncodeError as exc:
        raise ValueError(non_utf8_message) from exc


def _preflight_central_directory(
    source: BinaryIO,
    *,
    central_directory_start: int,
    central_directory_end: int,
    total_entries: int,
    max_filename_bytes: int,
    canonicalize_filename: Callable[[str], str],
    filename_limit_message: str,
) -> tuple[ZipMemberPreflight, ...]:
    """Validate names, disk layout, and symlinks before ``ZipFile`` creation."""
    members: list[ZipMemberPreflight] = []
    offset = central_directory_start
    for _ in range(total_entries):
        header = _read_at(source, offset, 46)
        (
            signature,
            _,
            _,
            flag_bits,
            compression_method,
            _,
            _,
            _,
            _,
            _,
            filename_size,
            extra_size,
            comment_size,
            disk_start,
            _,
            external_attr,
            _,
        ) = struct.unpack('<4s6H3I5H2I', header)
        if signature != b'PK\x01\x02':
            raise ValueError('ZIP 파일이 손상되었거나 읽을 수 없습니다')
        if disk_start != 0:
            raise ValueError('다중 디스크 ZIP은 지원하지 않습니다')

        next_offset = offset + 46 + filename_size + extra_size + comment_size
        if next_offset > central_directory_end:
            raise ValueError('ZIP 파일이 손상되었거나 읽을 수 없습니다')
        if filename_size > max_filename_bytes:
            raise ValueError(filename_limit_message)
        raw_filename = _read_at(source, offset + 46, filename_size)
        if b'\x00' in raw_filename:
            raise ValueError('ZIP 에 안전하지 않은 경로가 있습니다')
        try:
            encoding = 'utf-8' if flag_bits & 0x800 else 'cp437'
            filename = raw_filename.decode(encoding)
        except UnicodeDecodeError as exc:
            raise ValueError('ZIP 파일이 손상되었거나 읽을 수 없습니다') from exc
        if flag_bits & 0x1:
            raise ValueError('암호화된 ZIP 멤버는 지원하지 않습니다')
        if compression_method not in SUPPORTED_ZIP_COMPRESSION_METHODS:
            raise ValueError('지원하지 않는 ZIP 압축 방식입니다')
        if stat.S_ISLNK(external_attr >> 16):
            raise ValueError('ZIP 에 심볼릭 링크가 포함되어 있습니다')

        canonical_name = canonicalize_filename(filename)
        if not canonical_name or canonical_name == '.':
            raise ValueError('ZIP 에 안전하지 않은 경로가 있습니다')
        require_utf8_filename_within_limit(
            canonical_name,
            max_filename_bytes,
            limit_message=filename_limit_message,
        )
        members.append(
            ZipMemberPreflight(
                filename=filename,
                canonical_name=canonical_name,
                is_directory=filename.endswith('/'),
            )
        )
        offset = next_offset

    if offset != central_directory_end:
        raise ValueError('지원하지 않는 ZIP 중앙 디렉터리 형식입니다')
    return tuple(members)


def preflight_zip_central_directory(
    source: BinaryIO,
    *,
    max_files: int,
    max_compressed_bytes: int,
    max_filename_bytes: int,
    max_central_directory_bytes: int,
    canonicalize_filename: Callable[[str], str],
    filename_limit_message: str,
) -> ZipPreflight:
    """Validate ZIP/ZIP64 central metadata before constructing ``ZipFile``."""
    source.seek(0, 2)
    source_size = source.tell()
    if source_size > max_compressed_bytes:
        raise UploadSizeLimitExceeded('ZIP 압축 업로드 총 용량 상한을 초과했습니다')
    if source_size < 22:
        raise ValueError('ZIP 파일이 손상되었거나 읽을 수 없습니다')

    tail_size = min(source_size, 22 + 65_535)
    tail_offset = source_size - tail_size
    tail = _read_at(source, tail_offset, tail_size)
    eocd_index = tail.rfind(b'PK\x05\x06')
    while eocd_index >= 0:
        if eocd_index + 22 <= tail_size:
            comment_size = struct.unpack_from('<H', tail, eocd_index + 20)[0]
            if eocd_index + 22 + comment_size == tail_size:
                break
        eocd_index = tail.rfind(b'PK\x05\x06', 0, eocd_index)
    if eocd_index < 0:
        raise ValueError('ZIP 파일이 손상되었거나 읽을 수 없습니다')

    eocd_offset = tail_offset + eocd_index
    (
        _,
        disk_number,
        central_directory_disk,
        entries_on_disk,
        total_entries,
        central_directory_size,
        central_directory_offset,
        _,
    ) = struct.unpack_from('<4sHHHHIIH', tail, eocd_index)
    requires_zip64 = (
        total_entries == 0xFFFF
        or central_directory_size == 0xFFFFFFFF
        or central_directory_offset == 0xFFFFFFFF
    )

    if requires_zip64:
        if disk_number not in (0, 0xFFFF) or central_directory_disk not in (0, 0xFFFF):
            raise ValueError('다중 디스크 ZIP은 지원하지 않습니다')
        if eocd_offset < 20:
            raise ValueError('지원하지 않는 ZIP64 형식입니다')
        locator_offset = eocd_offset - 20
        locator = _read_at(source, locator_offset, 20)
        signature, zip64_disk, zip64_offset, zip64_disks = struct.unpack('<4sIQI', locator)
        if signature != b'PK\x06\x07':
            raise ValueError('지원하지 않는 ZIP64 형식입니다')
        if zip64_disk != 0 or zip64_disks != 1:
            raise ValueError('다중 디스크 ZIP은 지원하지 않습니다')
        if zip64_offset > locator_offset - 56:
            raise ValueError('지원하지 않는 ZIP64 형식입니다')

        header = _read_at(source, zip64_offset, 56)
        signature, record_size = struct.unpack_from('<4sQ', header)
        if signature != b'PK\x06\x06' or record_size < 44:
            raise ValueError('지원하지 않는 ZIP64 형식입니다')
        if zip64_offset + 12 + record_size > eocd_offset - 20:
            raise ValueError('지원하지 않는 ZIP64 형식입니다')
        (
            _,
            _,
            zip64_disk_number,
            zip64_central_directory_disk,
            zip64_entries_on_disk,
            total_entries,
            central_directory_size,
            central_directory_offset,
        ) = struct.unpack_from('<HHIIQQQQ', header, 12)
        if (
            zip64_disk_number != 0
            or zip64_central_directory_disk != 0
            or zip64_entries_on_disk != total_entries
        ):
            raise ValueError('다중 디스크 ZIP은 지원하지 않습니다')
        central_directory_end = zip64_offset
    else:
        if (
            disk_number != 0
            or central_directory_disk != 0
            or entries_on_disk != total_entries
        ):
            raise ValueError('다중 디스크 ZIP은 지원하지 않습니다')
        central_directory_end = eocd_offset

    if total_entries > max_files:
        raise ValueError(f'ZIP 안 파일 수가 {max_files}개를 초과했습니다')
    if central_directory_size > max_central_directory_bytes:
        raise ValueError('ZIP 중앙 디렉터리 용량 상한을 초과했습니다')
    if central_directory_size < total_entries * 46:
        raise ValueError('ZIP 파일이 손상되었거나 읽을 수 없습니다')

    prefix_size = central_directory_end - central_directory_size - central_directory_offset
    central_directory_start = central_directory_offset + prefix_size
    if prefix_size < 0 or central_directory_start < 0:
        raise ValueError('ZIP 파일이 손상되었거나 읽을 수 없습니다')
    if central_directory_start + central_directory_size != central_directory_end:
        raise ValueError('ZIP 파일이 손상되었거나 읽을 수 없습니다')

    members = _preflight_central_directory(
        source,
        central_directory_start=central_directory_start,
        central_directory_end=central_directory_end,
        total_entries=total_entries,
        max_filename_bytes=max_filename_bytes,
        canonicalize_filename=canonicalize_filename,
        filename_limit_message=filename_limit_message,
    )
    source.seek(0)
    return ZipPreflight(members)
