from app.core.security import hash_password, verify_password


def test_password_hash_roundtrip() -> None:
    password_hash = hash_password('secret-password')
    assert verify_password('secret-password', password_hash) is True
    assert verify_password('wrong-password', password_hash) is False
