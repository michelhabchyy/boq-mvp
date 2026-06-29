"""Pure-unit tests: password hashing and JWT — no database needed."""

import jwt
import pytest

from app.auth import ALGORITHM, create_access_token, hash_password, verify_password
from app.config import settings


def test_password_hash_roundtrip():
    h = hash_password("KarimMichel123")
    assert h != "KarimMichel123"  # stored hashed, never plaintext
    assert verify_password("KarimMichel123", h) is True
    assert verify_password("wrong", h) is False


def test_password_hashes_are_salted():
    assert hash_password("same") != hash_password("same")  # unique salt each time


class _U:
    username = "alice"
    role = "admin"


def test_jwt_roundtrip():
    tok = create_access_token(_U())
    payload = jwt.decode(tok, settings.auth_secret, algorithms=[ALGORITHM])
    assert payload["sub"] == "alice"
    assert payload["role"] == "admin"


def test_jwt_rejects_tampered_secret():
    tok = create_access_token(_U())
    with pytest.raises(jwt.InvalidTokenError):
        jwt.decode(tok, "not-the-secret", algorithms=[ALGORITHM])
