"""Weekly LLM-token quota per company (subscription enforcement).

Each company has a Plan with a weekly_token_limit. We track tokens used in the
current ISO week and reset every Monday. AI operations (RFP analysis, matching)
check the quota before running and record actual usage after.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import Company, Plan, TokenUsage, User

DEFAULT_PLANS = [
    ("Starter", 1_000_000),
    ("Professional", 3_000_000),
    ("Enterprise", 10_000_000),
]


def seed_plans() -> None:
    """Create the default plans once; assign the cheapest to any plan-less company."""
    with SessionLocal() as db:
        existing = db.execute(select(func.count(Plan.id))).scalar_one()
        if existing == 0:
            for name, limit in DEFAULT_PLANS:
                db.add(Plan(name=name, weekly_token_limit=limit))
            db.commit()
        starter = db.execute(
            select(Plan).order_by(Plan.weekly_token_limit).limit(1)
        ).scalar_one_or_none()
        if starter is not None:
            db.query(Company).filter(Company.plan_id.is_(None)).update(
                {Company.plan_id: starter.id}, synchronize_session=False
            )
            db.commit()


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def roll_week(company: Company) -> None:
    """Reset the company's weekly counter if we've moved into a new ISO week."""
    this_week = _monday(date.today())
    if company.week_start != this_week:
        company.week_start = this_week
        company.weekly_tokens_used = 0


def effective_used(company: Company) -> int:
    """Tokens used this week for display — 0 if the stored week has elapsed
    (no DB write; the real reset happens on the next AI operation)."""
    if company.week_start != _monday(date.today()):
        return 0
    return company.weekly_tokens_used or 0


def weekly_limit(company: Company) -> int:
    return company.plan.weekly_token_limit if company.plan else 0


def remaining(company: Company) -> int:
    return max(0, weekly_limit(company) - (company.weekly_tokens_used or 0))


def over_limit(db: Session, company: Company) -> bool:
    """True if the company has no allowance left this week (rolls the week first)."""
    roll_week(company)
    db.commit()
    return (company.weekly_tokens_used or 0) >= weekly_limit(company)


def record_tokens(
    db: Session,
    company: Company,
    tokens: int,
    user_id: int | None = None,
    kind: str = "",
) -> None:
    """Add tokens to the company's weekly counter AND log a per-user ledger row."""
    tokens = max(0, int(tokens))
    roll_week(company)
    company.weekly_tokens_used = (company.weekly_tokens_used or 0) + tokens
    if tokens > 0:
        db.add(
            TokenUsage(
                company_id=company.id, user_id=user_id, kind=kind, tokens=tokens
            )
        )
    db.commit()


def user_breakdown(db: Session, company_id: int) -> list[dict]:
    """Per-user token spend for a company: this week + all-time, from the ledger.

    Joins the ledger to users so even users with zero spend show up; users that
    were deleted (or the impersonating owner) appear under their stored name.
    """
    week_start = _monday(date.today())
    week_sum = func.coalesce(
        func.sum(
            case((TokenUsage.created_at >= week_start, TokenUsage.tokens), else_=0)
        ),
        0,
    ).label("week_tokens")
    all_sum = func.coalesce(func.sum(TokenUsage.tokens), 0).label("all_tokens")

    rows = db.execute(
        select(
            User.id,
            User.username,
            User.full_name,
            User.role,
            week_sum,
            all_sum,
        )
        .select_from(User)
        .outerjoin(
            TokenUsage,
            (TokenUsage.user_id == User.id) & (TokenUsage.company_id == company_id),
        )
        .where(User.company_id == company_id)
        .group_by(User.id, User.username, User.full_name, User.role)
        .order_by(week_sum.desc(), User.username)
    ).all()
    return [
        {
            "user_id": uid,
            "username": uname,
            "full_name": fname,
            "role": role,
            "tokens_this_week": int(wk),
            "tokens_all_time": int(al),
        }
        for uid, uname, fname, role, wk, al in rows
    ]


def my_usage(db: Session, company_id: int, user_id: int) -> dict:
    """A single user's own spend this week + all-time within a company."""
    week_start = _monday(date.today())
    base = select(func.coalesce(func.sum(TokenUsage.tokens), 0)).where(
        TokenUsage.company_id == company_id, TokenUsage.user_id == user_id
    )
    week = db.execute(base.where(TokenUsage.created_at >= week_start)).scalar_one()
    total = db.execute(base).scalar_one()
    return {"tokens_this_week": int(week), "tokens_all_time": int(total)}


class QuotaExceeded(Exception):
    """Raised when a company has exhausted its weekly token allowance."""
