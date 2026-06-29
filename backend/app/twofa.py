"""TOTP two-factor auth helpers (RFC 6238), used by the auth router."""

from __future__ import annotations

import hashlib
import io
import secrets

import pyotp
import qrcode
import qrcode.image.svg

ISSUER = "Taqdeer"

# Unambiguous alphabet (no 0/O/1/I/L) for human-typeable recovery codes.
_RC_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def new_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(secret: str, account: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=account, issuer_name=ISSUER)


def verify(secret: str | None, code: str | None) -> bool:
    """True if `code` is valid for `secret` (±1 step for clock drift)."""
    if not secret or not code:
        return False
    code = code.strip().replace(" ", "")
    if not code.isdigit():
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def qr_svg(uri: str) -> str:
    """An inline SVG QR code for the provisioning URI (no Pillow needed)."""
    img = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage)
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue().decode("utf-8")


# --- recovery (backup) codes -----------------------------------------------


def generate_recovery_codes(count: int = 10) -> list[str]:
    """Plaintext one-time codes, e.g. 'ABCDE-FGHJK'. Shown to the user once."""
    codes = []
    for _ in range(count):
        raw = "".join(secrets.choice(_RC_ALPHABET) for _ in range(10))
        codes.append(f"{raw[:5]}-{raw[5:]}")
    return codes


def normalize_recovery(code: str | None) -> str:
    return "".join(ch for ch in (code or "").upper() if ch.isalnum())


def hash_recovery(code: str) -> str:
    return hashlib.sha256(normalize_recovery(code).encode("utf-8")).hexdigest()


def looks_like_recovery(code: str | None) -> bool:
    """A recovery code is 10 alphanumerics; a TOTP is 6 digits."""
    return len(normalize_recovery(code)) >= 8
