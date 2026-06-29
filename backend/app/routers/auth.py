"""Auth endpoints: login, current-user, and TOTP two-factor management."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .. import twofa
from ..auth import create_access_token, get_current_user, verify_password
from ..db import get_db
from ..models import RecoveryCode, User
from ..observability import get_logger
from ..ratelimit import login_rate_limit
from ..schemas import (
    LoginRequest,
    LoginResponse,
    RecoveryCodesOut,
    TwoFACode,
    TwoFASetupOut,
    TwoFAStatus,
    TwoFAVerifyOut,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])
log = get_logger("auth")


def _remaining_codes(db: Session, user_id: int) -> int:
    return db.execute(
        select(func.count(RecoveryCode.id)).where(
            RecoveryCode.user_id == user_id, RecoveryCode.used.is_(False)
        )
    ).scalar_one()


def _issue_recovery_codes(db: Session, user_id: int) -> list[str]:
    """Replace any existing codes with a fresh set; return the plaintext once."""
    db.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user_id))
    codes = twofa.generate_recovery_codes()
    for c in codes:
        db.add(RecoveryCode(user_id=user_id, code_hash=twofa.hash_recovery(c)))
    db.commit()
    return codes


def _consume_second_factor(db: Session, user: User, code: str | None) -> bool:
    """True if `code` is a valid TOTP, or an unused recovery code (which is then
    consumed)."""
    if twofa.verify(user.totp_secret, code):
        return True
    if code and twofa.looks_like_recovery(code):
        rc = db.execute(
            select(RecoveryCode).where(
                RecoveryCode.user_id == user.id,
                RecoveryCode.code_hash == twofa.hash_recovery(code),
                RecoveryCode.used.is_(False),
            )
        ).scalar_one_or_none()
        if rc is not None:
            rc.used = True
            db.commit()
            return True
    return False


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
        if not _consume_second_factor(db, user, payload.otp):
            log.warning("2FA failed for user=%s", user.username)
            raise HTTPException(status_code=401, detail="Invalid 2FA or recovery code")

    log.info("Login ok for user=%s (2fa=%s)", user.username, user.totp_enabled)
    return LoginResponse(
        access_token=create_access_token(user), user=UserOut.model_validate(user)
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


# --- two-factor (TOTP) management ------------------------------------------


@router.get("/2fa/status", response_model=TwoFAStatus)
def twofa_status(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return TwoFAStatus(
        enabled=bool(user.totp_enabled),
        recovery_codes_remaining=_remaining_codes(db, user.id) if user.totp_enabled else 0,
    )


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


@router.post("/2fa/verify", response_model=TwoFAVerifyOut)
def twofa_verify(
    payload: TwoFACode, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """Confirm enrolment with the first code; flips 2FA on and returns a fresh
    set of one-time recovery codes (shown once)."""
    if not user.totp_secret:
        raise HTTPException(400, "Start 2FA setup first.")
    if not twofa.verify(user.totp_secret, payload.code):
        raise HTTPException(400, "Invalid code. Check your authenticator app and try again.")
    user.totp_enabled = True
    db.commit()
    codes = _issue_recovery_codes(db, user.id)
    log.info("2FA enabled for user=%s", user.username)
    return TwoFAVerifyOut(enabled=True, recovery_codes=codes)


@router.post("/2fa/recovery-codes", response_model=RecoveryCodesOut)
def twofa_regenerate_codes(
    payload: TwoFACode, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """Generate a NEW set of recovery codes (invalidates the old ones). Requires
    a current valid code (TOTP or an existing recovery code)."""
    if not user.totp_enabled:
        raise HTTPException(400, "Enable 2FA first.")
    if not _consume_second_factor(db, user, payload.code):
        raise HTTPException(400, "Invalid code.")
    return RecoveryCodesOut(recovery_codes=_issue_recovery_codes(db, user.id))


@router.post("/2fa/disable", response_model=TwoFAStatus)
def twofa_disable(
    payload: TwoFACode, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """Turn 2FA off — requires a current valid code (TOTP or recovery)."""
    if not user.totp_enabled:
        # Nothing enabled; just clear any half-finished setup.
        user.totp_secret = None
        db.commit()
        return TwoFAStatus(enabled=False)
    if not _consume_second_factor(db, user, payload.code):
        raise HTTPException(400, "Invalid code; 2FA not disabled.")
    user.totp_enabled = False
    user.totp_secret = None
    db.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user.id))
    db.commit()
    log.info("2FA disabled for user=%s", user.username)
    return TwoFAStatus(enabled=False)
