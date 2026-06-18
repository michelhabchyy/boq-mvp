"""BoQ export endpoint (Stage 6): download a bilingual Excel BoQ."""

import re

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import current_company_id
from ..db import get_db
from ..exporter import build_boq_workbook
from ..models import BoqLine, RFPDocument, RFPLine

router = APIRouter(prefix="/output", tags=["output"])

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/rfp/{rfp_id}/boq.xlsx")
def export_boq(
    rfp_id: int,
    include_unapproved: bool = Query(
        False, description="Include lines that haven't been approved yet"
    ),
    db: Session = Depends(get_db),
    cid: int = Depends(current_company_id),
):
    doc = db.get(RFPDocument, rfp_id)
    if doc is None or doc.company_id != cid:
        raise HTTPException(status_code=404, detail=f"RFP {rfp_id} not found")

    lines = (
        db.execute(
            select(RFPLine)
            .where(RFPLine.rfp_id == rfp_id, RFPLine.company_id == cid)
            .order_by(RFPLine.line_no)
        )
        .scalars()
        .all()
    )

    boq_q = select(BoqLine).where(BoqLine.rfp_id == rfp_id, BoqLine.company_id == cid)
    if not include_unapproved:
        boq_q = boq_q.where(BoqLine.approved.is_(True))
    boq_lines = db.execute(boq_q).scalars().all()

    if not boq_lines:
        raise HTTPException(
            status_code=400,
            detail="No approved BoQ lines to export. Approve lines first, "
            "or pass ?include_unapproved=true.",
        )

    # Group by scope line, preserving scope order; skip empty scope lines.
    by_line: dict[int, list[BoqLine]] = {}
    for bl in boq_lines:
        by_line.setdefault(bl.rfp_line_id, []).append(bl)
    groups = [(ln, by_line[ln.id]) for ln in lines if ln.id in by_line]

    content = build_boq_workbook(doc.filename, groups)

    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", doc.filename.rsplit(".", 1)[0]) or "boq"
    fname = f"BoQ_{rfp_id}_{safe}.xlsx"
    return Response(
        content=content,
        media_type=XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
