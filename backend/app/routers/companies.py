"""Company (tenant) management — platform OWNER only.

The owner provisions a company together with its first admin user here. That
admin then logs in and manages their own company's users + catalog + BoQs.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import hash_password, require_owner
from ..db import get_db
from ..models import BoqLine, CatalogItem, Company, Plan, RFPDocument, RFPLine, User
from ..schemas import (
    CompanyCreate,
    CompanyOut,
    CompanyUpdate,
    CompanyUsage,
    PlatformOverview,
    UserOut,
)
from ..usage import effective_used, weekly_limit

router = APIRouter(
    prefix="/companies", tags=["companies"], dependencies=[Depends(require_owner)]
)


def _company_out(company: Company, user_count: int) -> CompanyOut:
    return CompanyOut(
        id=company.id,
        name=company.name,
        is_active=company.is_active,
        user_count=user_count,
        plan_id=company.plan_id,
        plan_name=company.plan.name if company.plan else None,
        weekly_token_limit=weekly_limit(company),
        weekly_tokens_used=effective_used(company),
    )


def _with_counts(db: Session) -> list[CompanyOut]:
    rows = db.execute(
        select(Company, func.count(User.id))
        .outerjoin(User, User.company_id == Company.id)
        .group_by(Company.id)
        .order_by(Company.name)
    ).all()
    return [_company_out(c, n) for c, n in rows]


@router.get("", response_model=list[CompanyOut])
def list_companies(db: Session = Depends(get_db)):
    return _with_counts(db)


def _count_by_company(db: Session, model) -> dict[int, int]:
    rows = db.execute(
        select(model.company_id, func.count(model.id)).group_by(model.company_id)
    ).all()
    return {cid: n for cid, n in rows if cid is not None}


@router.get("/overview", response_model=PlatformOverview)
def overview(db: Session = Depends(get_db)):
    companies = db.execute(select(Company).order_by(Company.name)).scalars().all()
    users = _count_by_company(db, User)
    catalog = _count_by_company(db, CatalogItem)
    rfps = _count_by_company(db, RFPDocument)
    boqs = _count_by_company(db, BoqLine)

    breakdown = [
        CompanyUsage(
            id=c.id,
            name=c.name,
            is_active=c.is_active,
            users=users.get(c.id, 0),
            catalog_items=catalog.get(c.id, 0),
            rfps=rfps.get(c.id, 0),
            boq_lines=boqs.get(c.id, 0),
        )
        for c in companies
    ]
    return PlatformOverview(
        companies=len(companies),
        active=sum(1 for c in companies if c.is_active),
        disabled=sum(1 for c in companies if not c.is_active),
        # Sum the breakdown so totals reflect only existing companies.
        users=sum(b.users for b in breakdown),
        catalog_items=sum(b.catalog_items for b in breakdown),
        rfps=sum(b.rfps for b in breakdown),
        boq_lines=sum(b.boq_lines for b in breakdown),
        breakdown=breakdown,
    )


@router.post("", response_model=CompanyOut)
def create_company(payload: CompanyCreate, db: Session = Depends(get_db)):
    clash = db.execute(
        select(User).where(User.username == payload.admin_username)
    ).scalar_one_or_none()
    if clash:
        raise HTTPException(409, f"Username '{payload.admin_username}' already exists")

    plan_id = payload.plan_id
    if plan_id is None:  # default new companies to the cheapest plan
        cheapest = db.execute(
            select(Plan).order_by(Plan.weekly_token_limit).limit(1)
        ).scalar_one_or_none()
        plan_id = cheapest.id if cheapest else None

    company = Company(name=payload.name, is_active=True, plan_id=plan_id)
    db.add(company)
    db.flush()  # assign company.id

    admin = User(
        username=payload.admin_username,
        full_name=payload.admin_full_name,
        password_hash=hash_password(payload.admin_password),
        role="admin",
        company_id=company.id,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(company)
    return _company_out(company, 1)


@router.patch("/{company_id}", response_model=CompanyOut)
def update_company(
    company_id: int, payload: CompanyUpdate, db: Session = Depends(get_db)
):
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(404, f"Company {company_id} not found")
    fields = payload.model_dump(exclude_unset=True)
    if fields.get("plan_id") is not None and db.get(Plan, fields["plan_id"]) is None:
        raise HTTPException(404, f"Plan {fields['plan_id']} not found")
    for key, value in fields.items():
        setattr(company, key, value)
    db.commit()
    db.refresh(company)
    n = db.execute(
        select(func.count(User.id)).where(User.company_id == company.id)
    ).scalar_one()
    return _company_out(company, n)


@router.get("/{company_id}/users", response_model=list[UserOut])
def company_users(company_id: int, db: Session = Depends(get_db)):
    if db.get(Company, company_id) is None:
        raise HTTPException(404, f"Company {company_id} not found")
    return (
        db.execute(select(User).where(User.company_id == company_id).order_by(User.username))
        .scalars()
        .all()
    )


@router.delete("/{company_id}")
def delete_company(company_id: int, db: Session = Depends(get_db)):
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(404, f"Company {company_id} not found")
    # Explicitly remove all tenant data (works whether or not the migrated DB
    # has FK cascades on the company_id columns).
    for model in (BoqLine, RFPLine, RFPDocument, CatalogItem, User):
        db.query(model).filter(model.company_id == company_id).delete(
            synchronize_session=False
        )
    db.delete(company)
    db.commit()
    return {"deleted": company_id}
