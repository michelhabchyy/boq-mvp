"""BoQ export endpoint (Stage 6): download a bilingual Excel BoQ."""

import re

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import current_company_id
from ..db import get_db
from ..exporter import build_boq_workbook
from ..models import BoqLine, RFPDocument, RFPLine, Subcontractor

router = APIRouter(prefix="/output", tags=["output"])

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/rfp/{rfp_id}/boq.xlsx")
def export_boq(
    rfp_id: int,
    include_unapproved: bool = Query(
        False, description="Include lines that haven't been approved yet"
    ),
    subcontractor_id: int | None = Query(
        None, description="Export only the BoQ lines awarded to this subcontractor"
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
    sub_name = None
    if subcontractor_id is not None:
        sub = db.get(Subcontractor, subcontractor_id)
        if sub is None or sub.company_id != cid:
            raise HTTPException(404, f"Subcontractor {subcontractor_id} not found")
        sub_name = sub.name
        boq_q = boq_q.where(BoqLine.subcontractor == sub_name)
    boq_lines = db.execute(boq_q).scalars().all()

    if not boq_lines:
        raise HTTPException(
            status_code=400,
            detail="No BoQ lines to export for this selection. Approve lines first, "
            "or pass ?include_unapproved=true.",
        )

    # Group by scope line, preserving scope order; skip empty scope lines.
    by_line: dict[int, list[BoqLine]] = {}
    for bl in boq_lines:
        by_line.setdefault(bl.rfp_line_id, []).append(bl)
    groups = [(ln, by_line[ln.id]) for ln in lines if ln.id in by_line]

    content = build_boq_workbook(doc.filename, groups)

    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", doc.filename.rsplit(".", 1)[0]) or "boq"
    sub_tag = ""
    if sub_name:
        sub_tag = "_" + (re.sub(r"[^A-Za-z0-9_.-]", "_", sub_name) or "sub")
    fname = f"BoQ_{rfp_id}_{safe}{sub_tag}.xlsx"
    return Response(
        content=content,
        media_type=XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
