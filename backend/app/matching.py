"""The assembly/matching engine (Stage 4).

For each RFP scope line:
  1. retrieve the nearest catalog items by vector similarity,
  2. ask the LLM to decompose the line into the catalog item(s) it needs
     (one-to-many assembly), with a per-unit quantity and confidence,
  3. snapshot each chosen item's price/brand from the catalog, apply markup,
     compute totals, and flag low-confidence or unmatched lines for review,
  4. persist the result as BoqLine rows.

Prices ALWAYS come from the catalog, never the LLM — the LLM only selects items
and quantities. This keeps pricing trustworthy.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import usage
from .config import settings
from .embeddings import build_embedding_text, get_embedder  # noqa: F401 (re-export)
from .llm import get_matcher
from .models import BoqLine, CatalogItem, Company, RFPLine, Subcontractor


def retrieve_candidates(
    db: Session, query: str, k: int, company_id: int
) -> list[tuple[CatalogItem, float]]:
    """Top-k catalog items (within the company) as (item, similarity) pairs."""
    embedder = get_embedder()
    qvec = embedder.embed_query(query)
    distance = CatalogItem.embedding.cosine_distance(qvec).label("distance")
    rows = db.execute(
        select(CatalogItem, distance)
        .where(CatalogItem.company_id == company_id, CatalogItem.embedding.isnot(None))
        .order_by(distance)
        .limit(k)
    ).all()
    return [(item, 1.0 - float(dist)) for item, dist in rows]


def _candidate_payload(pairs: list[tuple[CatalogItem, float]]) -> list[dict]:
    """Shape candidates for the LLM (no prices — selection only)."""
    return [
        {
            "code": item.item_code,
            "description_en": item.description_en,
            "description_ar": item.description_ar,
            "unit": item.unit,
            "brand": item.brand,
            "similarity": round(sim, 4),
        }
        for item, sim in pairs
    ]


def _price(material, labour, markup, quantity) -> tuple[float, float, float]:
    """Return (unit_cost, unit_price, line_total). markup is a percentage."""
    unit_cost = float(material or 0) + float(labour or 0)
    unit_price = unit_cost * (1.0 + float(markup or 0) / 100.0)
    line_total = unit_price * float(quantity or 0)
    return round(unit_cost, 2), round(unit_price, 2), round(line_total, 2)


def _build_boq_line(line: RFPLine, comp, item: CatalogItem | None, sub_name, threshold):
    """Build one BoqLine from an LLM component + the resolved catalog item."""
    scope_qty = float(line.quantity) if line.quantity is not None else 1.0
    quantity = round(comp.quantity_per_unit * scope_qty, 3)
    if item is None:
        return BoqLine(
            company_id=line.company_id,
            rfp_id=line.rfp_id,
            rfp_line_id=line.id,
            catalog_item_id=None,
            item_code=None,
            unit=line.unit,
            quantity=quantity,
            unit_cost=0,
            markup=0,
            unit_price=0,
            line_total=0,
            confidence=comp.confidence,
            needs_review=True,
            notes=comp.reason,
        )
    unit_cost, unit_price, line_total = _price(
        item.material_cost, item.labour_cost, item.markup, quantity
    )
    return BoqLine(
        company_id=line.company_id,
        rfp_id=line.rfp_id,
        rfp_line_id=line.id,
        catalog_item_id=item.id,
        item_code=item.item_code,
        description_en=item.description_en,
        description_ar=item.description_ar,
        unit=item.unit,
        brand=item.brand,
        subcontractor=sub_name,
        quantity=quantity,
        unit_cost=unit_cost,
        markup=float(item.markup or 0),
        unit_price=unit_price,
        line_total=line_total,
        confidence=comp.confidence,
        needs_review=comp.confidence <= threshold,
        notes=comp.reason,
    )


def run_matching_for_rfp(
    db: Session,
    rfp_id: int,
    company_id: int,
    rfp_line_id: int | None = None,
    user_id: int | None = None,
) -> list[BoqLine]:
    """Match all lines of an RFP (or one). Lines are priced in BATCHES (one LLM
    call per batch) to keep cost/calls low. Idempotent: replaces prior BoqLines."""
    stmt = (
        select(RFPLine)
        .where(RFPLine.rfp_id == rfp_id, RFPLine.company_id == company_id)
        .order_by(RFPLine.line_no)
    )
    if rfp_line_id is not None:
        stmt = stmt.where(RFPLine.id == rfp_line_id)
    lines = db.execute(stmt).scalars().all()

    # Enforce the company's weekly token quota before doing any LLM work.
    company = db.get(Company, company_id)
    if company is not None and usage.over_limit(db, company):
        raise usage.QuotaExceeded(
            "Weekly AI token limit reached for this company. It resets Monday — "
            "ask the platform owner to upgrade the plan for more."
        )

    line_ids = [ln.id for ln in lines]
    if line_ids:
        db.query(BoqLine).filter(BoqLine.rfp_line_id.in_(line_ids)).delete(
            synchronize_session=False
        )

    matcher = get_matcher()
    threshold = settings.match_confidence_threshold
    batch_size = max(1, settings.match_batch_size)
    sub_names = dict(
        db.execute(
            select(Subcontractor.id, Subcontractor.name).where(
                Subcontractor.company_id == company_id
            )
        ).all()
    )

    all_results: list[BoqLine] = []
    for start in range(0, len(lines), batch_size):
        batch = lines[start : start + batch_size]
        payload: list[dict] = []
        code_to_item: dict[str, CatalogItem] = {}
        for idx, line in enumerate(batch):
            pairs = retrieve_candidates(
                db, line.description, settings.match_top_k, company_id
            )
            for item, _ in pairs:
                code_to_item[item.item_code] = item
            payload.append(
                {
                    "index": idx,
                    "scope": {
                        "description": line.description,
                        "quantity": float(line.quantity) if line.quantity is not None else None,
                        "unit": line.unit,
                    },
                    "candidates": _candidate_payload(pairs),
                }
            )

        result = matcher.propose_batch(payload)
        by_index = {r.line_index: r for r in result.results}

        for idx, line in enumerate(batch):
            r = by_index.get(idx)
            components = r.components if (r and r.components) else None
            if not components:
                # No result for this line — flag it unmatched for review.
                bl = BoqLine(
                    company_id=line.company_id,
                    rfp_id=line.rfp_id,
                    rfp_line_id=line.id,
                    unit=line.unit,
                    quantity=float(line.quantity) if line.quantity is not None else 1.0,
                    confidence=0.0,
                    needs_review=True,
                    notes="No match returned by the engine.",
                )
                db.add(bl)
                all_results.append(bl)
                continue
            for comp in components:
                item = code_to_item.get(comp.catalog_item_code) if comp.catalog_item_code else None
                sub_name = (
                    sub_names.get(item.subcontractor_id) if item and item.subcontractor_id else None
                )
                bl = _build_boq_line(line, comp, item, sub_name, threshold)
                db.add(bl)
                all_results.append(bl)

    db.commit()
    # Record what the matching actually consumed against the weekly quota,
    # attributed to the user who ran it.
    if company is not None:
        usage.record_tokens(
            db,
            company,
            getattr(matcher, "tokens_used", 0),
            user_id=user_id,
            kind="matching",
        )
    for bl in all_results:
        db.refresh(bl)
    return all_results
