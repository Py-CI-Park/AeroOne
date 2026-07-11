"""LLM API 키 대칭 암호화 — stdlib 만으로 구성한 HMAC 스트림 암호 + Encrypt-then-MAC.

폐쇄망 wheel 마찰을 피하려고 ``cryptography`` 같은 신규 의존성을 도입하지 않는다.
키 원천은 ``settings.jwt_secret_key`` 이며(production/closed_network 은 config 가 ≥32자
강제), 여기서 두 개의 서브키(암호화용/MAC용)를 SHA-256 라벨 파생으로 분리한다.

포맷: ``"v1:" + urlsafe_b64(nonce(16) + tag(32) + ciphertext)``.
복호화는 tag 를 ``hmac.compare_digest`` 로 상수시간 검증한 뒤에만 평문을 복원한다
(변조·잘림·잘못된 키는 모두 ``ValueError``). 시크릿이 회전되면 기존 토큰은 복호 불가가
되므로 운영자는 연결을 재등록해야 한다(런북에 명시).
"""

from __future__ import annotations

import base64
import binascii
import hmac
import os
from hashlib import sha256

_PREFIX = 'v1:'
_ENC_LABEL = b'aeroone-llm-enc-v1'
_MAC_LABEL = b'aeroone-llm-mac-v1'
_NONCE_LEN = 16
_TAG_LEN = 32


def _derive_keys(secret: str) -> tuple[bytes, bytes]:
    """시크릿 1개에서 암호화/MAC 서브키를 라벨 분리로 파생한다(키 재사용 방지)."""

    secret_bytes = secret.encode('utf-8')
    enc_key = sha256(_ENC_LABEL + secret_bytes).digest()
    mac_key = sha256(_MAC_LABEL + secret_bytes).digest()
    return enc_key, mac_key


def _keystream(enc_key: bytes, nonce: bytes, length: int) -> bytes:
    """HMAC-SHA256(enc_key, nonce+counter) 블록을 이어붙여 필요한 길이만큼 키스트림 생성."""

    blocks = bytearray()
    counter = 0
    while len(blocks) < length:
        block = hmac.new(enc_key, nonce + counter.to_bytes(4, 'big'), sha256).digest()
        blocks.extend(block)
        counter += 1
    return bytes(blocks[:length])


def _xor(data: bytes, keystream: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(data, keystream))


def encrypt(plaintext: str, secret: str) -> str:
    """평문 키를 ``v1:`` 토큰으로 암호화한다. nonce 는 호출마다 새로 뽑는다."""

    enc_key, mac_key = _derive_keys(secret)
    plaintext_bytes = plaintext.encode('utf-8')
    nonce = os.urandom(_NONCE_LEN)
    keystream = _keystream(enc_key, nonce, len(plaintext_bytes))
    ciphertext = _xor(plaintext_bytes, keystream)
    tag = hmac.new(mac_key, nonce + ciphertext, sha256).digest()
    return _PREFIX + base64.urlsafe_b64encode(nonce + tag + ciphertext).decode('ascii')


def decrypt(token: str, secret: str) -> str:
    """``v1:`` 토큰을 복호화한다. prefix/길이/MAC 중 하나라도 어긋나면 ``ValueError``."""

    if not token.startswith(_PREFIX):
        raise ValueError('invalid token prefix')
    try:
        raw = base64.urlsafe_b64decode(token[len(_PREFIX):].encode('ascii'))
    except (ValueError, binascii.Error) as exc:
        raise ValueError('invalid token encoding') from exc
    if len(raw) < _NONCE_LEN + _TAG_LEN:
        raise ValueError('token is truncated')
    nonce = raw[:_NONCE_LEN]
    tag = raw[_NONCE_LEN:_NONCE_LEN + _TAG_LEN]
    ciphertext = raw[_NONCE_LEN + _TAG_LEN:]
    enc_key, mac_key = _derive_keys(secret)
    expected_tag = hmac.new(mac_key, nonce + ciphertext, sha256).digest()
    if not hmac.compare_digest(tag, expected_tag):
        raise ValueError('MAC verification failed')
    keystream = _keystream(enc_key, nonce, len(ciphertext))
    return _xor(ciphertext, keystream).decode('utf-8')


def mask(plaintext: str) -> str:
    """응답 노출용 마스킹. 앞 3자 + 뒤 4자만 남기고, 8자 미만은 전체 ``****``."""

    if not plaintext:
        return ''
    if len(plaintext) < 8:
        return '****'
    return f'{plaintext[:3]}...{plaintext[-4:]}'
