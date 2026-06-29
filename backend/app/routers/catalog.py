"""Catalog endpoints — all scoped to the caller's company."""

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile
from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ..auth import admin_company_id, current_company_id, get_current_user, require_owner
from ..catalog_loader import parse_catalog_file
from ..config import settings
from ..db import get_db
from ..embeddings import build_embedding_text, get_embedder
from ..item_utils import (
    build_items_workbook,
    generate_item_code,
    log_item_change,
    summarize_changes,
)
from ..models import CatalogItem, Company, ItemAudit, User
from ..uploads import read_upload_capped
from ..schemas import (
    CatalogItemIn,
    CatalogItemOut,
    CatalogItemPatch,
    CatalogUploadResult,
    EmbeddingBuildResult,
    EmbeddingStatus,
    ItemAuditOut,
    RowError,
    SearchHit,
)

XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

router = APIRouter(prefix="/catalog", tags=["catalog"])

# Every text field a free-text query scans, so search reads across ALL item info.
SEARCH_COLUMNS = (
    CatalogItem.item_code,
    CatalogItem.description_en,
    CatalogItem.description_ar,
    CatalogItem.brand,
    CatalogItem.supplier,
    CatalogItem.model_number,
    CatalogItem.category,
    CatalogItem.industry,
    CatalogItem.unit,
    CatalogItem.count_unit,
    CatalogItem.notes,
    CatalogItem.link,
)


def build_search_filter(q: str | None):
    """Multi-term search: split the query into words and require EACH word to
    appear in at least one field (AND across words, OR across fields). This is
    more accurate than a single substring match — e.g. 'copper cable electrical'
    only returns items matching all three terms somewhere in their data."""
    if not q or not q.strip():
        return None
    clauses = []
    for term in q.split():
        like = f"%{term}%"
        clauses.append(or_(*[col.ilike(like) for col in SEARCH_COLUMNS]))
    return and_(*clauses)


def _embed_item(item: CatalogItem) -> None:
    """(Re)generate this item's embedding from its descriptions + classification
    (industry/category/brand/model sharpen the semantic match), in place."""
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
_EMBED_FIELDS = {
    "description_en",
    "description_ar",
    "industry",
    "category",
    "brand",
    "model_number",
}


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
    content = await read_upload_capped(file)
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
    company = db.get(Company, cid)
    item = CatalogItem(
        **payload.model_dump(),
        company_id=cid,
        item_code=generate_item_code(db, company),
    )
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
    user: User = Depends(get_current_user),
):
    item = _owned(db, item_id, cid)
    fields = payload.model_dump(exclude_unset=True)
    summary = summarize_changes(item, fields)
    for key, value in fields.items():
        setattr(item, key, value)
    if _EMBED_FIELDS & fields.keys():
        _embed_item(item)
    if summary:  # only log when something tracked actually changed
        log_item_change(db, item, "edited", user, summary)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/item/{item_id}")
def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    cid: int = Depends(admin_company_id),
    user: User = Depends(get_current_user),
):
    item = _owned(db, item_id, cid)
    log_item_change(db, item, "deleted", user)
    db.delete(item)
    db.commit()
    return {"deleted": item_id}


@router.get("", response_model=list[CatalogItemOut])
def list_catalog(
    q: str | None = Query(None, description="Filter by code / description / brand / supplier / model"),
    industry: str | None = Query(None, description="Filter to a single industry"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    cid: int = Depends(current_company_id),
):
    stmt = select(CatalogItem).where(CatalogItem.company_id == cid).order_by(CatalogItem.item_code)
    if industry:
        stmt = stmt.where(CatalogItem.industry == industry)
    search = build_search_filter(q)
    if search is not None:
        stmt = stmt.where(search)
    return db.execute(stmt.limit(limit).offset(offset)).scalars().all()


@router.get("/industries", response_model=list[str])
def list_industries(db: Session = Depends(get_db), cid: int = Depends(current_company_id)):
    """Distinct industries used in this company's catalog (for filters/pickers)."""
    rows = db.execute(
        select(CatalogItem.industry)
        .where(CatalogItem.company_id == cid, CatalogItem.industry.isnot(None))
        .distinct()
        .order_by(CatalogItem.industry)
    ).scalars().all()
    return [r for r in rows if r]


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


@router.get("/history", response_model=list[ItemAuditOut])
def catalog_history(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    cid: int = Depends(current_company_id),
):
    """Recent edit/delete history for the whole company's catalog (newest first)."""
    return (
        db.execute(
            select(ItemAudit)
            .where(ItemAudit.company_id == cid)
            .order_by(ItemAudit.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )


@router.get("/export")
def export_catalog(db: Session = Depends(get_db), cid: int = Depends(current_company_id)):
    """Download the company's catalog (all filled fields) as an .xlsx sheet."""
    items = (
        db.execute(
            select(CatalogItem)
            .where(CatalogItem.company_id == cid)
            .order_by(CatalogItem.item_code)
        )
        .scalars()
        .all()
    )
    data = build_items_workbook(items, title="Catalog")
    return Response(
        content=data,
        media_type=XLSX_MEDIA,
        headers={"Content-Disposition": 'attachment; filename="catalog.xlsx"'},
    )


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
        texts = [
            build_embedding_text(
                it.description_en, it.description_ar, it.industry, it.category, it.brand, it.model_number
            )
            for it in items
        ]
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
