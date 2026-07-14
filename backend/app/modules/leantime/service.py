"""Leantime 동거 스택의 기동 여부를 시간 제한 HTTP 프로브로 감지한다.

SaaS Kit(사용자 제공)의 서비스 정의는 Leantime 을 ``health_url: http://127.0.0.1:8081`` 로
점검하도록 설계돼 있다. 여기서는 두 단계로 판정한다:

1. 짧은 TCP connect 로 포트가 열려 있는지 본다(``absent`` 판정 — 미설치/미구동).
2. 포트가 열려 있으면 시간 제한 HTTP GET 으로 실제 애플리케이션 신원을 본다
   (``starting``/``unhealthy``/``ready`` 판정 — 부팅 중인지, 다른 앱이 점유한 포트인지,
   진짜 Leantime 인지).

- 대상 host/port 는 환경변수 ``AEROONE_LEANTIME_HEALTH_URL`` 로 재정의할 수 있다(운영자가
  다른 포트/호스트에 설치한 경우). 기본값은 킷과 동일한 127.0.0.1:8081.
- ``AEROONE_LEANTIME_LAUNCH_URL`` 로 프런트가 실제로 열 URL 을 별도로 재정의할 수 있다
  (예: 리버스 프록시 뒤에 있어 프로브 대상과 열람 URL 이 다른 경우).
- 프로브는 짧은 timeout 으로 대시보드 로딩을 막지 않는다. 실패는 예외가 아니라
  계약된 ``status`` 값(``absent``/``starting``/``unhealthy``/``error``)으로 정상 표현한다.
- AeroOne 은 Leantime 이 죽어 있어도 절대 실패/블록되지 않는다 — 프로브 함수 전체가
  예외를 밖으로 흘리지 않고 ``status='error'`` 로 낮춰 돌려준다.
"""

from __future__ import annotations

import os
import socket
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlparse

DEFAULT_HEALTH_URL = 'http://127.0.0.1:8081'
DEFAULT_PORT = 8081
_DEFAULT_HEALTH_HOST_PORT = ('127.0.0.1', DEFAULT_PORT)
_TCP_TIMEOUT_SECONDS = 0.6
_HTTP_TIMEOUT_SECONDS = 1.5
_IDENTITY_MARKER = 'leantime'
_BODY_SNIFF_LIMIT = 65536


@dataclass(frozen=True)
class HttpProbeResult:
    """시간 제한 HTTP GET 의 결과 — 신원 판정에 필요한 최소 정보만 담는다."""

    status_code: int
    header_values: tuple[str, ...]
    body_snippet: str
    latency_ms: int


def resolve_target() -> tuple[str, int]:
    """프로브 대상 (host, port) 을 환경변수 우선으로 해석한다.

    ``AEROONE_LEANTIME_HEALTH_URL`` 은 ``http://host:port`` 또는 ``host:port`` 형태를 허용한다.
    파싱에 실패하거나 값이 비면 킷 기본값(127.0.0.1:8081)으로 되돌린다.
    """

    raw = (os.environ.get('AEROONE_LEANTIME_HEALTH_URL') or DEFAULT_HEALTH_URL).strip()
    candidate = raw if '://' in raw else f'http://{raw}'
    try:
        parsed = urlparse(candidate)
        host = parsed.hostname or '127.0.0.1'
        port = parsed.port or DEFAULT_PORT
    except ValueError:
        return '127.0.0.1', DEFAULT_PORT
    return host, port

def _resolve_scheme() -> str:
    """프로브/열람에 쓸 스킴을 env 대상 URL 에서 해석한다(https 명시 시에만 https)."""

    raw = (os.environ.get('AEROONE_LEANTIME_HEALTH_URL') or DEFAULT_HEALTH_URL).strip()
    if '://' not in raw:
        return 'http'
    try:
        scheme = (urlparse(raw).scheme or 'http').lower()
    except ValueError:
        return 'http'
    return 'https' if scheme == 'https' else 'http'


def _resolve_launch_url(host: str, port: int, scheme: str = 'http') -> str:
    """프런트가 실제로 열 URL — 기본은 프로브 대상과 동일(스킴 포함), env 로 재정의 가능."""

    override = (os.environ.get('AEROONE_LEANTIME_LAUNCH_URL') or '').strip()
    if not override:
        return f'{scheme}://{host}:{port}'
    candidate = override if '://' in override else f'http://{override}'
    try:
        parsed = urlparse(candidate)
        if not parsed.hostname:
            return f'http://{host}:{port}'
    except ValueError:
        return f'http://{host}:{port}'
    return candidate


