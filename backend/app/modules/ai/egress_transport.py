from __future__ import annotations

import http.client
import ipaddress
import json
import re
import socket
import ssl
import time
from dataclasses import dataclass
from enum import StrEnum, unique
from typing import Any, Final, override

# Fail-closed, compatible-provider-only egress transport.
#
# This module is the ONLY sanctioned way the OpenAI-compatible adapter reaches the
# network. It never consults process/environment proxy settings (no `urllib`/`requests`
# proxy auto-detection is used anywhere here — sockets are opened directly), never
# follows redirects, and pins every connection to a single numeric peer address that
# passed both baseline SSRF-style safety checks AND an operator-configured allow-list
# before a single byte is sent. Nothing here ever logs, returns, or persists secret
# material; callers pass an `Authorization` value in and only ever get back a sanitized
# `EgressOutcome`.

_MAX_URL_LENGTH: Final = 2048
_HOSTNAME_LABEL_RE: Final = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")


def _app_version() -> str:
    # 지연 임포트: 이 모듈은 앱 의존이 없는 하드닝된 전송 계층이라 최상단에서
    # app.core.config 를 끌어오지 않는다. User-Agent 표기에만 릴리스 버전을 쓴다.
    from app.core.config import settings

    return settings.app_version


@unique
class EgressErrorCode(StrEnum):
    URL_INVALID = "url-invalid"
    URL_UNSAFE_COMPONENT = "url-unsafe-component"
    SCHEME_NOT_ALLOWED = "scheme-not-allowed"
    HOST_INVALID = "host-invalid"
    HOST_AMBIGUOUS = "host-ambiguous"
    PORT_NOT_ALLOWED = "port-not-allowed"
    PEER_POLICY_DENIED = "peer-policy-denied"
    DNS_RESOLUTION_FAILED = "dns-resolution-failed"
    PEER_EQUALITY_FAILED = "peer-equality-failed"
    TLS_VERIFICATION_FAILED = "tls-verification-failed"
    CONNECT_FAILED = "connect-failed"
    REDIRECT_REJECTED = "redirect-rejected"
    REQUEST_TOO_LARGE = "request-too-large"
    RESPONSE_TOO_LARGE = "response-too-large"
    INVALID_JSON = "invalid-json"
    HTTP_ERROR = "http-error"
    UPSTREAM_SHAPE_INVALID = "upstream-shape-invalid"


class EgressError(RuntimeError):
    code: EgressErrorCode

    def __init__(self, code: EgressErrorCode) -> None:
        self.code = code
        super().__init__(code.value)

    @override
    def __str__(self) -> str:
        return self.code.value


@dataclass(frozen=True, slots=True)
class CanonicalEndpoint:
    scheme: str
    host: str
    port: int
    path: str
    canonical_url: str


@dataclass(frozen=True, slots=True)
class PinnedPeer:
    ip: str
    family: int


@dataclass(frozen=True, slots=True)
class EgressPolicy:
    connect_timeout_seconds: float
    read_timeout_seconds: float
    max_request_bytes: int
    max_response_bytes: int
    allow_insecure_http: bool


@dataclass(frozen=True, slots=True)
class PeerPolicy:
    """Operator-configured allow-list. Both fields default-deny: an empty/None
    collection means nothing resolves (fail closed), never "no restriction"."""

    allowed_hostnames: frozenset[str] | None
    allowed_cidrs: tuple[str, ...]
    allowed_ports: frozenset[int]


@dataclass(frozen=True, slots=True)
class EgressOutcome:
    """Sanitized result taxonomy. Never carries request/response bodies, headers, or
    credential material — only enough to classify what happened and (on success) the
    parsed, size-bounded JSON payload the caller asked for."""

    ok: bool
    error_code: EgressErrorCode | None
    status_code: int | None
    latency_ms: int
    payload: dict[str, Any] | None


