"""Pure-unit tests: password hashing and JWT — no database needed."""

import asyncio

import jwt
import pytest
from fastapi import HTTPException

from app.auth import ALGORITHM, create_access_token, hash_password, verify_password
from app.config import settings
from app.uploads import read_upload_capped


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


class _FakeUpload:
    """Minimal stand-in for Starlette's UploadFile (returns all bytes once)."""

    def __init__(self, data: bytes):
        self._data = data
        self._done = False

    async def read(self, n: int = -1) -> bytes:
        if self._done:
            return b""
        self._done = True
        return self._data


def test_upload_cap_rejects_oversized():
    big = _FakeUpload(b"x" * 5000)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(read_upload_capped(big, max_bytes=1024))
    assert exc.value.status_code == 413


def test_upload_cap_allows_within_limit():
    small = _FakeUpload(b"hello")
    assert asyncio.run(read_upload_capped(small, max_bytes=1024)) == b"hello"
