"""TOTP two-factor auth helpers (RFC 6238), used by the auth router."""

from __future__ import annotations

import io

import pyotp
import qrcode
import qrcode.image.svg

ISSUER = "Taqdeer"


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