def canonicalize_endpoint(raw_url: str, *, app_env: str) -> CanonicalEndpoint:
    if not isinstance(raw_url, str) or not raw_url or len(raw_url) > _MAX_URL_LENGTH:
        raise EgressError(EgressErrorCode.URL_INVALID)
    from urllib.parse import urlsplit

    try:
        parts = urlsplit(raw_url)
    except ValueError as exc:
        raise EgressError(EgressErrorCode.URL_INVALID) from exc

    if parts.scheme not in ("http", "https"):
        raise EgressError(EgressErrorCode.SCHEME_NOT_ALLOWED)
    if parts.scheme == "http" and app_env not in ("development", "test"):
        raise EgressError(EgressErrorCode.SCHEME_NOT_ALLOWED)
    if parts.username is not None or parts.password is not None:
        raise EgressError(EgressErrorCode.URL_UNSAFE_COMPONENT)
    if parts.query or parts.fragment:
        raise EgressError(EgressErrorCode.URL_UNSAFE_COMPONENT)
    if not parts.hostname:
        raise EgressError(EgressErrorCode.HOST_INVALID)

    host = _canonicalize_host(parts.hostname)
    try:
        raw_port = parts.port
    except ValueError as exc:
        raise EgressError(EgressErrorCode.URL_INVALID) from exc
    port = raw_port if raw_port is not None else (443 if parts.scheme == "https" else 80)
    if not (1 <= port <= 65535):
        raise EgressError(EgressErrorCode.URL_INVALID)

    path = parts.path or "/"
    if not path.startswith("/") or ".." in path.split("/") or "\\" in path:
        raise EgressError(EgressErrorCode.URL_UNSAFE_COMPONENT)

    canonical_url = f"{parts.scheme}://{host}:{port}{path}"
    return CanonicalEndpoint(scheme=parts.scheme, host=host, port=port, path=path, canonical_url=canonical_url)


def _canonicalize_host(raw_host: str) -> str:
    host = raw_host.strip()
    if not host:
        raise EgressError(EgressErrorCode.HOST_INVALID)

    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None

    if address is not None:
        _reject_unsafe_address(address)
        return f"[{address}]" if isinstance(address, ipaddress.IPv6Address) else str(address)

    if host.endswith(".."):
        raise EgressError(EgressErrorCode.HOST_INVALID)
    if host.endswith("."):
        host = host[:-1]
    if not host:
        raise EgressError(EgressErrorCode.HOST_INVALID)

    labels = host.split(".")
    if not labels or any(not label for label in labels):
        raise EgressError(EgressErrorCode.HOST_INVALID)

    try:
        encoded = [label.encode("idna").decode("ascii") for label in labels]
    except UnicodeError as exc:
        raise EgressError(EgressErrorCode.HOST_INVALID) from exc

    canonical = ".".join(part.lower() for part in encoded)
    if len(canonical) > 253 or not all(_HOSTNAME_LABEL_RE.match(part) for part in canonical.split(".")):
        raise EgressError(EgressErrorCode.HOST_INVALID)
    return canonical


def _reject_unsafe_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
    if address.is_unspecified or address.is_multicast or address.is_reserved:
        raise EgressError(EgressErrorCode.HOST_AMBIGUOUS)
    if isinstance(address, ipaddress.IPv6Address):
        if address.is_site_local:
            raise EgressError(EgressErrorCode.HOST_AMBIGUOUS)
        mapped = address.ipv4_mapped
        if mapped is not None:
            _reject_unsafe_address(mapped)
    else:
        if address.is_link_local:
            raise EgressError(EgressErrorCode.HOST_AMBIGUOUS)


def _strip_brackets(host: str) -> str:
    return host[1:-1] if host.startswith("[") and host.endswith("]") else host


