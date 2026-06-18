"""User management within a company — company ADMIN only.

A company admin manages users in their own company. Owner-level provisioning
(creating companies + their first admin) lives in routers/companies.py.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import hash_password, require_company_admin
from ..db import get_db
from ..models import User
from ..schemas import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])

COMPANY_ROLES = {"admin", "reviewer"}  # company admins cannot mint owners


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), me: User = Depends(require_company_admin)):
    # Staff only (admin/reviewer). Subcontractor logins are managed under
    # /subcontractors, so exclude them here.
    return (
        db.execute(
            select(User)
            .where(User.company_id == me.company_id, User.subcontractor_id.is_(None))
            .order_by(User.username)
        )
        .scalars()
        .all()
    )


@router.post("", response_model=UserOut)
def create_user(
    payload: UserCreate, db: Session = Depends(get_db), me: User = Depends(require_company_admin)
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
        company_id=me.company_id,  # always the admin's own company
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _own_company_user(db: Session, user_id: int, me: User) -> User:
    user = db.get(User, user_id)
    if user is None or user.company_id != me.company_id:
        raise HTTPException(404, f"User {user_id} not found")
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    me: User = Depends(require_company_admin),
):
    user = _own_company_user(db, user_id, me)
    fields = payload.model_dump(exclude_unset=True)
    if "role" in fields and fields["role"] not in COMPANY_ROLES:
        raise HTTPException(400, f"role must be one of {sorted(COMPANY_ROLES)}")
    if user.id == me.id:
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
    user_id: int, db: Session = Depends(get_db), me: User = Depends(require_company_admin)
):
    if user_id == me.id:
        raise HTTPException(400, "You cannot delete your own account")
    user = _own_company_user(db, user_id, me)
    db.delete(user)
    db.commit()
    return {"deleted": user_id}
