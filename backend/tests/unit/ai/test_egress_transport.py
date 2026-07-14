from __future__ import annotations

import socket

import pytest

from app.modules.ai.egress_transport import (
    CanonicalEndpoint,
    EgressError,
    EgressErrorCode,
    PeerPolicy,
    canonicalize_endpoint,
    resolve_pinned_peer,
)

# ---------------------------------------------------------------------------
# canonicalize_endpoint
# ---------------------------------------------------------------------------


def test_canonicalize_endpoint_accepts_explicit_port_http_loopback_in_development() -> None:
    endpoint = canonicalize_endpoint('http://127.0.0.1:8080/v1/chat', app_env='development')
    assert endpoint == CanonicalEndpoint(
        scheme='http',
        host='127.0.0.1',
        port=8080,
        path='/v1/chat',
        canonical_url='http://127.0.0.1:8080/v1/chat',
    )


def test_canonicalize_endpoint_accepts_explicit_port_http_loopback_in_test_env() -> None:
    endpoint = canonicalize_endpoint('http://127.0.0.1:8080/', app_env='test')
    assert endpoint.canonical_url == 'http://127.0.0.1:8080/'


def test_canonicalize_endpoint_rejects_query() -> None:
    with pytest.raises(EgressError) as exc:
        canonicalize_endpoint('http://127.0.0.1:8080/v1?foo=bar', app_env='development')
    assert exc.value.code == EgressErrorCode.URL_UNSAFE_COMPONENT


def test_canonicalize_endpoint_rejects_fragment() -> None:
    with pytest.raises(EgressError) as exc:
        canonicalize_endpoint('http://127.0.0.1:8080/v1#frag', app_env='development')
    assert exc.value.code == EgressErrorCode.URL_UNSAFE_COMPONENT


def test_canonicalize_endpoint_rejects_userinfo() -> None:
    with pytest.raises(EgressError) as exc:
        canonicalize_endpoint('http://attacker:secret@127.0.0.1:8080/v1', app_env='development')
    assert exc.value.code == EgressErrorCode.URL_UNSAFE_COMPONENT


def test_canonicalize_endpoint_rejects_oversized_url() -> None:
    oversized = 'https://example.com:443/' + ('a' * 2048)
    assert len(oversized) > 2048
    with pytest.raises(EgressError) as exc:
        canonicalize_endpoint(oversized, app_env='production')
    assert exc.value.code == EgressErrorCode.URL_INVALID


def test_canonicalize_endpoint_rejects_non_absolute_url() -> None:
    with pytest.raises(EgressError) as exc:
        canonicalize_endpoint('/v1/chat/completions', app_env='development')
    assert exc.value.code == EgressErrorCode.SCHEME_NOT_ALLOWED


@pytest.mark.parametrize('ambiguous_host', ['0177.0.0.1', '0x7f.0.0.1', '2130706433', '127.1'])
def test_canonicalize_endpoint_treats_ambiguous_ipv4_notations_as_hostnames_not_literals(ambiguous_host: str) -> None:
    # Python's ipaddress.ip_address() rejects octal/hex/short-form IPv4 notation outright
    # (no silent decimal/octal/hex reinterpretation), so canonicalize_endpoint falls
    # through to the hostname path for these instead of resolving them as literal IPs.
    # The actual SSRF defense against these strings therefore lives in
    # resolve_pinned_peer's DNS-answer safety/CIDR validation (covered below), not here.
    endpoint = canonicalize_endpoint(f'http://{ambiguous_host}:8080/', app_env='development')
    assert endpoint.host == ambiguous_host
    assert endpoint.port == 8080


def test_canonicalize_endpoint_idna_normalizes_unicode_host() -> None:
    endpoint = canonicalize_endpoint('http://MÜLLER.example:8080/v1', app_env='development')
    assert endpoint.host == 'xn--mller-kva.example'
    assert endpoint.canonical_url == 'http://xn--mller-kva.example:8080/v1'


def test_canonicalize_endpoint_strips_trailing_dot() -> None:
    endpoint = canonicalize_endpoint('http://example.com.:8080/v1', app_env='development')
    assert endpoint.host == 'example.com'


