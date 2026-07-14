from __future__ import annotations

import base64

import pytest

from app.modules.ai import llm_crypto

_SECRET = 'unit-test-secret-key-0123456789abcdef'


def test_encrypt_decrypt_roundtrip() -> None:
    plaintext = 'sk-proj-abcdef1234567890'
    token = llm_crypto.encrypt(plaintext, _SECRET)
    assert token.startswith('v1:')
    assert plaintext not in token  # 평문이 토큰 안에 그대로 남지 않는다.
    assert llm_crypto.decrypt(token, _SECRET) == plaintext


def test_encrypt_uses_fresh_nonce_each_time() -> None:
    plaintext = 'same-key-value'
    first = llm_crypto.encrypt(plaintext, _SECRET)
    second = llm_crypto.encrypt(plaintext, _SECRET)
    assert first != second  # nonce 가 매번 달라 토큰도 달라진다.
    assert llm_crypto.decrypt(first, _SECRET) == plaintext
    assert llm_crypto.decrypt(second, _SECRET) == plaintext


def test_decrypt_rejects_tampered_tag() -> None:
    token = llm_crypto.encrypt('secret-value', _SECRET)
    raw = bytearray(base64.urlsafe_b64decode(token[len('v1:'):].encode('ascii')))
    raw[16] ^= 0x01  # tag 첫 바이트 변조 → MAC 검증 실패.
    tampered = 'v1:' + base64.urlsafe_b64encode(bytes(raw)).decode('ascii')
    with pytest.raises(ValueError):
        llm_crypto.decrypt(tampered, _SECRET)


def test_decrypt_rejects_wrong_secret() -> None:
    token = llm_crypto.encrypt('secret-value', _SECRET)
    with pytest.raises(ValueError):
        llm_crypto.decrypt(token, 'a-completely-different-secret-value-xx')


def test_decrypt_rejects_bad_prefix_and_truncation() -> None:
    with pytest.raises(ValueError):
        llm_crypto.decrypt('plain-not-a-token', _SECRET)
    with pytest.raises(ValueError):
        llm_crypto.decrypt('v1:' + base64.urlsafe_b64encode(b'short').decode('ascii'), _SECRET)


def test_mask_keeps_prefix_and_last_four() -> None:
    assert llm_crypto.mask('sk-proj-abcdef1234') == 'sk-...1234'


def test_mask_short_key_fully_hidden() -> None:
    assert llm_crypto.mask('abc123') == '****'
    assert llm_crypto.mask('') == ''
