"""Subscription plan management — platform OWNER only."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import require_owner
from ..db import get_db
from ..models import Plan
from ..schemas import PlanOut, PlanUpdate

router = APIRouter(prefix="/plans", tags=["plans"], dependencies=[Depends(require_owner)])


@router.get("", response_model=list[PlanOut])
def list_plans(db: Session = Depends(get_db)):
    return db.execute(select(Plan).order_by(Plan.weekly_token_limit)).scalars().all()


@router.patch("/{plan_id}", response_model=PlanOut)
def update_plan(plan_id: int, payload: PlanUpdate, db: Session = Depends(get_db)):
    plan = db.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(404, f"Plan {plan_id} not found")
    fields = payload.model_dump(exclude_unset=True)
    if "weekly_token_limit" in fields and fields["weekly_token_limit"] < 0:
        raise HTTPException(400, "weekly_token_limit must be >= 0")
    for k, v in fields.items():
        setattr(plan, k, v)
    db.commit()
    db.refresh(plan)
    return plan
