"""Company capability profile: a Fields → Services → Sub-services tree.

Sub-services are flagged in-house or external. This defines what the company
does and feeds the Field/Service selectors on projects. Company-scoped: admins
edit; reviewers and the owner-acting can read. Every mutation returns the full
refreshed tree so the client stays in sync with one response.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import admin_company_id, current_company_id
from ..db import get_db
from ..models import CapabilityField, CapabilityService, CapabilitySubService
from ..schemas import (
    CapabilityFieldOut,
    CapabilityServiceOut,
    CapabilitySubServiceOut,
    NameIn,
    NameUpdate,
    SubServiceIn,
    SubServiceUpdate,
)

router = APIRouter(prefix="/capabilities", tags=["capabilities"])


def _tree(db: Session, cid: int) -> list[CapabilityFieldOut]:
    fields = db.execute(
        select(CapabilityField).where(CapabilityField.company_id == cid).order_by(CapabilityField.name)
    ).scalars().all()
    services = db.execute(
        select(CapabilityService).where(CapabilityService.company_id == cid).order_by(CapabilityService.name)
    ).scalars().all()
    subs = db.execute(
        select(CapabilitySubService).where(CapabilitySubService.company_id == cid).order_by(CapabilitySubService.name)
    ).scalars().all()

    subs_by_service: dict[int, list] = {}
    for s in subs:
        subs_by_service.setdefault(s.service_id, []).append(
            CapabilitySubServiceOut(id=s.id, name=s.name, in_house=s.in_house)
        )
    svcs_by_field: dict[int, list] = {}
    for sv in services:
        svcs_by_field.setdefault(sv.field_id, []).append(
            CapabilityServiceOut(id=sv.id, name=sv.name, sub_services=subs_by_service.get(sv.id, []))
        )
    return [
        CapabilityFieldOut(id=fld.id, name=fld.name, services=svcs_by_field.get(fld.id, []))
        for fld in fields
    ]


def _field(db, fid, cid) -> CapabilityField:
    o = db.get(CapabilityField, fid)
    if o is None or o.company_id != cid:
        raise HTTPException(404, "Field not found")
    return o


def _service(db, sid, cid) -> CapabilityService:
    o = db.get(CapabilityService, sid)
    if o is None or o.company_id != cid:
        raise HTTPException(404, "Service not found")
    return o


def _sub(db, ssid, cid) -> CapabilitySubService:
    o = db.get(CapabilitySubService, ssid)
    if o is None or o.company_id != cid:
        raise HTTPException(404, "Sub-service not found")
    return o


def _require_name(name: str) -> str:
    name = (name or "").strip()
    if not name:
        raise HTTPException(400, "Name is required")
    return name


@router.get("", response_model=list[CapabilityFieldOut])
def get_tree(db: Session = Depends(get_db), cid: int = Depends(current_company_id)):
    return _tree(db, cid)


# --- fields ---
@router.post("/fields", response_model=list[CapabilityFieldOut])
def add_field(payload: NameIn, db: Session = Depends(get_db), cid: int = Depends(admin_company_id)):
    db.add(CapabilityField(company_id=cid, name=_require_name(payload.name)))
    db.commit()
    return _tree(db, cid)


@router.patch("/fields/{field_id}", response_model=list[CapabilityFieldOut])
def rename_field(field_id: int, payload: NameUpdate, db: Session = Depends(get_db), cid: int = Depends(admin_company_id)):
    _field(db, field_id, cid).name = _require_name(payload.name)
    db.commit()
    return _tree(db, cid)


@router.delete("/fields/{field_id}", response_model=list[CapabilityFieldOut])
def delete_field(field_id: int, db: Session = Depends(get_db), cid: int = Depends(admin_company_id)):
    db.delete(_field(db, field_id, cid))
    db.commit()
    return _tree(db, cid)


# --- services ---
@router.post("/fields/{field_id}/services", response_model=list[CapabilityFieldOut])
def add_service(field_id: int, payload: NameIn, db: Session = Depends(get_db), cid: int = Depends(admin_company_id)):
    _field(db, field_id, cid)
    db.add(CapabilityService(company_id=cid, field_id=field_id, name=_require_name(payload.name)))
    db.commit()
    return _tree(db, cid)


@router.patch("/services/{service_id}", response_model=list[CapabilityFieldOut])
def rename_service(service_id: int, payload: NameUpdate, db: Session = Depends(get_db), cid: int = Depends(admin_company_id)):
    _service(db, service_id, cid).name = _require_name(payload.name)
    db.commit()
    return _tree(db, cid)


@router.delete("/services/{service_id}", response_model=list[CapabilityFieldOut])
def delete_service(service_id: int, db: Session = Depends(get_db), cid: int = Depends(admin_company_id)):
    db.delete(_service(db, service_id, cid))
    db.commit()
    return _tree(db, cid)


# --- sub-services ---
@router.post("/services/{service_id}/subservices", response_model=list[CapabilityFieldOut])
def add_sub(service_id: int, payload: SubServiceIn, db: Session = Depends(get_db), cid: int = Depends(admin_company_id)):
    _service(db, service_id, cid)
    db.add(
        CapabilitySubService(
            company_id=cid, service_id=service_id, name=_require_name(payload.name), in_house=payload.in_house
        )
    )
    db.commit()
    return _tree(db, cid)


@router.patch("/subservices/{sub_id}", response_model=list[CapabilityFieldOut])
def update_sub(sub_id: int, payload: SubServiceUpdate, db: Session = Depends(get_db), cid: int = Depends(admin_company_id)):
    sub = _sub(db, sub_id, cid)
    if payload.name is not None:
        sub.name = _require_name(payload.name)
    if payload.in_house is not None:
        sub.in_house = payload.in_house
    db.commit()
    return _tree(db, cid)


@router.delete("/subservices/{sub_id}", response_model=list[CapabilityFieldOut])
def delete_sub(sub_id: int, db: Session = Depends(get_db), cid: int = Depends(admin_company_id)):
    db.delete(_sub(db, sub_id, cid))
    db.commit()
    return _tree(db, cid)
