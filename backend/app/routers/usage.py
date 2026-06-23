"""Token-usage tracking endpoints.

Every company user can see their OWN live token spend (/usage/me). Company
admins (and the owner acting on a company) can see a per-user breakdown for the
whole company (/usage/users). Data comes from the TokenUsage ledger, written
whenever an AI operation (RFP analysis / matching) records its token cost.

Token figures shown to companies are the BILLED amount only. The billing markup
(actual consumption vs billed, and the multiplier itself) is a platform secret —
it is exposed ONLY to the platform owner, never to a company's own admins/users,
even via direct API calls.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..auth import current_company_id, get_current_user
from ..config import settings
from ..db import get_db
from ..models import Company, User
from ..schemas import (
    CompanyUsageOut,
    MyUsageOut,
    UsageHistoryOut,
    UserUsageOut,
    UserWeeklyOut,
)
from ..usage import (
    effective_used,
    my_usage,
    user_breakdown,
    weekly_history,
    weekly_limit,
)

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
    # Only the platform owner is ever told the markup; companies see 1.0.
    multiplier = settings.token_billing_multiplier if user.role == "owner" else 1.0
    return MyUsageOut(
        user_id=user.id,
        tokens_this_week=mine["tokens_this_week"],
        tokens_all_time=mine["tokens_all_time"],
        company_weekly_limit=limit,
        company_weekly_used=used,
        company_weekly_remaining=remaining,
        billing_multiplier=multiplier,
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
    is_owner = user.role == "owner"
    limit, used, remaining = _company_totals(db, cid)
    rows = user_breakdown(db, cid)
    if not is_owner:
        # Never leak the real (pre-markup) consumption to a company: mask the
        # actual figure to match the billed one so no markup can be inferred.
        for r in rows:
            r["actual_this_week"] = r["tokens_this_week"]
    return CompanyUsageOut(
        company_weekly_limit=limit,
        company_weekly_used=used,
        company_weekly_remaining=remaining,
        billing_multiplier=settings.token_billing_multiplier if is_owner else 1.0,
        users=[UserUsageOut(**row) for row in rows],
    )


@router.get("/history", response_model=UsageHistoryOut)
def company_usage_history(
    weeks: int = Query(8, ge=1, le=52, description="How many recent weeks to return"),
    db: Session = Depends(get_db),
    cid: int = Depends(current_company_id),
    user: User = Depends(get_current_user),
):
    """Weekly per-user spend history (billed tokens) for the company — admins and
    the owner-acting only. Lets a company see who spends the most over time."""
    if user.role not in ("admin", "owner"):
        raise HTTPException(403, "Company admin only")
    data = weekly_history(db, cid, weeks)
    return UsageHistoryOut(
        weeks=data["weeks"],
        users=[UserWeeklyOut(**u) for u in data["users"]],
    )