def resolve_pinned_peer(endpoint: CanonicalEndpoint, policy: PeerPolicy) -> PinnedPeer:
    if endpoint.port not in policy.allowed_ports:
        raise EgressError(EgressErrorCode.PORT_NOT_ALLOWED)
    if policy.allowed_hostnames is not None and endpoint.host not in policy.allowed_hostnames:
        raise EgressError(EgressErrorCode.PEER_POLICY_DENIED)
    if not policy.allowed_cidrs:
        raise EgressError(EgressErrorCode.PEER_POLICY_DENIED)

    bare_host = _strip_brackets(endpoint.host)
    try:
        literal = ipaddress.ip_address(bare_host)
    except ValueError:
        literal = None

    candidates: list[ipaddress.IPv4Address | ipaddress.IPv6Address]
    if literal is not None:
        candidates = [literal]
    else:
        try:
            infos = socket.getaddrinfo(bare_host, endpoint.port, proto=socket.IPPROTO_TCP)
        except OSError as exc:
            raise EgressError(EgressErrorCode.DNS_RESOLUTION_FAILED) from exc
        seen: set[str] = set()
        candidates = []
        for info in infos:
            ip_text = info[4][0]
            if ip_text in seen:
                continue
            seen.add(ip_text)
            candidates.append(ipaddress.ip_address(ip_text))
        if not candidates:
            raise EgressError(EgressErrorCode.DNS_RESOLUTION_FAILED)

    # All-answer validation: every resolved address must independently clear safety
    # and operator policy — a single unsafe/unauthorized answer fails the whole lookup
    # so an attacker cannot smuggle one bad record past a policy that only checks one.
    for candidate in candidates:
        _reject_unsafe_address(candidate)
        _enforce_cidr_policy(candidate, policy)

    pinned = min(candidates, key=lambda addr: (addr.version, int(addr)))
    family = socket.AF_INET6 if pinned.version == 6 else socket.AF_INET
    return PinnedPeer(ip=str(pinned), family=family)


def _enforce_cidr_policy(address: ipaddress.IPv4Address | ipaddress.IPv6Address, policy: PeerPolicy) -> None:
    for cidr in policy.allowed_cidrs:
        try:
            network = ipaddress.ip_network(cidr, strict=False)
        except ValueError:
            continue
        if address in network:
            return
    raise EgressError(EgressErrorCode.PEER_POLICY_DENIED)


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, pinned_ip: str, hostname: str, port: int, *, connect_timeout: float, read_timeout: float) -> None:
        super().__init__(hostname, port, timeout=connect_timeout)
        self._pinned_ip = pinned_ip
        self._read_timeout = read_timeout

    @override
    def connect(self) -> None:
        try:
            sock = socket.create_connection((self._pinned_ip, self.port), timeout=self.timeout)
        except OSError as exc:
            raise EgressError(EgressErrorCode.CONNECT_FAILED) from exc
        if sock.getpeername()[0] != self._pinned_ip:
            sock.close()
            raise EgressError(EgressErrorCode.PEER_EQUALITY_FAILED)
        sock.settimeout(self._read_timeout)
        self.sock = sock


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(
        self,
        pinned_ip: str,
        hostname: str,
        port: int,
        *,
        connect_timeout: float,
        read_timeout: float,
        ssl_context: ssl.SSLContext,
    ) -> None:
        super().__init__(hostname, port, timeout=connect_timeout, context=ssl_context)
        self._pinned_ip = pinned_ip
        self._read_timeout = read_timeout

    @override
    def connect(self) -> None:
        try:
            raw_sock = socket.create_connection((self._pinned_ip, self.port), timeout=self.timeout)
        except OSError as exc:
            raise EgressError(EgressErrorCode.CONNECT_FAILED) from exc
        if raw_sock.getpeername()[0] != self._pinned_ip:
            raw_sock.close()
            raise EgressError(EgressErrorCode.PEER_EQUALITY_FAILED)
        try:
            # server_hostname drives both SNI and the standard hostname-verification
            # check performed by the ssl context, even though the TCP connect target
            # is the pinned numeric IP rather than a freshly re-resolved hostname.
            tls_sock = self._context.wrap_socket(raw_sock, server_hostname=self.host)
        except ssl.SSLError as exc:
            raw_sock.close()
            raise EgressError(EgressErrorCode.TLS_VERIFICATION_FAILED) from exc
        tls_sock.settimeout(self._read_timeout)
        self.sock = tls_sock


