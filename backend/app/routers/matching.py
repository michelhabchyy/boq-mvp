"""Matching endpoints: run the engine for an RFP, fetch the proposed BoQ."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import current_company_id
from ..config import settings
from ..db import get_db
from ..matching import run_matching_for_rfp
from ..usage import QuotaExceeded
from ..models import BoqLine, RFPDocument, RFPLine
from ..schemas import (
    BoqLineOut,
    MatchRunResult,
    ScopeLineOut,
    ScopeLineWithMatches,
)

router = APIRouter(prefix="/matching", tags=["matching"])


def _group_by_scope_line(
    lines: list[RFPLine], boq_lines: list[BoqLine]
) -> list[ScopeLineWithMatches]:
    by_line: dict[int, list[BoqLine]] = {}
    for bl in boq_lines:
        by_line.setdefault(bl.rfp_line_id, []).append(bl)
    grouped = []
    for line in lines:
        grouped.append(
            ScopeLineWithMatches(
                scope_line=ScopeLineOut.model_validate(line),
                boq_lines=[
                    BoqLineOut.model_validate(bl) for bl in by_line.get(line.id, [])
                ],
            )
        )
    return grouped


def _owned_rfp(db: Session, rfp_id: int, cid: int) -> RFPDocument:
    doc = db.get(RFPDocument, rfp_id)
    if doc is None or doc.company_id != cid:
        raise HTTPException(status_code=404, detail=f"RFP {rfp_id} not found")
    return doc


@router.post("/run/{rfp_id}", response_model=MatchRunResult)
def run_matching(
    rfp_id: int,
    rfp_line_id: int | None = Query(
        None, description="Match only this scope line (default: all lines)"
    ),
    db: Session = Depends(get_db),
    cid: int = Depends(current_company_id),
):
    _owned_rfp(db, rfp_id, cid)
    try:
        created = run_matching_for_rfp(db, rfp_id, cid, rfp_line_id)
    except QuotaExceeded as e:
        raise HTTPException(status_code=402, detail=str(e))

    lines = (
        db.execute(
            select(RFPLine)
            .where(RFPLine.rfp_id == rfp_id, RFPLine.company_id == cid)
            .order_by(RFPLine.line_no)
        )
        .scalars()
        .all()
    )
    matched_line_ids = {bl.rfp_line_id for bl in created}
    return MatchRunResult(
        rfp_id=rfp_id,
        provider=settings.llm_provider,
        scope_lines_matched=len(matched_line_ids),
        boq_lines_created=len(created),
        flagged_for_review=sum(1 for bl in created if bl.needs_review),
        results=_group_by_scope_line(
            [ln for ln in lines if ln.id in matched_line_ids], created
        ),
    )


@router.get("/rfp/{rfp_id}", response_model=list[ScopeLineWithMatches])
def get_matches(rfp_id: int, db: Session = Depends(get_db), cid: int = Depends(current_company_id)):
    _owned_rfp(db, rfp_id, cid)
    lines = (
        db.execute(
            select(RFPLine)
            .where(RFPLine.rfp_id == rfp_id, RFPLine.company_id == cid)
            .order_by(RFPLine.line_no)
        )
        .scalars()
        .all()
    )
    boq_lines = (
        db.execute(
            select(BoqLine).where(BoqLine.rfp_id == rfp_id, BoqLine.company_id == cid)
        )
        .scalars()
        .all()
    )
    return _group_by_scope_line(lines, boq_lines)
