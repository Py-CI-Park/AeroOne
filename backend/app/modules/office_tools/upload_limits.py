"""Office upload ingress limits applied before FastAPI form parsing.

Configured Office upload paths are consumed into a bounded replay buffer before
Starlette sees a request body.  This keeps raw-byte, multipart file-count, and
per-file limits ahead of Starlette's multipart spooling for both fixed-length
and chunked requests.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from tempfile import SpooledTemporaryFile
from typing import Awaitable, Callable

from python_multipart.multipart import parse_options_header

from app.modules.office_tools.limits import OFFICE_STREAM_CHUNK_BYTES, bounded_decimal
from app.modules.office_tools.schemas import MAX_CHART_UPLOAD_BYTES, MAX_REPORT_UPLOAD_BYTES

_ASGIApp = Callable[[dict, Callable[[], Awaitable[dict]], Callable[[dict], Awaitable[None]]], Awaitable[None]]
_MAX_PART_HEADER_BYTES = 16 * 1024
_REPLAY_MEMORY_BYTES = 1024 * 1024
_REPLAY_CHUNK_BYTES = OFFICE_STREAM_CHUNK_BYTES
_COUNTER_SLICE_BYTES = OFFICE_STREAM_CHUNK_BYTES
_BOUNDARY_CHARS = frozenset(b"0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'()+_,-./:=? ")

# Multipart framing and small form fields need room in addition to the file byte
# limit.  The separate per-file limit still keeps the chart source at 20 MiB.
_CHART_MULTIPART_OVERHEAD_BYTES = 256 * 1024
_REPORT_MULTIPART_OVERHEAD_BYTES = 512 * 1024


@dataclass(frozen=True)
class OfficeMultipartLimits:
    """Raw multipart bounds for one Office endpoint."""

    max_total_bytes: int
    max_file_bytes: int
    max_files: int

    def __post_init__(self) -> None:
        if self.max_total_bytes < 1 or self.max_file_bytes < 1 or self.max_files < 1:
            raise ValueError('Office multipart limits must be positive')


CHART_MULTIPART_LIMITS = OfficeMultipartLimits(
    max_total_bytes=MAX_CHART_UPLOAD_BYTES + _CHART_MULTIPART_OVERHEAD_BYTES,
    max_file_bytes=MAX_CHART_UPLOAD_BYTES,
    max_files=1,
)
REPORT_MULTIPART_LIMITS = OfficeMultipartLimits(
    max_total_bytes=MAX_REPORT_UPLOAD_BYTES + (50 * 1024 * 1024) + _REPORT_MULTIPART_OVERHEAD_BYTES,
    max_file_bytes=MAX_REPORT_UPLOAD_BYTES,
    max_files=201,
)


class OfficeMultipartLimitExceeded(Exception):
    """A raw multipart request crossed an ingress boundary."""


class _MalformedOfficeUpload(Exception):
    """The request cannot safely reach FastAPI's form parser."""