def _build_connection(
    endpoint: CanonicalEndpoint,
    peer: PinnedPeer,
    policy: EgressPolicy,
) -> http.client.HTTPConnection:
    if endpoint.scheme == "https":
        context = ssl.create_default_context()
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        return _PinnedHTTPSConnection(
            peer.ip,
            _strip_brackets(endpoint.host),
            endpoint.port,
            connect_timeout=policy.connect_timeout_seconds,
            read_timeout=policy.read_timeout_seconds,
            ssl_context=context,
        )
    if not policy.allow_insecure_http:
        raise EgressError(EgressErrorCode.SCHEME_NOT_ALLOWED)
    return _PinnedHTTPConnection(
        peer.ip,
        _strip_brackets(endpoint.host),
        endpoint.port,
        connect_timeout=policy.connect_timeout_seconds,
        read_timeout=policy.read_timeout_seconds,
    )


def _read_bounded(response: http.client.HTTPResponse, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = response.read(8192)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise EgressError(EgressErrorCode.RESPONSE_TOO_LARGE)
        chunks.append(chunk)
    return b"".join(chunks)


def send_json_request(
    endpoint: CanonicalEndpoint,
    peer: PinnedPeer,
    *,
    method: str,
    body: dict[str, Any] | None,
    authorization: str | None,
    policy: EgressPolicy,
) -> tuple[int, dict[str, Any]]:
    data: bytes | None = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        if len(data) > policy.max_request_bytes:
            raise EgressError(EgressErrorCode.REQUEST_TOO_LARGE)

    host_header = endpoint.host if endpoint.port in (80, 443) else f"{endpoint.host}:{endpoint.port}"
    headers: dict[str, str] = {
        "Host": host_header,
        "Accept": "application/json",
        "Connection": "close",
        # 릴리스 버전 단일 원천(settings.app_version)에서 파생 — 하드코딩 버전 드리프트 방지.
        "User-Agent": f"AeroOne-Compatible-Adapter/{_app_version()}",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(data))
    # Authorization is attached last: by this point canonicalization, host safety,
    # operator policy, DNS all-answer validation, and peer pinning have all already
    # succeeded — the credential is never placed on the wire toward an unvalidated peer.
    if authorization is not None:
        headers["Authorization"] = authorization

    conn = _build_connection(endpoint, peer, policy)
    try:
        conn.request(method, endpoint.path, body=data, headers=headers)
        response = conn.getresponse()
        if 300 <= response.status < 400:
            raise EgressError(EgressErrorCode.REDIRECT_REJECTED)
        raw = _read_bounded(response, policy.max_response_bytes)
        status_code = response.status
    except EgressError:
        raise
    except (TimeoutError, OSError) as exc:
        raise EgressError(EgressErrorCode.CONNECT_FAILED) from exc
    finally:
        conn.close()

    if status_code >= 400:
        raise EgressError(EgressErrorCode.HTTP_ERROR)

    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EgressError(EgressErrorCode.INVALID_JSON) from exc
    if not isinstance(parsed, dict):
        raise EgressError(EgressErrorCode.INVALID_JSON)
    return status_code, parsed


def _execute(
    raw_url: str,
    *,
    app_env: str,
    method: str,
    path: str,
    body: dict[str, Any] | None,
    api_key: str,
    policy: EgressPolicy,
    peer_policy: PeerPolicy,
) -> EgressOutcome:
    started = time.monotonic()
    try:
        endpoint = canonicalize_endpoint(raw_url, app_env=app_env)
        endpoint = CanonicalEndpoint(scheme=endpoint.scheme, host=endpoint.host, port=endpoint.port, path=path, canonical_url=endpoint.canonical_url)
        peer = resolve_pinned_peer(endpoint, peer_policy)
        status_code, payload = send_json_request(
            endpoint,
            peer,
            method=method,
            body=body,
            authorization=f"Bearer {api_key}",
            policy=policy,
        )
    except EgressError as exc:
        return EgressOutcome(ok=False, error_code=exc.code, status_code=None, latency_ms=int((time.monotonic() - started) * 1000), payload=None)
    return EgressOutcome(ok=True, error_code=None, status_code=status_code, latency_ms=int((time.monotonic() - started) * 1000), payload=payload)


def probe_models(
    raw_url: str,
    *,
    model: str,
    app_env: str,
    api_key: str,
    policy: EgressPolicy,
    peer_policy: PeerPolicy,
) -> EgressOutcome:
    """Strict GET /v1/models probe: succeeds only if the requested model id is present
    in a well-formed OpenAI-compatible model listing."""
    outcome = _execute(
        raw_url,
        app_env=app_env,
        method="GET",
        path="/v1/models",
        body=None,
        api_key=api_key,
        policy=policy,
        peer_policy=peer_policy,
    )
    if not outcome.ok or outcome.payload is None:
        return outcome
    data = outcome.payload.get("data")
    if not isinstance(data, list):
        return EgressOutcome(ok=False, error_code=EgressErrorCode.UPSTREAM_SHAPE_INVALID, status_code=outcome.status_code, latency_ms=outcome.latency_ms, payload=None)
    ids = {entry.get("id") for entry in data if isinstance(entry, dict) and isinstance(entry.get("id"), str)}
    if model not in ids:
        return EgressOutcome(ok=False, error_code=EgressErrorCode.UPSTREAM_SHAPE_INVALID, status_code=outcome.status_code, latency_ms=outcome.latency_ms, payload=None)
    return outcome


def chat_completion(
    raw_url: str,
    *,
    model: str,
    messages: list[dict[str, str]],
    app_env: str,
    api_key: str,
    policy: EgressPolicy,
    peer_policy: PeerPolicy,
    max_tokens: int = 1200,
) -> EgressOutcome:
    """Bounded, non-streaming POST /v1/chat/completions call."""
    outcome = _execute(
        raw_url,
        app_env=app_env,
        method="POST",
        path="/v1/chat/completions",
        body={"model": model, "messages": messages, "stream": False, "max_tokens": max_tokens, "temperature": 0.2},
        api_key=api_key,
        policy=policy,
        peer_policy=peer_policy,
    )
    if not outcome.ok or outcome.payload is None:
        return outcome
    choices = outcome.payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return EgressOutcome(ok=False, error_code=EgressErrorCode.UPSTREAM_SHAPE_INVALID, status_code=outcome.status_code, latency_ms=outcome.latency_ms, payload=None)
    first = choices[0]
    message = first.get("message") if isinstance(first, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str):
        return EgressOutcome(ok=False, error_code=EgressErrorCode.UPSTREAM_SHAPE_INVALID, status_code=outcome.status_code, latency_ms=outcome.latency_ms, payload=None)
    return outcome
def embeddings(
    raw_url: str,
    *,
    model: str,
    inputs: list[str],
    app_env: str,
    api_key: str,
    policy: EgressPolicy,
    peer_policy: PeerPolicy,
) -> EgressOutcome:
    """OpenAI 호환 POST /v1/embeddings 호출과 응답 벡터 형태를 검증한다."""
    outcome = _execute(
        raw_url,
        app_env=app_env,
        method="POST",
        path="/v1/embeddings",
        body={"model": model, "input": inputs},
        api_key=api_key,
        policy=policy,
        peer_policy=peer_policy,
    )
    if not outcome.ok or outcome.payload is None:
        return outcome
    data = outcome.payload.get("data")
    if (
        not isinstance(data, list)
        or len(data) != len(inputs)
        or any(
            not isinstance(item, dict)
            or not isinstance(item.get("embedding"), list)
            or not item["embedding"]
            or any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in item["embedding"])
            for item in data
        )
    ):
        return EgressOutcome(
            ok=False,
            error_code=EgressErrorCode.UPSTREAM_SHAPE_INVALID,
            status_code=outcome.status_code,
            latency_ms=outcome.latency_ms,
            payload=None,
        )
    return outcome
