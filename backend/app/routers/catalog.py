"""Catalog endpoints — all scoped to the caller's company."""

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ..auth import admin_company_id, current_company_id, require_owner
from ..catalog_loader import parse_catalog_file
from ..config import settings
from ..db import get_db
from ..embeddings import build_embedding_text, get_embedder
from ..models import CatalogItem
from ..schemas import (
    CatalogItemIn,
    CatalogItemOut,
    CatalogItemPatch,
    CatalogUploadResult,
    EmbeddingBuildResult,
    EmbeddingStatus,
    RowError,
    SearchHit,
)

router = APIRouter(prefix="/catalog", tags=["catalog"])


def _embed_item(item: CatalogItem) -> None:
    """(Re)generate this item's embedding from its descriptions, in place."""
    text = build_embedding_text(item.description_en, item.description_ar)
    item.embedding = get_embedder().embed_documents([text])[0] if text else None


def _owned(db: Session, item_id: int, cid: int) -> CatalogItem:
    item = db.get(CatalogItem, item_id)
    if item is None or item.company_id != cid:
        raise HTTPException(404, f"Catalog item {item_id} not found")
    return item


@router.post("/upload", response_model=CatalogUploadResult)
async def upload_catalog(
    file: UploadFile,
    replace: bool = Query(False, description="Wipe the catalog before loading"),
    skip_invalid: bool = Query(
        False, description="Load valid rows and skip bad ones instead of rejecting the file"
    ),
    db: Session = Depends(get_db),
    cid: int = Depends(admin_company_id),
):
    content = await file.read()
    try:
        parsed = parse_catalog_file(file.filename or "", content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if parsed.missing_columns:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required column(s): {', '.join(parsed.missing_columns)}",
        )

    row_errors = [RowError(row=r, errors=errs) for r, errs in parsed.row_errors]
    if parsed.row_errors and not skip_invalid:
        raise HTTPException(
            status_code=422,
            detail={
                "message": f"{len(parsed.row_errors)} invalid row(s). "
                "Fix them or retry with ?skip_invalid=true.",
                "row_errors": [e.model_dump() for e in row_errors],
            },
        )

    if replace:
        db.query(CatalogItem).filter(CatalogItem.company_id == cid).delete()

    if parsed.valid_rows:
        rows = [{**r, "company_id": cid} for r in parsed.valid_rows]
        stmt = pg_insert(CatalogItem).values(rows)
        update_cols = {
            c.name: stmt.excluded[c.name]
            for c in CatalogItem.__table__.columns
            if c.name not in ("id", "item_code", "company_id")
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=["company_id", "item_code"], set_=update_cols
        )
        db.execute(stmt)

    db.commit()
    return CatalogUploadResult(
        loaded=len(parsed.valid_rows),
        duplicates_in_file=parsed.duplicates_in_file,
        skipped=len(parsed.row_errors),
        replaced_existing=replace,
        row_errors=row_errors,
    )


