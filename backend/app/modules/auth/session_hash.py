from __future__ import annotations

import hashlib


def hash_session_token(token: str) -> str:
    """Canonical session-token hash: UTF-8 SHA-256, lowercase hex digest.

    This is the SOLE hashing routine for session tokens across the auth
    module (session-activity creation, activity current-session comparison,
    and logout session-activity removal). Do not reimplement inline.
    """
    return hashlib.sha256(token.encode('utf-8')).hexdigest()
