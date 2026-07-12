"""Leantime 동거 스택의 기동 여부를 TCP 로 감지한다.

SaaS Kit(사용자 제공)의 서비스 정의는 Leantime 을 ``health_url: http://127.0.0.1:8081`` 로
점검하도록 설계돼 있다. 여기서는 그 대상에 짧은 TCP connect 한 번으로 '열려 있는가'만 본다
(HTTP 응답 본문 파싱은 하지 않는다 — 폐쇄망에서 가장 가볍고 빠른 신호).

- 대상 host/port 는 환경변수 ``AEROONE_LEANTIME_HEALTH_URL`` 로 재정의할 수 있다(운영자가
  다른 포트/호스트에 설치한 경우). 기본값은 킷과 동일한 127.0.0.1:8081.
- 프로브는 짧은 timeout 으로 대시보드 로딩을 막지 않는다. 실패(미설치/미구동)는 예외가 아니라
  ``status='down'`` 으로 정상 표현한다.
"""

from __future__ import annotations

import os
import socket
from urllib.parse import urlparse

DEFAULT_HEALTH_URL = 'http://127.0.0.1:8081'
DEFAULT_PORT = 8081
_PROBE_TIMEOUT_SECONDS = 0.6


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


def probe_leantime(timeout: float = _PROBE_TIMEOUT_SECONDS) -> bool:
    """대상 host:port 로 TCP connect 를 시도해 열려 있으면 True.

    미설치/미구동/타임아웃은 모두 False 로 낮춰 돌려준다(예외를 밖으로 흘리지 않는다).
    """

    host, port = resolve_target()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def leantime_status() -> dict[str, object]:
    """프로브 결과를 프런트가 소비할 상태 딕셔너리로 만든다."""

    host, port = resolve_target()
    running = probe_leantime()
    return {
        'status': 'up' if running else 'down',
        'probe_host': host,
        'port': port,
        'probe_target': f'{host}:{port}',
    }
