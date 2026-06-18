"""BoQ line review actions: edit, approve, add, delete — company-scoped."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..auth import current_company_id
from ..db import get_db
from ..matching import _price
from ..models import BoqLine, CatalogItem, RFPLine
from ..schemas import BoqLineCreate, BoqLineOut, BoqLineUpdate

router = APIRouter(prefix="/boq-lines", tags=["boq"])


def _snapshot_from_catalog(bl: BoqLine, item: CatalogItem) -> None:
    """Copy catalog fields onto a BoQ line and reprice from cost + markup."""
    bl.catalog_item_id = item.id
    bl.item_code = item.item_code
    bl.description_en = item.description_en
    bl.description_ar = item.description_ar
    bl.unit = item.unit
    bl.brand = item.brand
    bl.subcontractor = item.subcontractor.name if item.subcontractor else None
    unit_cost, unit_price, _ = _price(
        item.material_cost, item.labour_cost, item.markup, bl.quantity
    )
    bl.unit_cost = unit_cost
    bl.markup = float(item.markup or 0)
    bl.unit_price = unit_price


def _owned_line(db: Session, line_id: int, cid: int) -> BoqLine:
    bl = db.get(BoqLine, line_id)
    if bl is None or bl.company_id != cid:
        raise HTTPException(status_code=404, detail=f"BoQ line {line_id} not found")
    return bl


def _owned_catalog_item(db: Session, item_id: int, cid: int) -> CatalogItem:
    item = db.get(CatalogItem, item_id)
    if item is None or item.company_id != cid:
        raise HTTPException(404, f"Catalog item {item_id} not found")
    return item


@router.patch("/{line_id}", response_model=BoqLineOut)
def update_boq_line(
    line_id: int,
    payload: BoqLineUpdate,
    db: Session = Depends(get_db),
    cid: int = Depends(current_company_id),
):
    bl = _owned_line(db, line_id, cid)
    fields = payload.model_dump(exclude_unset=True)

    if "catalog_item_id" in fields:
        new_id = fields.pop("catalog_item_id")
        if new_id is None:
            bl.catalog_item_id = None
            bl.item_code = bl.description_en = bl.description_ar = None
            bl.unit_cost = bl.markup = bl.unit_price = 0
            bl.needs_review = True
        else:
            _snapshot_from_catalog(bl, _owned_catalog_item(db, new_id, cid))

    for key, value in fields.items():
        setattr(bl, key, value)

    bl.line_total = round(float(bl.quantity or 0) * float(bl.unit_price or 0), 2)
    db.commit()
    db.refresh(bl)
    return bl


@router.post("", response_model=BoqLineOut)
def add_boq_line(
    payload: BoqLineCreate,
    db: Session = Depends(get_db),
    cid: int = Depends(current_company_id),
):
    scope = db.get(RFPLine, payload.rfp_line_id)
    if scope is None or scope.company_id != cid:
        raise HTTPException(404, f"Scope line {payload.rfp_line_id} not found")
    item = _owned_catalog_item(db, payload.catalog_item_id, cid)

    bl = BoqLine(
        company_id=cid,
        rfp_id=scope.rfp_id,
        rfp_line_id=scope.id,
        quantity=payload.quantity,
        confidence=1.0,  # manually added by a human
        needs_review=False,
    )
    _snapshot_from_catalog(bl, item)
    bl.line_total = round(float(bl.quantity) * float(bl.unit_price), 2)
    db.add(bl)
    db.commit()
    db.refresh(bl)
    return bl


@router.delete("/{line_id}")
def delete_boq_line(line_id: int, db: Session = Depends(get_db), cid: int = Depends(current_company_id)):
    db.delete(_owned_line(db, line_id, cid))
    db.commit()
    return {"deleted": line_id}


@router.post("/approve-all")
def approve_all(
    rfp_id: int = Query(..., description="Approve every BoQ line for this RFP"),
    db: Session = Depends(get_db),
    cid: int = Depends(current_company_id),
):
    updated = (
        db.query(BoqLine)
        .filter(BoqLine.rfp_id == rfp_id, BoqLine.company_id == cid)
        .update({BoqLine.approved: True}, synchronize_session=False)
    )
    db.commit()
    return {"approved": updated}
