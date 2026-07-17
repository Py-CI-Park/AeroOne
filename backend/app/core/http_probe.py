"""공유 TCP/HTTP 프로브 프리미티브.

동거 스택(Leantime, Open Notebook, Open WebUI 등)이 공통으로 쓰는 시간 제한 도달성 검사.
호출부는 이 모듈을 조합해 자신만의 상태 판정(신원 마커 필요 여부 등)을 얹는다. 이 모듈
자체는 절대 예외를 밖으로 흘리지 않는다 — 실패는 ``False``/``None`` 으로 낮춰 돌려준다.
"""

from __future__ import annotations

import socket
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime

DEFAULT_TCP_TIMEOUT_SECONDS = 0.6
DEFAULT_HTTP_TIMEOUT_SECONDS = 1.5
BODY_SNIFF_LIMIT = 65536


@dataclass(frozen=True)
class HttpProbeResult:
    """시간 제한 HTTP GET 의 결과 — 신원 판정에 필요한 최소 정보만 담는다."""

    status_code: int
    header_values: tuple[str, ...]
    body_snippet: str
    latency_ms: int


def tcp_reachable(host: str, port: int, timeout: float = DEFAULT_TCP_TIMEOUT_SECONDS) -> bool:
    """대상 host:port 로 TCP connect 를 시도해 열려 있으면 True.

    미설치/미구동/타임아웃은 모두 False 로 낮춰 돌려준다(예외를 밖으로 흘리지 않는다).
    """

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def http_probe(url: str, timeout: float = DEFAULT_HTTP_TIMEOUT_SECONDS) -> HttpProbeResult | None:
    """시간 제한 HTTP GET. 타임아웃/리셋/5xx 등 '부팅 중' 신호는 None 을 돌려준다.

    반환값이 있으면(2xx/3xx/4xx 등 실제 응답을 받았으면) 신원 판정을 위한 헤더/본문
    스니펫을 담아 돌려준다. 예외는 밖으로 흘리지 않는다.
    """

    started = datetime.now(UTC)
    request = urllib.request.Request(url, method='GET')
    # https 대상은 폐쇄망 자체서명 인증서가 흔하므로 라이브니스 프로브에 한해 검증을 생략한다
    # (데이터 채널이 아니라 신원 마커만 보는 liveness 확인이다).
    context = ssl._create_unverified_context() if url.lower().startswith('https://') else None
    try:
        response = urllib.request.urlopen(request, timeout=timeout, context=context)  # noqa: S310 - 로컬/사설 대상 폴링
    except urllib.error.HTTPError as exc:
        # 4xx/5xx 도 '응답은 받았다' — 5xx 는 starting 취급을 위해 호출부에서 구분한다.
        latency_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
        if exc.code >= 500:
            return None
        try:
            body = exc.read(BODY_SNIFF_LIMIT)
        except OSError:
            body = b''
        header_values = tuple(str(v) for v in exc.headers.values()) if exc.headers else ()
        return HttpProbeResult(
            status_code=exc.code,
            header_values=header_values,
            body_snippet=body.decode('utf-8', errors='ignore'),
            latency_ms=latency_ms,
        )
    except (urllib.error.URLError, OSError, ValueError):
        # 타임아웃, 연결 리셋, 잘못된 URL 등 — 모두 '아직 부팅 중'으로 취급.
        return None

    latency_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
    try:
        body = response.read(BODY_SNIFF_LIMIT)
    except OSError:
        body = b''
    finally:
        response.close()
    header_values = tuple(str(v) for v in response.headers.values()) if response.headers else ()
    return HttpProbeResult(
        status_code=response.status,
        header_values=header_values,
        body_snippet=body.decode('utf-8', errors='ignore'),
        latency_ms=latency_ms,
    )
