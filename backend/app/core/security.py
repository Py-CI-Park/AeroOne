from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
import secrets
from typing import Any

import jwt
from passlib.context import CryptContext

PASSWORD_MAX_LENGTH = 256
PASSWORD_MIN_LENGTH = 8
_RETIRED_PASSWORD = 'change' + '-me'
pwd_context = CryptContext(
    schemes=['bcrypt_sha256', 'bcrypt'],
    deprecated=['bcrypt'],
)


class PasswordCandidateError(ValueError):
    pass


class PasswordHashError(ValueError):
    pass


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def _password_hash_scheme(password_hash: str) -> str:
    if not isinstance(password_hash, str):
        raise PasswordHashError('Stored password hash is invalid')
    try:
        scheme = pwd_context.identify(password_hash)
    except (TypeError, ValueError) as exc:
        raise PasswordHashError('Stored password hash is invalid') from exc
    if scheme is None:
        raise PasswordHashError('Stored password hash is invalid')
    return scheme


def verify_password(password: str, password_hash: str) -> bool:
    _password_hash_scheme(password_hash)
    try:
        return pwd_context.verify(password, password_hash)
    except (TypeError, ValueError) as exc:
        raise PasswordHashError('Stored password hash is invalid') from exc


def is_retired_password(value: str) -> bool:
    return isinstance(value, str) and value.strip().casefold() == _RETIRED_PASSWORD


def validate_password_candidate(
    password: str,
    *,
    field_name: str = 'Password',
    minimum_length: int = PASSWORD_MIN_LENGTH,
) -> str:
    if not isinstance(password, str):
        raise PasswordCandidateError(f'{field_name} must be text')
    if len(password) > PASSWORD_MAX_LENGTH:
        raise PasswordCandidateError(
            f'{field_name} must be at most {PASSWORD_MAX_LENGTH} characters'
        )
    if not password.strip():
        raise PasswordCandidateError(f'{field_name} is required')
    if is_retired_password(password):
        raise PasswordCandidateError('Retired password cannot be used')
    if len(password) < minimum_length:
        raise PasswordCandidateError(
            f'{field_name} must be at least {minimum_length} characters'
        )
    return password


def password_hash_uses_retired_password(password_hash: str) -> bool:
    return verify_password(_RETIRED_PASSWORD, password_hash)


def create_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def hash_file_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def create_access_token(
    secret_key: str,
    subject: str,
    role: str,
    csrf_token: str,
    ttl_minutes: int,
    session_version: int,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        'sub': subject,
        'role': role,
        'csrf': csrf_token,
        'iat': int(now.timestamp()),
        'exp': int((now + timedelta(minutes=ttl_minutes)).timestamp()),
        'ver': session_version,
    }
    return jwt.encode(payload, secret_key, algorithm='HS256')


def decode_access_token(token: str, secret_key: str) -> dict[str, Any]:
    return jwt.decode(token, secret_key, algorithms=['HS256'])
