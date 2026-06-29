"""Staff (admin/reviewer) user management — company ADMIN, or the OWNER acting
on a company via X-Company-Id. Company resolved by `admin_company_id`; the acting
user is used only for self-protection (an admin can't lock themselves out)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import admin_company_id, get_current_user, hash_password
from ..db import get_db
from ..models import User
from ..schemas import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])

COMPANY_ROLES = {"admin", "reviewer"}  # company admins cannot mint owners


@router.get("", response_model=list[UserOut])
def list_users(
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    cid: int = Depends(admin_company_id),
):
    # Staff only — subcontractor logins are managed under /subcontractors.
    return (
        db.execute(
            select(User)
            .where(User.company_id == cid, User.subcontractor_id.is_(None))
            .order_by(User.username)
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )


@router.post("", response_model=UserOut)
def create_user(
    payload: UserCreate, db: Session = Depends(get_db), cid: int = Depends(admin_company_id)
):
    if payload.role not in COMPANY_ROLES:
        raise HTTPException(400, f"role must be one of {sorted(COMPANY_ROLES)}")
    if db.execute(
        select(User).where(User.username == payload.username)
    ).scalar_one_or_none():
        raise HTTPException(409, f"Username '{payload.username}' already exists")
    user = User(
        username=payload.username,
        full_name=payload.full_name,
        role=payload.role,
        password_hash=hash_password(payload.password),
        company_id=cid,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _own_company_user(db: Session, user_id: int, cid: int) -> User:
    user = db.get(User, user_id)
    if user is None or user.company_id != cid or user.subcontractor_id is not None:
        raise HTTPException(404, f"User {user_id} not found")
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    cid: int = Depends(admin_company_id),
    actor: User = Depends(get_current_user),
):
    user = _own_company_user(db, user_id, cid)
    fields = payload.model_dump(exclude_unset=True)
    if "role" in fields and fields["role"] not in COMPANY_ROLES:
        raise HTTPException(400, f"role must be one of {sorted(COMPANY_ROLES)}")
    if user.id == actor.id:  # only triggers for a real admin editing themselves
        if fields.get("is_active") is False:
            raise HTTPException(400, "You cannot deactivate your own account")
        if fields.get("role") == "reviewer":
            raise HTTPException(400, "You cannot remove your own admin role")
    if "password" in fields:
        pw = fields.pop("password")
        if pw:
            user.password_hash = hash_password(pw)
    for key, value in fields.items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    cid: int = Depends(admin_company_id),
    actor: User = Depends(get_current_user),
):
    if user_id == actor.id:
        raise HTTPException(400, "You cannot delete your own account")
    user = _own_company_user(db, user_id, cid)
    db.delete(user)
    db.commit()
    return {"deleted": user_id}
