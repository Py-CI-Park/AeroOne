"""외부 앱 런처 카드(Open Notebook/Open WebUI)의 기동 여부를 시간 제한 프로브로 감지한다.

Leantime 동거 스택 프로브(``app.core.http_probe``)를 그대로 재사용한다. Leantime 과 달리
이 런처들은 신원 마커 검사를 요구하지 않는다 — 대상 포트가 무엇이든 서비스를 올리는
애플리케이션이라고 가정하고, HTTP 응답이 오면(2xx~4xx) 곧바로 ``ready`` 로 판정한다.

폐쇄망 순도: 프로브 대상은 항상 loopback(``127.0.0.1``)이다. 포트는 ``Settings`` 의
``open_notebook_port``/``open_webui_port`` (env 로 재정의 가능)로만 해석하며, 원격 호스트를
가리키도록 구성할 방법을 두지 않는다 — 프런트가 실제로 여는 URL 은 브라우저 호스트 기준으로
별도 계산되므로(``ExternalLauncherCard``) 여기서는 상태만 보고한다.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.config import get_settings
from app.core.http_probe import http_probe as _http_probe, tcp_reachable as _tcp_reachable

PROBE_HOST = '127.0.0.1'

_LABELS: dict[str, str] = {
    'open_notebook': 'Open Notebook',
    'open_webui': 'OpenWebUI',
}

_PORT_SETTINGS_FIELD: dict[str, str] = {
    'open_notebook': 'open_notebook_port',
    'open_webui': 'open_webui_port',
}


class UnknownLauncherKindError(KeyError):
    """등록되지 않은 launcher kind — 라우터에서 404 로 변환한다."""


def known_kinds() -> tuple[str, ...]:
    return tuple(_LABELS.keys())


def resolve_port(kind: str) -> int:
    """kind 에 대응하는 포트를 settings 에서 해석한다(env 재정의 가능). 미등록 kind 는 예외."""

    field = _PORT_SETTINGS_FIELD.get(kind)
    if field is None:
        raise UnknownLauncherKindError(kind)
    return int(getattr(get_settings(), field))


def _detail(kind: str, status: str) -> str:
    label = _LABELS[kind]
    return {
        'ready': f'{label} 이 정상 구동 중입니다.',
        'starting': f'{label} 포트는 열려 있지만 아직 응답이 없습니다(부팅 중일 수 있습니다).',
        'absent': f'{label} 이 설치되어 있지 않거나 아직 시작되지 않았습니다.',
        'error': f'{label} 상태를 확인하는 중 예기치 않은 오류가 발생했습니다.',
    }[status]


def launcher_status(kind: str) -> dict[str, object]:
    """프로브 결과를 프런트가 소비할 상태 딕셔너리로 만든다(계약 전체를 항상 채운다).

    미등록 kind 는 ``UnknownLauncherKindError`` 를 그대로 전파한다(라우터가 404 로 변환).
    그 외 프로브/설정 처리 중 예기치 않은 오류는 절대 밖으로 흘리지 않는다 — AeroOne 은
    외부 런처가 죽어 있어도 절대 실패/블록되지 않아야 한다.
    """

    if kind not in _LABELS:
        raise UnknownLauncherKindError(kind)

    try:
        port = resolve_port(kind)
        probe_target = f'{PROBE_HOST}:{port}'
        checked_at = datetime.now(UTC).isoformat()

        if not _tcp_reachable(PROBE_HOST, port):
            return {
                'status': 'absent',
                'port': port,
                'probe_target': probe_target,
                'checked_at': checked_at,
                'latency_ms': None,
                'detail': _detail(kind, 'absent'),
            }

        probe = _http_probe(f'http://{PROBE_HOST}:{port}')
        if probe is None:
            return {
                'status': 'starting',
                'port': port,
                'probe_target': probe_target,
                'checked_at': checked_at,
                'latency_ms': None,
                'detail': _detail(kind, 'starting'),
            }

        # 신원 마커는 옵션 — 대상 포트에서 어떤 HTTP 응답이든 오면 곧바로 ready 로 판정한다.
        return {
            'status': 'ready',
            'port': port,
            'probe_target': probe_target,
            'checked_at': checked_at,
            'latency_ms': probe.latency_ms,
            'detail': _detail(kind, 'ready'),
        }
    except Exception:  # noqa: BLE001 - AeroOne 은 런처 프로브 실패로 죽지 않는다.
        try:
            port = resolve_port(kind)
        except Exception:  # noqa: BLE001 - 대상 해석까지 실패하면 0 으로 낮춘다.
            port = 0
        return {
            'status': 'error',
            'port': port,
            'probe_target': f'{PROBE_HOST}:{port}',
            'checked_at': datetime.now(UTC).isoformat(),
            'latency_ms': None,
            'detail': _detail(kind, 'error'),
        }
