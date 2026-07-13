from __future__ import annotations

import hashlib

from app.modules.auth.session_hash import hash_session_token


def test_hash_session_token_matches_known_vector() -> None:
    assert hash_session_token('token') == '3c469e9d6c5875d37a43f353d4f88e61fcf812c66eee3457465a40b0da4153e0'


def test_hash_session_token_matches_hashlib_reference_for_ascii() -> None:
    token = 'sample-session-token-value'
    expected = hashlib.sha256(token.encode('utf-8')).hexdigest()
    assert hash_session_token(token) == expected


def test_hash_session_token_matches_hashlib_reference_for_korean_utf8() -> None:
    token = '토큰-korean-테스트'
    expected = hashlib.sha256(token.encode('utf-8')).hexdigest()
    assert hash_session_token(token) == expected
    assert hash_session_token(token) == '28d4beb309b23ca9e4f0daa7b877b6dfa24ff68b2ab600b8b2731680fd2b6eae'


def test_hash_session_token_is_lowercase_hex_64_chars() -> None:
    digest = hash_session_token('another-token')
    assert len(digest) == 64
    assert digest == digest.lower()
    int(digest, 16)  # raises ValueError if not valid hex