@router.post("/item", response_model=CatalogItemOut)
def create_item(
    payload: CatalogItemIn,
    db: Session = Depends(get_db),
    cid: int = Depends(admin_company_id),
):
    exists = db.execute(
        select(CatalogItem).where(
            CatalogItem.company_id == cid, CatalogItem.item_code == payload.item_code
        )
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(409, f"Item code '{payload.item_code}' already exists")
    item = CatalogItem(**payload.model_dump(), company_id=cid)
    _embed_item(item)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{item_id}", response_model=CatalogItemOut)
def update_item(
    item_id: int,
    payload: CatalogItemPatch,
    db: Session = Depends(get_db),
    cid: int = Depends(admin_company_id),
):
    item = _owned(db, item_id, cid)
    fields = payload.model_dump(exclude_unset=True)
    if "item_code" in fields and fields["item_code"] != item.item_code:
        clash = db.execute(
            select(CatalogItem).where(
                CatalogItem.company_id == cid,
                CatalogItem.item_code == fields["item_code"],
            )
        ).scalar_one_or_none()
        if clash:
            raise HTTPException(409, f"Item code '{fields['item_code']}' already exists")
    for key, value in fields.items():
        setattr(item, key, value)
    if "description_en" in fields or "description_ar" in fields:
        _embed_item(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/item/{item_id}")
def delete_item(
    item_id: int, db: Session = Depends(get_db), cid: int = Depends(admin_company_id)
):
    item = _owned(db, item_id, cid)
    db.delete(item)
    db.commit()
    return {"deleted": item_id}


@router.get("", response_model=list[CatalogItemOut])
def list_catalog(
    q: str | None = Query(None, description="Filter by item_code or description (AR/EN)"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    cid: int = Depends(current_company_id),
):
    stmt = select(CatalogItem).where(CatalogItem.company_id == cid).order_by(CatalogItem.item_code)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                CatalogItem.item_code.ilike(like),
                CatalogItem.description_ar.ilike(like),
                CatalogItem.description_en.ilike(like),
            )
        )
    return db.execute(stmt.limit(limit).offset(offset)).scalars().all()


@router.get("/count")
def catalog_count(db: Session = Depends(get_db), cid: int = Depends(current_company_id)):
    return {
        "count": db.execute(
            select(func.count(CatalogItem.id)).where(CatalogItem.company_id == cid)
        ).scalar_one()
    }


@router.delete("")
def clear_catalog(db: Session = Depends(get_db), cid: int = Depends(admin_company_id)):
    deleted = db.query(CatalogItem).filter(CatalogItem.company_id == cid).delete()
    db.commit()
    return {"deleted": deleted}


# --- embeddings + semantic search (scoped) ----------------------------------


@router.get("/embeddings/status", response_model=EmbeddingStatus)
def embedding_status(db: Session = Depends(get_db), cid: int = Depends(current_company_id)):
    total = db.execute(
        select(func.count(CatalogItem.id)).where(CatalogItem.company_id == cid)
    ).scalar_one()
    embedded = db.execute(
        select(func.count(CatalogItem.id)).where(
            CatalogItem.company_id == cid, CatalogItem.embedding.isnot(None)
        )
    ).scalar_one()
    return EmbeddingStatus(
        provider=settings.embed_provider,
        dim=settings.embed_dim,
        total_items=total,
        embedded_items=embedded,
    )


@router.post("/embeddings/build", response_model=EmbeddingBuildResult)
def build_embeddings(
    force: bool = Query(False, description="Re-embed every item, not just missing ones"),
    db: Session = Depends(get_db),
    cid: int = Depends(admin_company_id),
):
    embedder = get_embedder()
    stmt = select(CatalogItem).where(CatalogItem.company_id == cid)
    if not force:
        stmt = stmt.where(CatalogItem.embedding.is_(None))
    items = db.execute(stmt).scalars().all()
    if items:
        texts = [build_embedding_text(it.description_en, it.description_ar) for it in items]
        for item, vector in zip(items, embedder.embed_documents(texts)):
            item.embedding = vector
        db.commit()
    return EmbeddingBuildResult(
        provider=settings.embed_provider, dim=settings.embed_dim, embedded=len(items)
    )


@router.get("/search", response_model=list[SearchHit])
def search_catalog(
    q: str = Query(..., min_length=1, description="Free-text query (AR or EN)"),
    k: int = Query(5, ge=1, le=50, description="Number of nearest items to return"),
    db: Session = Depends(get_db),
    cid: int = Depends(current_company_id),
):
    qvec = get_embedder().embed_query(q)
    distance = CatalogItem.embedding.cosine_distance(qvec).label("distance")
    rows = db.execute(
        select(CatalogItem, distance)
        .where(CatalogItem.company_id == cid, CatalogItem.embedding.isnot(None))
        .order_by(distance)
        .limit(k)
    ).all()
    return [
        SearchHit(
            item=CatalogItemOut.model_validate(item),
            distance=float(dist),
            similarity=1.0 - float(dist),
        )
        for item, dist in rows
    ]


@router.post("/embeddings/reset")
def reset_embeddings(db: Session = Depends(get_db), _owner=Depends(require_owner)):
    """Platform-level: drop & recreate the embedding column at the current
    EMBED_DIM (affects ALL companies). Use when changing the embedding provider
    dimension; every company then rebuilds via /embeddings/build."""
    from sqlalchemy import text

    db.execute(text("ALTER TABLE catalog_items DROP COLUMN IF EXISTS embedding"))
    db.execute(
        text(f"ALTER TABLE catalog_items ADD COLUMN embedding vector({int(settings.embed_dim)})")
    )
    db.commit()
    return {"reset": True, "dim": settings.embed_dim}
