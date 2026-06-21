"""Weekly LLM-token quota per company (subscription enforcement).

Each company has a Plan with a weekly_token_limit. We track tokens used in the
current ISO week and reset every Monday. AI operations (RFP analysis, matching)
check the quota before running and record actual usage after.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import Company, Plan

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


def record_tokens(db: Session, company: Company, tokens: int) -> None:
    roll_week(company)
    company.weekly_tokens_used = (company.weekly_tokens_used or 0) + max(0, int(tokens))
    db.commit()


class QuotaExceeded(Exception):
    """Raised when a company has exhausted its weekly token allowance."""