def test_canonicalize_endpoint_requires_https_in_production() -> None:
    with pytest.raises(EgressError) as exc:
        canonicalize_endpoint('http://example.com:8080/v1', app_env='production')
    assert exc.value.code == EgressErrorCode.SCHEME_NOT_ALLOWED

    ok = canonicalize_endpoint('https://example.com:443/v1', app_env='production')
    assert ok.scheme == 'https'


def test_canonicalize_endpoint_rejects_http_in_closed_network() -> None:
    # closed_network is not in the (development, test) allow-list that gates
    # insecure http, so http is rejected there just like production.
    with pytest.raises(EgressError) as exc:
        canonicalize_endpoint('http://example.com:8080/v1', app_env='closed_network')
    assert exc.value.code == EgressErrorCode.SCHEME_NOT_ALLOWED


@pytest.mark.parametrize(
    'unsafe_host',
    ['0.0.0.0', '224.0.0.1', '240.0.0.1', '169.254.1.1'],
)
def test_canonicalize_endpoint_rejects_unsafe_literal_addresses(unsafe_host: str) -> None:
    with pytest.raises(EgressError) as exc:
        canonicalize_endpoint(f'http://{unsafe_host}:8080/', app_env='development')
    assert exc.value.code == EgressErrorCode.HOST_AMBIGUOUS


def test_canonicalize_endpoint_allows_private_rfc1918_literal_at_canonicalize_stage() -> None:
    # RFC1918/loopback are not blanket-rejected here; operator CIDR allow-listing is
    # enforced later, in resolve_pinned_peer.
    endpoint = canonicalize_endpoint('http://10.0.0.5:8080/', app_env='development')
    assert endpoint.host == '10.0.0.5'


# ---------------------------------------------------------------------------
# resolve_pinned_peer
# ---------------------------------------------------------------------------


def _policy(**overrides: object) -> PeerPolicy:
    base: dict[str, object] = {
        'allowed_hostnames': None,
        'allowed_cidrs': ('127.0.0.0/8',),
        'allowed_ports': frozenset({8080}),
    }
    base.update(overrides)
    return PeerPolicy(**base)  # type: ignore[arg-type]


def test_resolve_pinned_peer_rejects_port_not_in_allow_list() -> None:
    endpoint = canonicalize_endpoint('http://127.0.0.1:9999/', app_env='development')
    with pytest.raises(EgressError) as exc:
        resolve_pinned_peer(endpoint, _policy(allowed_ports=frozenset({8080})))
    assert exc.value.code == EgressErrorCode.PORT_NOT_ALLOWED


def test_resolve_pinned_peer_rejects_hostname_outside_allow_list() -> None:
    endpoint = canonicalize_endpoint('http://127.0.0.1:8080/', app_env='development')
    with pytest.raises(EgressError) as exc:
        resolve_pinned_peer(endpoint, _policy(allowed_hostnames=frozenset({'other.example'})))
    assert exc.value.code == EgressErrorCode.PEER_POLICY_DENIED


def test_resolve_pinned_peer_fails_closed_with_no_allowed_cidrs() -> None:
    endpoint = canonicalize_endpoint('http://127.0.0.1:8080/', app_env='development')
    with pytest.raises(EgressError) as exc:
        resolve_pinned_peer(endpoint, _policy(allowed_cidrs=()))
    assert exc.value.code == EgressErrorCode.PEER_POLICY_DENIED


def test_resolve_pinned_peer_pins_single_approved_numeric_peer() -> None:
    endpoint = canonicalize_endpoint('http://127.0.0.1:8080/', app_env='development')
    pinned = resolve_pinned_peer(endpoint, _policy())
    assert pinned.ip == '127.0.0.1'
    assert pinned.family == socket.AF_INET


