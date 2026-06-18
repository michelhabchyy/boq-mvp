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

from .config import settings
from .embeddings import build_embedding_text, get_embedder
from .llm import get_matcher
from .models import BoqLine, CatalogItem, RFPLine


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


def match_scope_line(db: Session, line: RFPLine) -> list[BoqLine]:
    """Run retrieval + LLM + pricing for one scope line. Returns unsaved BoqLines."""
    pairs = retrieve_candidates(db, line.description, settings.match_top_k, line.company_id)
    by_code = {item.item_code: item for item, _ in pairs}

    matcher = get_matcher()
    assembly = matcher.propose_assembly(
        scope={
            "description": line.description,
            "quantity": float(line.quantity) if line.quantity is not None else None,
            "unit": line.unit,
        },
        candidates=_candidate_payload(pairs),
    )

    scope_qty = float(line.quantity) if line.quantity is not None else 1.0
    threshold = settings.match_confidence_threshold
    results: list[BoqLine] = []

    for comp in assembly.components:
        item = by_code.get(comp.catalog_item_code) if comp.catalog_item_code else None
        quantity = comp.quantity_per_unit * scope_qty

        if item is None:
            # Unmatched (LLM chose null, or hallucinated a code not in candidates).
            results.append(
                BoqLine(
                    company_id=line.company_id,
                    rfp_id=line.rfp_id,
                    rfp_line_id=line.id,
                    catalog_item_id=None,
                    item_code=None,
                    description_en=None,
                    description_ar=None,
                    unit=line.unit,
                    brand=None,
                    quantity=round(quantity, 3),
                    unit_cost=0,
                    markup=0,
                    unit_price=0,
                    line_total=0,
                    confidence=comp.confidence,
                    needs_review=True,
                    notes=comp.reason,
                )
            )
            continue

        unit_cost, unit_price, line_total = _price(
            item.material_cost, item.labour_cost, item.markup, quantity
        )
        results.append(
            BoqLine(
                company_id=line.company_id,
                rfp_id=line.rfp_id,
                rfp_line_id=line.id,
                catalog_item_id=item.id,
                item_code=item.item_code,
                description_en=item.description_en,
                description_ar=item.description_ar,
                unit=item.unit,
                brand=item.brand,
                subcontractor=item.subcontractor.name if item.subcontractor else None,
                quantity=round(quantity, 3),
                unit_cost=unit_cost,
                markup=float(item.markup or 0),
                unit_price=unit_price,
                line_total=line_total,
                confidence=comp.confidence,
                needs_review=comp.confidence <= threshold,
                notes=comp.reason,
            )
        )

    return results


def run_matching_for_rfp(
    db: Session, rfp_id: int, company_id: int, rfp_line_id: int | None = None
) -> list[BoqLine]:
    """Match all lines of an RFP (or one line). Replaces prior BoqLines for those
    scope lines so the run is idempotent. Returns the persisted BoqLines."""
    stmt = (
        select(RFPLine)
        .where(RFPLine.rfp_id == rfp_id, RFPLine.company_id == company_id)
        .order_by(RFPLine.line_no)
    )
    if rfp_line_id is not None:
        stmt = stmt.where(RFPLine.id == rfp_line_id)
    lines = db.execute(stmt).scalars().all()

    line_ids = [ln.id for ln in lines]
    if line_ids:
        db.query(BoqLine).filter(BoqLine.rfp_line_id.in_(line_ids)).delete(
            synchronize_session=False
        )

    all_results: list[BoqLine] = []
    for line in lines:
        boq_lines = match_scope_line(db, line)
        db.add_all(boq_lines)
        all_results.extend(boq_lines)

    db.commit()
    for bl in all_results:
        db.refresh(bl)
    return all_results
