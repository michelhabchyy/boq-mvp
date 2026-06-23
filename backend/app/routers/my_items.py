"""Subcontractor self-service item list. A subcontractor login can only see and
edit its OWN catalog items (company catalog rows tagged with its subcontractor_id).
Items auto-embed on save so they're immediately matchable by the contractor."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import require_subcontractor
from ..db import get_db
from ..embeddings import build_embedding_text, get_embedder
from ..item_utils import (
    build_items_workbook,
    generate_item_code,
    log_item_change,
    summarize_changes,
)
from ..models import CatalogItem, Company, ItemAudit, User
from ..schemas import CatalogItemIn, CatalogItemOut, CatalogItemPatch, ItemAuditOut
from .catalog import XLSX_MEDIA, build_search_filter

router = APIRouter(prefix="/my-items", tags=["my-items"])


def _edit_blocked_until(last_edited_at: datetime | None) -> datetime | None:
    """If the item was already edited THIS calendar month, return the moment the
    next edit becomes allowed (start of next month). Otherwise None (allowed)."""
    if last_edited_at is None:
        return None
    now = datetime.now(timezone.utc)
    le = last_edited_at
    if le.tzinfo is None:  # stored naive → treat as UTC
        le = le.replace(tzinfo=timezone.utc)
    if (le.year, le.month) != (now.year, now.month):
        return None
    # First day of next month, 00:00 UTC.
    year = now.year + (1 if now.month == 12 else 0)
    month = 1 if now.month == 12 else now.month + 1
    return datetime(year, month, 1, tzinfo=timezone.utc)


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
    search = build_search_filter(q)
    if search is not None:
        stmt = stmt.where(search)
    return db.execute(stmt).scalars().all()


@router.post("", response_model=CatalogItemOut)
def create_my_item(
    payload: CatalogItemIn, db: Session = Depends(get_db), me: User = Depends(require_subcontractor)
):
    company = db.get(Company, me.company_id)
    item = CatalogItem(
        **payload.model_dump(),
        company_id=me.company_id,
        subcontractor_id=me.subcontractor_id,
        item_code=generate_item_code(db, company),
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
    # One edit per calendar month per item.
    blocked_until = _edit_blocked_until(item.last_edited_at)
    if blocked_until is not None:
        raise HTTPException(
            status_code=429,
            detail=(
                "You can edit each item only once per month. This item was "
                "already edited this month — you can edit it again on "
                f"{blocked_until:%d %B %Y}."
            ),
        )
    fields = payload.model_dump(exclude_unset=True)
    summary = summarize_changes(item, fields)
    for k, v in fields.items():
        setattr(item, k, v)
    if _EMBED_FIELDS & fields.keys():
        _embed(item)
    item.last_edited_at = datetime.now(timezone.utc)
    if summary:
        log_item_change(db, item, "edited", me, summary)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}")
def delete_my_item(item_id: int, db: Session = Depends(get_db), me: User = Depends(require_subcontractor)):
    item = _mine(db, item_id, me)
    log_item_change(db, item, "deleted", me)
    db.delete(item)
    db.commit()
    return {"deleted": item_id}


@router.get("/history", response_model=list[ItemAuditOut])
def my_items_history(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    me: User = Depends(require_subcontractor),
):
    """Edit/delete history for THIS subcontractor's own items (newest first)."""
    return (
        db.execute(
            select(ItemAudit)
            .where(ItemAudit.subcontractor_id == me.subcontractor_id)
            .order_by(ItemAudit.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )


@router.get("/export")
def export_my_items(db: Session = Depends(get_db), me: User = Depends(require_subcontractor)):
    """Download this subcontractor's items (all filled fields) as an .xlsx sheet."""
    items = (
        db.execute(
            select(CatalogItem)
            .where(CatalogItem.subcontractor_id == me.subcontractor_id)
            .order_by(CatalogItem.item_code)
        )
        .scalars()
        .all()
    )
    data = build_items_workbook(items, title="My Items")
    return Response(
        content=data,
        media_type=XLSX_MEDIA,
        headers={"Content-Disposition": 'attachment; filename="my-items.xlsx"'},
    )
