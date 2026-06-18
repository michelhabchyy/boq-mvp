"""Authentication: password hashing, JWT tokens, and FastAPI guards.

Single-tenant per deployment (each company gets its own copy + DB), so there is
no org scoping — just users with roles. Guards:
  require_user  -> any active, logged-in user
  require_admin -> active user with role 'admin'
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import settings
from .db import SessionLocal, get_db
from .models import User

ALGORITHM = "HS256"
_bearer = HTTPBearer(auto_error=True)


# --- passwords ---------------------------------------------------------------


def hash_password(password: str) -> str:
    # bcrypt has a 72-byte limit; encode and let bcrypt handle salting.
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


# --- tokens ------------------------------------------------------------------


def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.username,
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.auth_secret, algorithm=ALGORITHM)


# --- guards ------------------------------------------------------------------


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(creds.credentials, settings.auth_secret, algorithms=[ALGORITHM])
        username = payload.get("sub")
    except jwt.PyJWTError:
        raise cred_exc
    if not username:
        raise cred_exc

    user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if user is None or not user.is_active:
        raise cred_exc
    # A user whose company has been disabled loses access immediately.
    if user.company_id is not None:
        from .models import Company

        company = db.get(Company, user.company_id)
        if company is None or not company.is_active:
            raise cred_exc
    return user


def require_user(user: User = Depends(get_current_user)) -> User:
    return user


def require_owner(user: User = Depends(get_current_user)) -> User:
    """Platform super-admin only (manages companies)."""
    if user.role != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner only")
    return user


def require_company_user(user: User = Depends(get_current_user)) -> User:
    """Any company user (admin or reviewer). Owner has no company → blocked."""
    if user.company_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This area requires a company account",
        )
    return user


def require_company_admin(user: User = Depends(get_current_user)) -> User:
    """Company admin (manages their company's users + subcontractors + catalog)."""
    if user.company_id is None or user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Company admin only"
        )
    return user


def require_subcontractor(user: User = Depends(get_current_user)) -> User:
    """A subcontractor login (manages only its own item list)."""
    if user.role != "subcontractor" or user.subcontractor_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Subcontractor account only"
        )
    return user


def current_company_id(user: User = Depends(require_company_user)) -> int:
    """Tenant id for estimator-side endpoints (catalog/RFP/matching/BoQ/output).

    Subcontractors are NOT estimators — they only use /my-items — so they are
    blocked here. This single guard fences them out of every estimator route.
    """
    if user.role not in ("admin", "reviewer"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This area is for the contractor's team, not subcontractors",
        )
    return user.company_id


# --- bootstrap ---------------------------------------------------------------


def seed_owner() -> None:
    """Ensure a platform owner exists.

    Fresh DB  -> create the owner from SEED_ADMIN_* env vars.
    Upgraded DB (had a pre-multi-tenancy admin) -> promote that user to owner.
    """
    with SessionLocal() as db:
        owner = db.execute(select(User).where(User.role == "owner")).scalars().first()
        if owner is not None:
            return

        existing = db.execute(
            select(User).where(User.username == settings.seed_admin_username)
        ).scalar_one_or_none()
        if existing is not None:
            existing.role = "owner"
            existing.company_id = None
            db.commit()
            return

        db.add(
            User(
                username=settings.seed_admin_username,
                full_name="Platform Owner",
                password_hash=hash_password(settings.seed_admin_password),
                role="owner",
                company_id=None,
                is_active=True,
            )
        )
        db.commit()