def test_resolve_pinned_peer_resolves_hostname_via_getaddrinfo_seam(monkeypatch: pytest.MonkeyPatch) -> None:
    endpoint = canonicalize_endpoint('http://api.internal.example:8080/', app_env='development')

    def fake_getaddrinfo(host: str, port: int, *, proto: int = 0) -> list[tuple]:
        assert host == 'api.internal.example'
        assert port == 8080
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.9', port))]

    monkeypatch.setattr('app.modules.ai.egress_transport.socket.getaddrinfo', fake_getaddrinfo)
    pinned = resolve_pinned_peer(endpoint, _policy())
    assert pinned.ip == '127.0.0.9'
    assert pinned.family == socket.AF_INET


def test_resolve_pinned_peer_rejects_when_getaddrinfo_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    endpoint = canonicalize_endpoint('http://api.internal.example:8080/', app_env='development')

    def fake_getaddrinfo(host: str, port: int, *, proto: int = 0) -> list[tuple]:
        raise OSError('name resolution failed')

    monkeypatch.setattr('app.modules.ai.egress_transport.socket.getaddrinfo', fake_getaddrinfo)
    with pytest.raises(EgressError) as exc:
        resolve_pinned_peer(endpoint, _policy())
    assert exc.value.code == EgressErrorCode.DNS_RESOLUTION_FAILED


def test_resolve_pinned_peer_rejects_when_getaddrinfo_returns_no_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    endpoint = canonicalize_endpoint('http://api.internal.example:8080/', app_env='development')

    monkeypatch.setattr('app.modules.ai.egress_transport.socket.getaddrinfo', lambda *a, **k: [])
    with pytest.raises(EgressError) as exc:
        resolve_pinned_peer(endpoint, _policy())
    assert exc.value.code == EgressErrorCode.DNS_RESOLUTION_FAILED


def test_resolve_pinned_peer_rejects_dns_rebinding_style_mixed_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    # One answer is inside the operator allow-list, the other is an unrelated public
    # address. All-answer validation must fail the whole lookup rather than pinning the
    # first "good-looking" record, which is exactly the DNS-rebinding bypass this guards.
    endpoint = canonicalize_endpoint('http://api.internal.example:8080/', app_env='development')

    def fake_getaddrinfo(host: str, port: int, *, proto: int = 0) -> list[tuple]:
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', port)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('203.0.113.9', port)),
        ]

    monkeypatch.setattr('app.modules.ai.egress_transport.socket.getaddrinfo', fake_getaddrinfo)
    with pytest.raises(EgressError) as exc:
        resolve_pinned_peer(endpoint, _policy())
    assert exc.value.code == EgressErrorCode.PEER_POLICY_DENIED


def test_resolve_pinned_peer_rejects_unsafe_resolved_address(monkeypatch: pytest.MonkeyPatch) -> None:
    endpoint = canonicalize_endpoint('http://api.internal.example:8080/', app_env='development')

    def fake_getaddrinfo(host: str, port: int, *, proto: int = 0) -> list[tuple]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('169.254.1.1', port))]

    monkeypatch.setattr('app.modules.ai.egress_transport.socket.getaddrinfo', fake_getaddrinfo)
    with pytest.raises(EgressError) as exc:
        resolve_pinned_peer(endpoint, _policy(allowed_cidrs=('169.254.0.0/16',)))
    assert exc.value.code == EgressErrorCode.HOST_AMBIGUOUS


def test_resolve_pinned_peer_rejects_ambiguous_ipv4_hostname_resolving_outside_allow_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # "2130706433" (decimal-encoded 127.0.0.1) was accepted by canonicalize_endpoint as
    # a bare hostname (see test above); this proves the SSRF defense catches it here,
    # at resolution time, once it resolves to something the operator did not allow-list.
    endpoint = canonicalize_endpoint('http://2130706433:8080/', app_env='development')

    def fake_getaddrinfo(host: str, port: int, *, proto: int = 0) -> list[tuple]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('203.0.113.5', port))]

    monkeypatch.setattr('app.modules.ai.egress_transport.socket.getaddrinfo', fake_getaddrinfo)
    with pytest.raises(EgressError) as exc:
        resolve_pinned_peer(endpoint, _policy())
    assert exc.value.code == EgressErrorCode.PEER_POLICY_DENIED