class _MultipartFileCounter:
    """Bounded multipart state machine that only retains delimiter/header tails."""

    def __init__(self, boundary: bytes, limits: OfficeMultipartLimits) -> None:
        self._initial_boundary = b'--' + boundary
        self._part_boundary = b'\r\n--' + boundary
        self._limits = limits
        self._buffer = bytearray()
        self._state = 'preamble'
        self._part_is_file = False
        self._file_bytes = 0
        self._file_count = 0

    def feed(self, body: bytes | memoryview) -> None:
        if self._state == 'done' or not body:
            return
        self._buffer.extend(body)
        while self._state != 'done':
            previous_state = self._state
            previous_length = len(self._buffer)
            if self._state == 'preamble':
                self._consume_preamble()
            elif self._state == 'headers':
                self._consume_headers()
            elif self._state == 'body':
                self._consume_body()
            else:  # Defensive: a state typo must never weaken ingress limits.
                raise RuntimeError(f'unknown multipart state: {self._state}')

            if (self._state, len(self._buffer)) == (previous_state, previous_length):
                return

    def finish(self) -> None:
        """Reject an incomplete multipart body after accounting for its file tail."""
        if self._state == 'body' and self._buffer:
            self._consume_file_bytes(len(self._buffer))
            self._buffer.clear()
        if self._state != 'done':
            raise _MalformedOfficeUpload('잘못된 multipart 경계입니다')

    def _consume_preamble(self) -> None:
        needed = len(self._initial_boundary) + 2
        if len(self._buffer) < needed:
            return
        if not self._buffer.startswith(self._initial_boundary):
            raise _MalformedOfficeUpload('잘못된 multipart 경계입니다')
        suffix = bytes(self._buffer[len(self._initial_boundary):needed])
        del self._buffer[:needed]
        if suffix == b'--':
            self._state = 'done'
        elif suffix == b'\r\n':
            self._state = 'headers'
        else:
            raise _MalformedOfficeUpload('잘못된 multipart 경계입니다')

    def _consume_headers(self) -> None:
        marker_index = self._buffer.find(b'\r\n\r\n')
        if marker_index < 0:
            if len(self._buffer) > _MAX_PART_HEADER_BYTES:
                raise OfficeMultipartLimitExceeded('multipart 파트 헤더가 허용 크기를 초과했습니다')
            return

        header_bytes = bytes(self._buffer[:marker_index])
        del self._buffer[:marker_index + 4]
        self._part_is_file = self._headers_describe_file(header_bytes)
        self._file_bytes = 0
        if self._part_is_file:
            self._file_count += 1
            if self._file_count > self._limits.max_files:
                raise OfficeMultipartLimitExceeded('업로드 파일 수가 허용 상한을 초과했습니다')
        self._state = 'body'

    def _consume_body(self) -> None:
        marker_index = self._buffer.find(self._part_boundary)
        if marker_index >= 0:
            boundary_end = marker_index + len(self._part_boundary)
            if len(self._buffer) < boundary_end + 2:
                return
            suffix = bytes(self._buffer[boundary_end:boundary_end + 2])
            if suffix == b'--':
                self._consume_file_bytes(marker_index)
                del self._buffer[:boundary_end + 2]
                self._state = 'done'
                return
            if suffix == b'\r\n':
                self._consume_file_bytes(marker_index)
                del self._buffer[:boundary_end + 2]
                self._part_is_file = False
                self._file_bytes = 0
                self._state = 'headers'
                return
            # A file may legitimately contain a delimiter prefix not followed by
            # a delimiter suffix. Consume its leading CR and continue scanning.
            self._consume_file_bytes(marker_index + 1)
            del self._buffer[:marker_index + 1]
            return

        preserved_tail = len(self._part_boundary) - 1
        safe_length = len(self._buffer) - preserved_tail
        if safe_length > 0:
            self._consume_file_bytes(safe_length)
            del self._buffer[:safe_length]

    def _consume_file_bytes(self, count: int) -> None:
        if not self._part_is_file or count == 0:
            return
        self._file_bytes += count
        if self._file_bytes > self._limits.max_file_bytes:
            raise OfficeMultipartLimitExceeded('업로드 파일이 허용 크기를 초과했습니다')

    @staticmethod
    def _headers_describe_file(header_bytes: bytes) -> bool:
        content_disposition: bytes | None = None
        for line in header_bytes.split(b'\r\n'):
            name, separator, value = line.partition(b':')
            if not separator or not name.strip():
                raise _MalformedOfficeUpload('잘못된 multipart 파트 헤더입니다')
            if name.strip().lower() == b'content-disposition':
                content_disposition = value.strip()

        if content_disposition is None:
            return False
        try:
            _, options = parse_options_header(content_disposition)
        except (IndexError, TypeError, UnicodeError, ValueError) as exc:
            raise _MalformedOfficeUpload('잘못된 Content-Disposition 헤더입니다') from exc
        return any(
            parameter == b'filename' or parameter.startswith(b'filename*')
            for parameter in options
        )


def _header(scope: dict, name: bytes) -> bytes | None:
    for key, value in scope.get('headers', []):
        if key.lower() == name:
            return value
    return None


def _parse_content_type(content_type: bytes | None) -> tuple[bytes, dict[bytes, bytes]]:
    try:
        media_type, parameters = parse_options_header(content_type)
    except (IndexError, TypeError, UnicodeError, ValueError) as exc:
        raise _MalformedOfficeUpload('잘못된 Content-Type 헤더입니다') from exc
    return media_type.lower(), parameters


def _is_valid_boundary(boundary: bytes | None) -> bool:
    return bool(
        boundary
        and len(boundary) <= 70
        and boundary[-1] != 0x20
        and all(character in _BOUNDARY_CHARS for character in boundary)
    )


