"""Auth endpoints: login, current-user, and TOTP two-factor management."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import twofa
from ..auth import create_access_token, get_current_user, verify_password
from ..db import get_db
from ..models import User
from ..observability import get_logger
from ..ratelimit import login_rate_limit
from ..schemas import (
    LoginRequest,
    LoginResponse,
    TwoFACode,
    TwoFASetupOut,
    TwoFAStatus,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])
log = get_logger("auth")


@router.post("/login", response_model=LoginResponse, dependencies=[Depends(login_rate_limit)])
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.execute(
        select(User).where(User.username == payload.username)
    ).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        log.warning("Login failed for username=%r", payload.username)
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")
    if user.company_id is not None:
        from ..models import Company

        company = db.get(Company, user.company_id)
        if company is None or not company.is_active:
            raise HTTPException(status_code=403, detail="Company access is disabled")

    # Second factor, if enabled for this account.
    if user.totp_enabled:
        if not payload.otp:
            return LoginResponse(mfa_required=True)
        if not twofa.verify(user.totp_secret, payload.otp):
            log.warning("2FA failed for user=%s", user.username)
            raise HTTPException(status_code=401, detail="Invalid 2FA code")

    log.info("Login ok for user=%s (2fa=%s)", user.username, user.totp_enabled)
    return LoginResponse(
        access_token=create_access_token(user), user=UserOut.model_validate(user)
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


# --- two-factor (TOTP) management ------------------------------------------


@router.get("/2fa/status", response_model=TwoFAStatus)
def twofa_status(user: User = Depends(get_current_user)):
    return TwoFAStatus(enabled=bool(user.totp_enabled))


@router.post("/2fa/setup", response_model=TwoFASetupOut)
def twofa_setup(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Begin enrolment: generate a secret + QR. Not active until verified."""
    if user.totp_enabled:
        raise HTTPException(400, "2FA is already enabled. Disable it first to re-enroll.")
    secret = twofa.new_secret()
    user.totp_secret = secret
    db.commit()
    uri = twofa.provisioning_uri(secret, user.username)
    return TwoFASetupOut(secret=secret, otpauth_uri=uri, qr_svg=twofa.qr_svg(uri))


@router.post("/2fa/verify", response_model=TwoFAStatus)
def twofa_verify(
    payload: TwoFACode, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """Confirm enrolment with the first code; flips 2FA on."""
    if not user.totp_secret:
        raise HTTPException(400, "Start 2FA setup first.")
    if not twofa.verify(user.totp_secret, payload.code):
        raise HTTPException(400, "Invalid code. Check your authenticator app and try again.")
    user.totp_enabled = True
    db.commit()
    log.info("2FA enabled for user=%s", user.username)
    return TwoFAStatus(enabled=True)


@router.post("/2fa/disable", response_model=TwoFAStatus)
def twofa_disable(
    payload: TwoFACode, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """Turn 2FA off — requires a current valid code to prove possession."""
    if not user.totp_enabled:
        # Nothing enabled; just clear any half-finished setup.
        user.totp_secret = None
        db.commit()
        return TwoFAStatus(enabled=False)
    if not twofa.verify(user.totp_secret, payload.code):
        raise HTTPException(400, "Invalid code; 2FA not disabled.")
    user.totp_enabled = False
    user.totp_secret = None
    db.commit()
    log.info("2FA disabled for user=%s", user.username)
    return TwoFAStatus(enabled=False)
