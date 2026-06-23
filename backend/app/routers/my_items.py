"""Subcontractor self-service item list. A subcontractor login can only see and
edit its OWN catalog items (company catalog rows tagged with its subcontractor_id).
Items auto-embed on save so they're immediately matchable by the contractor."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..auth import require_subcontractor
from ..db import get_db
from ..embeddings import build_embedding_text, get_embedder
from ..models import CatalogItem, User
from ..schemas import CatalogItemIn, CatalogItemOut, CatalogItemPatch

router = APIRouter(prefix="/my-items", tags=["my-items"])


def _embed(item: CatalogItem) -> None:
    text = build_embedding_text(
        item.description_en,
        item.description_ar,
        item.industry,
        item.category,
        item.brand,
        item.model_number,
    )
    item.embedding = get_embedder().embed_documents([text])[0] if text else None


# Editing any of these changes the embedding text, so we re-embed on change.
_EMBED_FIELDS = {"description_en", "description_ar", "industry", "category", "brand", "model_number"}


def _mine(db: Session, item_id: int, me: User) -> CatalogItem:
    item = db.get(CatalogItem, item_id)
    if item is None or item.subcontractor_id != me.subcontractor_id:
        raise HTTPException(404, f"Item {item_id} not found")
    return item


@router.get("", response_model=list[CatalogItemOut])
def list_my_items(
    q: str | None = Query(None),
    db: Session = Depends(get_db),
    me: User = Depends(require_subcontractor),
):
    stmt = (
        select(CatalogItem)
        .where(CatalogItem.subcontractor_id == me.subcontractor_id)
        .order_by(CatalogItem.item_code)
    )
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                CatalogItem.item_code.ilike(like),
                CatalogItem.description_ar.ilike(like),
                CatalogItem.description_en.ilike(like),
            )
        )
    return db.execute(stmt).scalars().all()


@router.post("", response_model=CatalogItemOut)
def create_my_item(
    payload: CatalogItemIn, db: Session = Depends(get_db), me: User = Depends(require_subcontractor)
):
    exists = db.execute(
        select(CatalogItem).where(
            CatalogItem.subcontractor_id == me.subcontractor_id,
            CatalogItem.item_code == payload.item_code,
        )
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(409, f"Item code '{payload.item_code}' already exists")
    item = CatalogItem(
        **payload.model_dump(), company_id=me.company_id, subcontractor_id=me.subcontractor_id
    )
    _embed(item)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{item_id}", response_model=CatalogItemOut)
def update_my_item(
    item_id: int,
    payload: CatalogItemPatch,
    db: Session = Depends(get_db),
    me: User = Depends(require_subcontractor),
):
    item = _mine(db, item_id, me)
    fields = payload.model_dump(exclude_unset=True)
    if "item_code" in fields and fields["item_code"] != item.item_code:
        clash = db.execute(
            select(CatalogItem).where(
                CatalogItem.subcontractor_id == me.subcontractor_id,
                CatalogItem.item_code == fields["item_code"],
            )
        ).scalar_one_or_none()
        if clash:
            raise HTTPException(409, f"Item code '{fields['item_code']}' already exists")
    for k, v in fields.items():
        setattr(item, k, v)
    if _EMBED_FIELDS & fields.keys():
        _embed(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}")
def delete_my_item(item_id: int, db: Session = Depends(get_db), me: User = Depends(require_subcontractor)):
    db.delete(_mine(db, item_id, me))
    db.commit()
    return {"deleted": item_id}