class OfficeMultipartIngressLimitMiddleware:
    """Bound Office request bodies before FastAPI can materialize form data."""

    def __init__(
        self,
        app: _ASGIApp,
        *,
        limits_by_path: dict[str, OfficeMultipartLimits],
    ) -> None:
        self.app = app
        self._limits_by_path = dict(limits_by_path)

    async def __call__(
        self,
        scope: dict,
        receive: Callable[[], Awaitable[dict]],
        send: Callable[[dict], Awaitable[None]],
    ) -> None:
        if scope.get('type') != 'http' or scope.get('method') != 'POST':
            await self.app(scope, receive, send)
            return

        limits = self._limits_by_path.get(scope.get('path', ''))
        if limits is None:
            await self.app(scope, receive, send)
            return

        content_length = _header(scope, b'content-length')
        if content_length is not None:
            length_value = content_length.strip()
            try:
                bounded_decimal(length_value, maximum=limits.max_total_bytes)
            except ValueError:
                await self._send_error_response(send, 400, '잘못된 Content-Length 헤더입니다')
                return
            except OverflowError:
                await self._send_limit_response(send, '업로드 전체 크기가 허용 상한을 초과했습니다')
                return

        content_type = _header(scope, b'content-type')
        counter: _MultipartFileCounter | None = None
        media_type = b''
        content_type_error: _MalformedOfficeUpload | None = None
        try:
            media_type, parameters = _parse_content_type(content_type)
            if media_type == b'multipart/form-data':
                boundary = parameters.get(b'boundary')
                if not _is_valid_boundary(boundary):
                    content_type_error = _MalformedOfficeUpload('잘못된 multipart 경계입니다')
                else:
                    counter = _MultipartFileCounter(boundary, limits)
        except _MalformedOfficeUpload as exc:
            content_type_error = exc

        try:
            replay, body_length = await self._buffer_request_body(receive, limits, counter)
        except OfficeMultipartLimitExceeded as exc:
            await self._send_limit_response(send, str(exc))
            return
        except _MalformedOfficeUpload as exc:
            await self._send_error_response(send, 400, str(exc))
            return

        try:
            if content_type_error is not None:
                await self._send_error_response(send, 400, str(content_type_error))
                return
            if media_type != b'multipart/form-data':
                await self._send_error_response(send, 415, 'multipart/form-data 요청만 지원합니다')
                return
            await self.app(scope, self._replay_receive(replay, body_length), send)
        finally:
            replay.close()

    @staticmethod
    async def _buffer_request_body(
        receive: Callable[[], Awaitable[dict]],
        limits: OfficeMultipartLimits,
        counter: _MultipartFileCounter | None,
    ) -> tuple[SpooledTemporaryFile, int]:
        replay = SpooledTemporaryFile(max_size=_REPLAY_MEMORY_BYTES, mode='w+b')
        received_total = 0
        try:
            while True:
                message = await receive()
                if message.get('type') != 'http.request':
                    raise _MalformedOfficeUpload('업로드 요청 본문이 중단되었습니다')
                body = message.get('body', b'')
                if not isinstance(body, bytes):
                    raise _MalformedOfficeUpload('잘못된 업로드 요청 본문입니다')
                received_total += len(body)
                if received_total > limits.max_total_bytes:
                    raise OfficeMultipartLimitExceeded(
                        '업로드 전체 크기가 허용 상한을 초과했습니다'
                    )
                frame = memoryview(body)
                for offset in range(0, len(frame), _COUNTER_SLICE_BYTES):
                    chunk = frame[offset:offset + _COUNTER_SLICE_BYTES]
                    if counter is not None:
                        counter.feed(chunk)
                    replay.write(chunk)
                if not message.get('more_body', False):
                    if counter is not None:
                        counter.finish()
                    replay.seek(0)
                    return replay, received_total
        except BaseException:
            replay.close()
            raise

    @staticmethod
    def _replay_receive(
        replay: SpooledTemporaryFile,
        body_length: int,
    ) -> Callable[[], Awaitable[dict]]:
        remaining = body_length

        async def receive() -> dict:
            nonlocal remaining
            if remaining == 0:
                return {'type': 'http.request', 'body': b'', 'more_body': False}
            body = replay.read(min(_REPLAY_CHUNK_BYTES, remaining))
            remaining -= len(body)
            if not body and remaining:
                raise RuntimeError('ingress replay body ended unexpectedly')
            return {'type': 'http.request', 'body': body, 'more_body': remaining > 0}

        return receive

    @staticmethod
    async def _send_limit_response(
        send: Callable[[dict], Awaitable[None]],
        detail: str,
    ) -> None:
        await OfficeMultipartIngressLimitMiddleware._send_error_response(send, 413, detail)

    @staticmethod
    async def _send_error_response(
        send: Callable[[dict], Awaitable[None]],
        status: int,
        detail: str,
    ) -> None:
        body = json.dumps({'detail': detail}, ensure_ascii=False).encode('utf-8')
        await send(
            {
                'type': 'http.response.start',
                'status': status,
                'headers': [
                    (b'content-type', b'application/json; charset=utf-8'),
                    (b'content-length', str(len(body)).encode('ascii')),
                ],
            }
        )
        await send({'type': 'http.response.body', 'body': body})
