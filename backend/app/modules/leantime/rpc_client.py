"""Leantime JSON-RPC 2.0 읽기 전용 어댑터.

공식 API 경계(``{base_url}/api/jsonrpc``)만 사용하고 Leantime DB/세션에는 절대 접근하지
않는다. 호출 가능한 메서드는 :data:`ALLOWLIST` 로 제한되며, 목록에 없는 메서드는 네트워크
호출 전에 ``ValueError`` 로 거부한다. 스코프 API 키는 ``x-api-key`` 헤더로만 전송하고
URL/쿼리스트링·응답·예외 메시지 어디에도 노출하지 않는다.

전송 계층은 ``_post_jsonrpc`` 모듈 함수 하나로 좁혀 두어 테스트에서 monkeypatch 로 실제
네트워크를 대체할 수 있게 한다(``OpenAiCompatibleClient`` 와 동일하게 stdlib ``urllib`` 만
쓰고 신규 의존성을 도입하지 않는다).
"""

from __future__ import annotations

import json
import ssl
from typing import Any
from urllib import error, request

DEFAULT_TIMEOUT_SECONDS = 8.0

# 읽기 전용으로 허용하는 JSON-RPC 메서드만 나열한다 — 그 외 메서드는 호출 자체를 거부한다.
ALLOWLIST: frozenset[str] = frozenset(
    {
        'leantime.rpc.projects.getAll',
        'leantime.rpc.tickets.getAll',
        'leantime.rpc.calendar.getAll',
    }
)


class LeantimeUnavailable(RuntimeError):
    """타임아웃/연결 실패/5xx — Leantime 이 응답하지 못하는 상태."""


class LeantimeAuthError(RuntimeError):
    """401/403 — 스코프 API 키가 거부됨."""


class LeantimeRpcError(RuntimeError):
    """JSON-RPC 응답에 ``error`` 객체가 포함됨."""


class LeantimeProtocolError(RuntimeError):
    """응답이 JSON-RPC 2.0 계약을 따르지 않는 등 형식이 깨짐."""


def _post_jsonrpc(
    url: str,
    payload: dict[str, Any],
    *,
    api_key: str,
    timeout: float,
    verify_tls: bool,
) -> dict:
    """실제 HTTP POST 전송 — 테스트에서 monkeypatch 하는 유일한 진입점.

    API 키는 헤더로만 보내고, URL 은 쿼리스트링을 절대 포함하지 않는다.
    """

    body = json.dumps(payload).encode('utf-8')
    headers = {'Content-Type': 'application/json'}
    if api_key:
        headers['x-api-key'] = api_key
    req = request.Request(url, data=body, headers=headers, method='POST')
    context = None if verify_tls else ssl._create_unverified_context()
    with request.urlopen(req, timeout=timeout, context=context) as response:  # noqa: S310 - 등록된 내부망 대상만 호출
        raw = response.read().decode('utf-8')
    return json.loads(raw)


def _normalize_str(value: Any, default: str = '') -> str:
    if value is None:
        return default
    return str(value)


def _normalize_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


class LeantimeRpcClient:
    """등록된 단일 Leantime 연결에 대한 읽기 전용 JSON-RPC 클라이언트."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        verify_tls: bool = True,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key or ''
        self.verify_tls = verify_tls
        self.timeout = timeout

    def _endpoint(self) -> str:
        return f'{self.base_url}/api/jsonrpc'

    def _call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        if method not in ALLOWLIST:
            raise ValueError(f'method not in read-only allowlist: {method!r}')

        payload = {
            'jsonrpc': '2.0',
            'method': method,
            'params': params or {},
            'id': 1,
        }
        try:
            response = _post_jsonrpc(
                self._endpoint(),
                payload,
                api_key=self.api_key,
                timeout=self.timeout,
                verify_tls=self.verify_tls,
            )
        except error.HTTPError as exc:
            if exc.code in (401, 403):
                raise LeantimeAuthError('Leantime rejected the scoped API key') from exc
            if exc.code >= 500:
                raise LeantimeUnavailable(f'Leantime returned HTTP {exc.code}') from exc
            raise LeantimeProtocolError(f'Leantime returned unexpected HTTP {exc.code}') from exc
        except error.URLError as exc:
            raise LeantimeUnavailable('Leantime connection failed') from exc
        except TimeoutError as exc:
            raise LeantimeUnavailable('Leantime request timed out') from exc
        except (ValueError, json.JSONDecodeError) as exc:
            raise LeantimeProtocolError('Leantime response was not valid JSON') from exc

        if not isinstance(response, dict):
            raise LeantimeProtocolError('Leantime response was not a JSON object')

        if 'error' in response:
            rpc_error = response['error']
            message = rpc_error.get('message', 'unknown error') if isinstance(rpc_error, dict) else str(rpc_error)
            raise LeantimeRpcError(message)

        if 'result' not in response:
            raise LeantimeProtocolError('Leantime response missing result field')

        return response['result']

    def list_projects(self) -> list['LeantimeProject']:
        from app.modules.leantime.schemas import LeantimeProject

        result = self._call('leantime.rpc.projects.getAll')
        rows = result if isinstance(result, list) else []
        return [_normalize_project(row) for row in rows if isinstance(row, dict)]

    def list_tasks(self) -> list['LeantimeTask']:
        from app.modules.leantime.schemas import LeantimeTask

        result = self._call('leantime.rpc.tickets.getAll')
        rows = result if isinstance(result, list) else []
        return [_normalize_task(row) for row in rows if isinstance(row, dict)]

    def list_calendar(self, start: str, end: str) -> list['LeantimeCalendarEntry']:
        from app.modules.leantime.schemas import LeantimeCalendarEntry

        result = self._call('leantime.rpc.calendar.getAll', {'start': start, 'end': end})
        rows = result if isinstance(result, list) else []
        return [_normalize_calendar_entry(row) for row in rows if isinstance(row, dict)]


def _normalize_project(row: dict[str, Any]) -> 'LeantimeProject':
    from app.modules.leantime.schemas import LeantimeProject

    return LeantimeProject(
        id=_normalize_str(row.get('id')),
        name=_normalize_str(row.get('name'), default='(untitled project)'),
        state=_normalize_optional_str(row.get('state')),
        client_name=_normalize_optional_str(row.get('clientName') or row.get('client_name')),
    )


def _normalize_task(row: dict[str, Any]) -> 'LeantimeTask':
    from app.modules.leantime.schemas import LeantimeTask

    return LeantimeTask(
        id=_normalize_str(row.get('id')),
        project_id=_normalize_optional_str(row.get('projectId') or row.get('project_id')),
        headline=_normalize_str(row.get('headline'), default='(untitled task)'),
        status=_normalize_optional_str(row.get('status')),
        date_to_finish=_normalize_optional_str(row.get('dateToFinish') or row.get('date_to_finish')),
    )


def _normalize_calendar_entry(row: dict[str, Any]) -> 'LeantimeCalendarEntry':
    from app.modules.leantime.schemas import LeantimeCalendarEntry

    return LeantimeCalendarEntry(
        id=_normalize_str(row.get('id')),
        name=_normalize_str(row.get('name'), default='(untitled event)'),
        date_start=_normalize_optional_str(row.get('dateStart') or row.get('date_start')),
        date_end=_normalize_optional_str(row.get('dateEnd') or row.get('date_end')),
    )
