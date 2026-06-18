"""Subcontractor management — company ADMIN, or the OWNER acting on a company
(via the X-Company-Id header). The company is resolved by `admin_company_id`.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import admin_company_id, hash_password
from ..db import get_db
from ..models import CatalogItem, Subcontractor, User
from ..schemas import (
    SubcontractorCreate,
    SubcontractorOut,
    SubcontractorUpdate,
    SubUserCreate,
    UserOut,
    UserUpdate,
)

router = APIRouter(prefix="/subcontractors", tags=["subcontractors"])


def _owned_sub(db: Session, sub_id: int, cid: int) -> Subcontractor:
    sub = db.get(Subcontractor, sub_id)
    if sub is None or sub.company_id != cid:
        raise HTTPException(404, f"Subcontractor {sub_id} not found")
    return sub


@router.get("", response_model=list[SubcontractorOut])
def list_subcontractors(db: Session = Depends(get_db), cid: int = Depends(admin_company_id)):
    subs = (
        db.execute(
            select(Subcontractor)
            .where(Subcontractor.company_id == cid)
            .order_by(Subcontractor.name)
        )
        .scalars()
        .all()
    )
    users = dict(
        db.execute(
            select(User.subcontractor_id, func.count(User.id))
            .where(User.company_id == cid, User.subcontractor_id.isnot(None))
            .group_by(User.subcontractor_id)
        ).all()
    )
    items = dict(
        db.execute(
            select(CatalogItem.subcontractor_id, func.count(CatalogItem.id))
            .where(CatalogItem.company_id == cid, CatalogItem.subcontractor_id.isnot(None))
            .group_by(CatalogItem.subcontractor_id)
        ).all()
    )
    return [
        SubcontractorOut(
            id=s.id,
            name=s.name,
            trade=s.trade,
            is_active=s.is_active,
            user_count=users.get(s.id, 0),
            item_count=items.get(s.id, 0),
        )
        for s in subs
    ]


@router.post("", response_model=SubcontractorOut)
def create_subcontractor(
    payload: SubcontractorCreate, db: Session = Depends(get_db), cid: int = Depends(admin_company_id)
):
    sub = Subcontractor(company_id=cid, name=payload.name, trade=payload.trade)
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return SubcontractorOut(id=sub.id, name=sub.name, trade=sub.trade, is_active=sub.is_active)


@router.patch("/{sub_id}", response_model=SubcontractorOut)
def update_subcontractor(
    sub_id: int,
    payload: SubcontractorUpdate,
    db: Session = Depends(get_db),
    cid: int = Depends(admin_company_id),
):
    sub = _owned_sub(db, sub_id, cid)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(sub, k, v)
    db.commit()
    db.refresh(sub)
    return SubcontractorOut(id=sub.id, name=sub.name, trade=sub.trade, is_active=sub.is_active)


@router.delete("/{sub_id}")
def delete_subcontractor(
    sub_id: int, db: Session = Depends(get_db), cid: int = Depends(admin_company_id)
):
    _owned_sub(db, sub_id, cid)
    db.query(CatalogItem).filter(CatalogItem.subcontractor_id == sub_id).delete(
        synchronize_session=False
    )
    db.query(User).filter(User.subcontractor_id == sub_id).delete(synchronize_session=False)
    db.query(Subcontractor).filter(Subcontractor.id == sub_id).delete(synchronize_session=False)
    db.commit()
    return {"deleted": sub_id}


# --- subcontractor login users ---------------------------------------------


@router.get("/{sub_id}/users", response_model=list[UserOut])
def list_sub_users(sub_id: int, db: Session = Depends(get_db), cid: int = Depends(admin_company_id)):
    _owned_sub(db, sub_id, cid)
    return (
        db.execute(select(User).where(User.subcontractor_id == sub_id).order_by(User.username))
        .scalars()
        .all()
    )


@router.post("/{sub_id}/users", response_model=UserOut)
def create_sub_user(
    sub_id: int,
    payload: SubUserCreate,
    db: Session = Depends(get_db),
    cid: int = Depends(admin_company_id),
):
    _owned_sub(db, sub_id, cid)
    if db.execute(select(User).where(User.username == payload.username)).scalar_one_or_none():
        raise HTTPException(409, f"Username '{payload.username}' already exists")
    user = User(
        username=payload.username,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role="subcontractor",
        company_id=cid,
        subcontractor_id=sub_id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{sub_id}/users/{user_id}", response_model=UserOut)
def update_sub_user(
    sub_id: int,
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    cid: int = Depends(admin_company_id),
):
    _owned_sub(db, sub_id, cid)
    user = db.get(User, user_id)
    if user is None or user.subcontractor_id != sub_id:
        raise HTTPException(404, f"User {user_id} not found")
    fields = payload.model_dump(exclude_unset=True)
    fields.pop("role", None)
    if "password" in fields:
        pw = fields.pop("password")
        if pw:
            user.password_hash = hash_password(pw)
    for k, v in fields.items():
        setattr(user, k, v)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{sub_id}/users/{user_id}")
def delete_sub_user(
    sub_id: int, user_id: int, db: Session = Depends(get_db), cid: int = Depends(admin_company_id)
):
    _owned_sub(db, sub_id, cid)
    user = db.get(User, user_id)
    if user is None or user.subcontractor_id != sub_id:
        raise HTTPException(404, f"User {user_id} not found")
    db.delete(user)
    db.commit()
    return {"deleted": user_id}