def _tcp_reachable(host: str, port: int, timeout: float = _TCP_TIMEOUT_SECONDS) -> bool:
    """대상 host:port 로 TCP connect 를 시도해 열려 있으면 True.

    미설치/미구동/타임아웃은 모두 False 로 낮춰 돌려준다(예외를 밖으로 흘리지 않는다).
    """

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _http_probe(url: str, timeout: float = _HTTP_TIMEOUT_SECONDS) -> HttpProbeResult | None:
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
            body = exc.read(_BODY_SNIFF_LIMIT)
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
        body = response.read(_BODY_SNIFF_LIMIT)
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


def _identifies_as_leantime(probe: HttpProbeResult) -> bool:
    """응답 헤더 값 또는 본문 스니펫에 'leantime' 이 대소문자 무관 포함돼 있는가."""

    marker = _IDENTITY_MARKER
    if any(marker in value.lower() for value in probe.header_values):
        return True
    return marker in probe.body_snippet.lower()


_KOREAN_DETAIL: dict[str, str] = {
    'ready': 'Leantime 이 정상 구동 중입니다.',
    'unhealthy': 'Leantime 포트가 응답했지만 Leantime 으로 식별되지 않았습니다.',
    'starting': 'Leantime 포트는 열려 있지만 아직 응답이 없습니다(부팅 중일 수 있습니다).',
    'absent': 'Leantime 이 설치되어 있지 않거나 아직 시작되지 않았습니다.',
    'error': 'Leantime 상태를 확인하는 중 예기치 않은 오류가 발생했습니다.',
}


def leantime_status() -> dict[str, object]:
    """프로브 결과를 프런트가 소비할 상태 딕셔너리로 만든다(계약 전체를 항상 채운다).

    이 함수는 절대 예외를 밖으로 흘리지 않는다 — AeroOne 은 Leantime 이 죽어 있어도
    절대 실패/블록되지 않아야 한다.
    """

    try:
        host, port = resolve_target()
        scheme = _resolve_scheme()
        launch_url = _resolve_launch_url(host, port, scheme)
        probe_target = f'{host}:{port}'
        checked_at = datetime.now(UTC).isoformat()

        if not _tcp_reachable(host, port):
            return {
                'status': 'absent',
                'probe_host': host,
                'port': port,
                'probe_target': probe_target,
                'launch_url': launch_url,
                'checked_at': checked_at,
                'latency_ms': None,
                'detail': _KOREAN_DETAIL['absent'],
                'app_identified': False,
            }

        probe = _http_probe(f'{scheme}://{host}:{port}')
        if probe is None:
            return {
                'status': 'starting',
                'probe_host': host,
                'port': port,
                'probe_target': probe_target,
                'launch_url': launch_url,
                'checked_at': checked_at,
                'latency_ms': None,
                'detail': _KOREAN_DETAIL['starting'],
                'app_identified': False,
            }

        app_identified = _identifies_as_leantime(probe)
        auth_gated = probe.status_code in (401, 403)
        responded_ok = 200 <= probe.status_code < 400 or auth_gated
        status = 'ready' if (responded_ok and app_identified) else 'unhealthy'
        return {
            'status': status,
            'probe_host': host,
            'port': port,
            'probe_target': probe_target,
            'launch_url': launch_url,
            'checked_at': checked_at,
            'latency_ms': probe.latency_ms,
            'detail': _KOREAN_DETAIL[status],
            'app_identified': app_identified,
        }
    except Exception:  # noqa: BLE001 - AeroOne 은 Leantime 프로브 실패로 죽지 않는다.
        # 진단 정확도: 오류 payload 도 가능하면 실제로 설정된 대상을 보고한다.
        try:
            host, port = resolve_target()
        except Exception:  # noqa: BLE001 - 대상 해석까지 실패하면 킷 기본값으로 낮춘다.
            host, port = _DEFAULT_HEALTH_HOST_PORT
        try:
            launch_url = _resolve_launch_url(host, port, _resolve_scheme())
        except Exception:  # noqa: BLE001
            launch_url = f'http://{host}:{port}'
        return {
            'status': 'error',
            'probe_host': host,
            'port': port,
            'probe_target': f'{host}:{port}',
            'launch_url': launch_url,
            'checked_at': datetime.now(UTC).isoformat(),
            'latency_ms': None,
            'detail': _KOREAN_DETAIL['error'],
            'app_identified': False,
        }