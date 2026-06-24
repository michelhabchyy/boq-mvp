"""Company dashboard — a single overview a contractor can open on the go to see
all their RFPs and the BoQ broken down by subcontractor, then download each.

Company-scoped (the owner can view it for any company via X-Company-Id).
"""

from fastapi import APIRouter, Depends
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from ..auth import current_company_id
from ..db import get_db
from ..models import BoqLine, CatalogItem, RFPDocument, RFPLine, Subcontractor
from ..schemas import (
    CompanyDashboardOut,
    DashRFP,
    DashSub,
    DashSubRFP,
    DashTotals,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

OWN = "Own (contractor)"  # label for BoQ lines not tied to a subcontractor


@router.get("", response_model=CompanyDashboardOut)
def company_dashboard(db: Session = Depends(get_db), cid: int = Depends(current_company_id)):
    docs = (
        db.execute(
            select(RFPDocument)
            .where(RFPDocument.company_id == cid)
            .order_by(RFPDocument.created_at.desc())
        )
        .scalars()
        .all()
    )
    fname_by_rfp = {d.id: d.filename for d in docs}

    scope_counts = dict(
        db.execute(
            select(RFPLine.rfp_id, func.count(RFPLine.id))
            .where(RFPLine.company_id == cid)
            .group_by(RFPLine.rfp_id)
        ).all()
    )

    # BoQ aggregates per RFP (count + total value).
    boq_by_rfp = {
        rid: (cnt, float(total or 0))
        for rid, cnt, total in db.execute(
            select(
                BoqLine.rfp_id,
                func.count(BoqLine.id),
                func.coalesce(func.sum(BoqLine.line_total), 0),
            )
            .where(BoqLine.company_id == cid)
            .group_by(BoqLine.rfp_id)
        ).all()
    }

    # Distinct subcontractors involved per RFP.
    subs_by_rfp: dict[int, set] = {}
    for rid, sname in db.execute(
        select(BoqLine.rfp_id, BoqLine.subcontractor)
        .where(BoqLine.company_id == cid)
        .distinct()
    ).all():
        subs_by_rfp.setdefault(rid, set()).add(sname or OWN)

    rfps = [
        DashRFP(
            id=d.id,
            filename=d.filename,
            status=d.status,
            created_at=d.created_at,
            scope_lines=scope_counts.get(d.id, 0),
            boq_lines=boq_by_rfp.get(d.id, (0, 0.0))[0],
            total_value=boq_by_rfp.get(d.id, (0, 0.0))[1],
            subcontractors=sorted(subs_by_rfp.get(d.id, set())),
        )
        for d in docs
    ]

    # --- per-subcontractor breakdown ---
    subs = (
        db.execute(
            select(Subcontractor)
            .where(Subcontractor.company_id == cid)
            .order_by(Subcontractor.name)
        )
        .scalars()
        .all()
    )
    cat_counts = dict(
        db.execute(
            select(CatalogItem.subcontractor_id, func.count(CatalogItem.id))
            .where(CatalogItem.company_id == cid)
            .group_by(CatalogItem.subcontractor_id)
        ).all()
    )
    agg_by_name = {
        (name or OWN): (cnt, float(total or 0), rfps_n)
        for name, cnt, total, rfps_n in db.execute(
            select(
                BoqLine.subcontractor,
                func.count(BoqLine.id),
                func.coalesce(func.sum(BoqLine.line_total), 0),
                func.count(distinct(BoqLine.rfp_id)),
            )
            .where(BoqLine.company_id == cid)
            .group_by(BoqLine.subcontractor)
        ).all()
    }
    # Per (subcontractor, RFP) so the UI can list & download each.
    rfps_by_name: dict[str, list[DashSubRFP]] = {}
    for name, rid, cnt, total in db.execute(
        select(
            BoqLine.subcontractor,
            BoqLine.rfp_id,
            func.count(BoqLine.id),
            func.coalesce(func.sum(BoqLine.line_total), 0),
        )
        .where(BoqLine.company_id == cid)
        .group_by(BoqLine.subcontractor, BoqLine.rfp_id)
    ).all():
        rfps_by_name.setdefault(name or OWN, []).append(
            DashSubRFP(
                rfp_id=rid,
                filename=fname_by_rfp.get(rid, f"RFP {rid}"),
                boq_lines=cnt,
                total_value=float(total or 0),
            )
        )

    dash_subs = []
    for s in subs:
        cnt, total, _ = agg_by_name.get(s.name, (0, 0.0, 0))
        dash_subs.append(
            DashSub(
                id=s.id,
                name=s.name,
                trade=s.trade,
                catalog_items=cat_counts.get(s.id, 0),
                boq_lines=cnt,
                total_value=total,
                rfps=rfps_by_name.get(s.name, []),
            )
        )
    # The contractor's own (non-sub) items, if any are matched.
    if OWN in agg_by_name:
        cnt, total, _ = agg_by_name[OWN]
        dash_subs.append(
            DashSub(
                id=None,
                name=OWN,
                catalog_items=cat_counts.get(None, 0),
                boq_lines=cnt,
                total_value=total,
                rfps=rfps_by_name.get(OWN, []),
            )
        )

    totals = DashTotals(
        rfps=len(docs),
        boq_lines=sum(c for c, _ in boq_by_rfp.values()),
        subcontractors=len(subs),
        total_value=sum(t for _, t in boq_by_rfp.values()),
    )
    return CompanyDashboardOut(totals=totals, rfps=rfps, subcontractors=dash_subs)
