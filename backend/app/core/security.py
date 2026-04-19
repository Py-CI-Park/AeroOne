from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
import secrets
from typing import Any

import jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def hash_file_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def create_access_token(secret_key: str, subject: str, role: str, csrf_token: str, ttl_minutes: int) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        'sub': subject,
        'role': role,
        'csrf': csrf_token,
        'iat': int(now.timestamp()),
        'exp': int((now + timedelta(minutes=ttl_minutes)).timestamp()),
    }
    return jwt.encode(payload, secret_key, algorithm='HS256')


def decode_access_token(token: str, secret_key: str) -> dict[str, Any]:
    return jwt.decode(token, secret_key, algorithms=['HS256'])
