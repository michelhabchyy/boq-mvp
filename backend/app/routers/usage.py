"""Token-usage tracking endpoints.

Every company user can see their OWN live token spend (/usage/me). Company
admins (and the owner acting on a company) can see a per-user breakdown for the
whole company (/usage/users). Data comes from the TokenUsage ledger, written
whenever an AI operation (RFP analysis / matching) records its token cost.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import current_company_id, get_current_user
from ..db import get_db
from ..models import Company, User
from ..schemas import CompanyUsageOut, MyUsageOut, UserUsageOut
from ..usage import effective_used, my_usage, user_breakdown, weekly_limit

router = APIRouter(prefix="/usage", tags=["usage"])


def _company_totals(db: Session, cid: int) -> tuple[int, int, int]:
    company = db.get(Company, cid)
    limit = weekly_limit(company) if company else 0
    used = effective_used(company) if company else 0
    return limit, used, max(0, limit - used)


@router.get("/me", response_model=MyUsageOut)
def my_token_usage(
    db: Session = Depends(get_db),
    cid: int = Depends(current_company_id),
    user: User = Depends(get_current_user),
):
    mine = my_usage(db, cid, user.id)
    limit, used, remaining = _company_totals(db, cid)
    return MyUsageOut(
        user_id=user.id,
        tokens_this_week=mine["tokens_this_week"],
        tokens_all_time=mine["tokens_all_time"],
        company_weekly_limit=limit,
        company_weekly_used=used,
        company_weekly_remaining=remaining,
    )


@router.get("/users", response_model=CompanyUsageOut)
def company_token_usage(
    db: Session = Depends(get_db),
    cid: int = Depends(current_company_id),
    user: User = Depends(get_current_user),
):
    # Per-user breakdown is an admin-level view (owner acting on a company counts).
    if user.role not in ("admin", "owner"):
        raise HTTPException(403, "Company admin only")
    limit, used, remaining = _company_totals(db, cid)
    return CompanyUsageOut(
        company_weekly_limit=limit,
        company_weekly_used=used,
        company_weekly_remaining=remaining,
        users=[UserUsageOut(**row) for row in user_breakdown(db, cid)],
    )
