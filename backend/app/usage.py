"""Weekly LLM-token quota per company (subscription enforcement).

Each company has a Plan with a weekly_token_limit. We track tokens used in the
current ISO week and reset every Monday. AI operations (RFP analysis, matching)
check the quota before running and record actual usage after.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from .config import settings
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


def billed_tokens(actual: int) -> int:
    """Tokens to CHARGE = actual consumed × the billing multiplier (markup)."""
    mult = settings.token_billing_multiplier or 1.0
    return int(round(max(0, int(actual)) * mult))


def record_tokens(
    db: Session,
    company: Company,
    tokens: int,
    user_id: int | None = None,
    kind: str = "",
) -> None:
    """Charge the company/user for an AI operation.

    `tokens` is the ACTUAL count consumed from the platform API key. We apply the
    billing markup, add the billed amount to the company's weekly quota, and log
    a ledger row keeping both the billed and actual figures (for reconciliation).
    """
    actual = max(0, int(tokens))
    billed = billed_tokens(actual)
    roll_week(company)
    company.weekly_tokens_used = (company.weekly_tokens_used or 0) + billed
    if actual > 0:
        db.add(
            TokenUsage(
                company_id=company.id,
                user_id=user_id,
                kind=kind,
                tokens=billed,
                actual_tokens=actual,
            )
        )
    db.commit()


def user_breakdown(db: Session, company_id: int) -> list[dict]:
    """Per-user token spend for a company: this week + all-time, from the ledger.

    Every company user is listed (even with zero spend). Usage attributed to a
    user who is NOT in the company list — the platform owner while impersonating,
    or a since-deleted user (user_id NULL) — is still shown so the per-user rows
    always reconcile with the company total. Nothing recorded is ever dropped.
    """
    week_start = _monday(date.today())
    week_sum = func.coalesce(
        func.sum(
            case((TokenUsage.created_at >= week_start, TokenUsage.tokens), else_=0)
        ),
        0,
    )
    all_sum = func.coalesce(func.sum(TokenUsage.tokens), 0)
    week_actual = func.coalesce(
        func.sum(
            case((TokenUsage.created_at >= week_start, TokenUsage.actual_tokens), else_=0)
        ),
        0,
    )

    # 1) Aggregate the ledger by the user who triggered each operation.
    agg = {
        uid: (int(wk), int(al), int(wa))
        for uid, wk, al, wa in db.execute(
            select(TokenUsage.user_id, week_sum, all_sum, week_actual)
            .where(TokenUsage.company_id == company_id)
            .group_by(TokenUsage.user_id)
        ).all()
    }

    # 2) All company users (so people with zero spend still appear).
    company_users = db.execute(
        select(User.id, User.username, User.full_name, User.role).where(
            User.company_id == company_id
        )
    ).all()
    known_ids = {u.id for u in company_users}

    # 3) Names for any ledger user_ids that aren't company members (e.g. owner).
    extra_ids = [uid for uid in agg if uid is not None and uid not in known_ids]
    extra_names = {
        u.id: u
        for u in (
            db.execute(
                select(User.id, User.username, User.full_name, User.role).where(
                    User.id.in_(extra_ids)
                )
            ).all()
            if extra_ids
            else []
        )
    }

    def _row(uid, uname, fname, role):
        wk, al, wa = agg.get(uid, (0, 0, 0))
        return {
            "user_id": uid,
            "username": uname,
            "full_name": fname,
            "role": role,
            "tokens_this_week": wk,
            "tokens_all_time": al,
            "actual_this_week": wa,
        }

    rows = [_row(u.id, u.username, u.full_name, u.role) for u in company_users]
    for uid in extra_ids:
        u = extra_names.get(uid)
        if u is not None:
            rows.append(_row(uid, u.username, u.full_name, u.role))
        else:  # user existed but was deleted after spending
            rows.append(_row(uid, "(deleted user)", None, "—"))
    if None in agg:  # ledger rows whose user was hard-removed (user_id NULL)
        rows.append(_row(None, "(former user)", None, "—"))

    rows.sort(key=lambda r: (-r["tokens_this_week"], (r["username"] or "")))
    return rows


def my_usage(db: Session, company_id: int, user_id: int) -> dict:
    """A single user's own spend this week + all-time within a company."""
    week_start = _monday(date.today())
    base = select(func.coalesce(func.sum(TokenUsage.tokens), 0)).where(
        TokenUsage.company_id == company_id, TokenUsage.user_id == user_id
    )
    week = db.execute(base.where(TokenUsage.created_at >= week_start)).scalar_one()
    total = db.execute(base).scalar_one()
    return {"tokens_this_week": int(week), "tokens_all_time": int(total)}


def _resolve_names(db: Session, company_id: int, ledger_ids: set) -> dict:
    """Map user_id -> (username, full_name, role) for every company member plus
    any non-member who appears in the ledger (the impersonating owner / deleted
    users). user_id None maps to a '(former user)' label."""
    names: dict = {}
    members = db.execute(
        select(User.id, User.username, User.full_name, User.role).where(
            User.company_id == company_id
        )
    ).all()
    member_ids = set()
    for u in members:
        names[u.id] = (u.username, u.full_name, u.role)
        member_ids.add(u.id)
    extra = [i for i in ledger_ids if i is not None and i not in member_ids]
    if extra:
        for u in db.execute(
            select(User.id, User.username, User.full_name, User.role).where(
                User.id.in_(extra)
            )
        ).all():
            names[u.id] = (u.username, u.full_name, u.role)
    # Anyone in the ledger we still couldn't name was hard-deleted.
    for i in ledger_ids:
        if i not in names:
            names[i] = ("(former user)" if i is None else "(deleted user)", None, "—")
    return names, member_ids


def weekly_history(db: Session, company_id: int, weeks: int = 8) -> dict:
    """Per-user BILLED token spend bucketed by ISO week (Monday-start) for the
    last `weeks` weeks, so a company can track who spends the most over time.

    Returns oldest→newest week dates and one row per user with a weekly array
    and a period total, sorted heaviest-spender first."""
    weeks = max(1, min(int(weeks), 52))
    this_monday = _monday(date.today())
    start = this_monday - timedelta(days=7 * (weeks - 1))
    week_list = [start + timedelta(days=7 * i) for i in range(weeks)]
    wk_index = {w: i for i, w in enumerate(week_list)}

    # Low volume (one row per AI op) → bucket in Python for exact Monday-week
    # alignment with the rest of the quota logic, regardless of DB timezone.
    ledger = db.execute(
        select(TokenUsage.user_id, TokenUsage.created_at, TokenUsage.tokens).where(
            TokenUsage.company_id == company_id, TokenUsage.created_at >= start
        )
    ).all()

    per_user: dict = {}
    ledger_ids: set = set()
    for uid, created, tokens in ledger:
        ledger_ids.add(uid)
        idx = wk_index.get(_monday(created.date()))
        if idx is None:
            continue
        per_user.setdefault(uid, [0] * weeks)[idx] += int(tokens or 0)

    names, member_ids = _resolve_names(db, company_id, ledger_ids)

    # Every current member is shown (even with zero spend in the window), plus
    # any non-member who actually spent.
    uids = list(member_ids | {i for i in ledger_ids})
    out_users = []
    for uid in uids:
        weekly = per_user.get(uid, [0] * weeks)
        uname, fname, role = names.get(uid, ("(unknown)", None, "—"))
        out_users.append(
            {
                "user_id": uid,
                "username": uname,
                "full_name": fname,
                "role": role,
                "total": sum(weekly),
                "weekly": weekly,
            }
        )
    out_users.sort(key=lambda r: (-r["total"], (r["username"] or "")))
    return {"weeks": [w.isoformat() for w in week_list], "users": out_users}


class QuotaExceeded(Exception):
    """Raised when a company has exhausted its weekly token allowance."""
