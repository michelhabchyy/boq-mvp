"""RFP endpoints: upload a scope-of-work, list, fetch, delete."""

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import current_company_id
from ..db import get_db
from ..llm import get_matcher
from ..models import RFPDocument, RFPLine
from ..rfp_loader import extract_full_text, parse_rfp_file
from ..schemas import (
    RFPDetail,
    RFPDocumentOut,
    RFPUploadResult,
    ScopeLineOut,
)

router = APIRouter(prefix="/rfps", tags=["rfp"])


def _document_out(doc: RFPDocument, line_count: int) -> RFPDocumentOut:
    return RFPDocumentOut(
        id=doc.id,
        filename=doc.filename,
        source_type=doc.source_type,
        created_at=doc.created_at,
        line_count=line_count,
    )


def _source_type(filename: str) -> str:
    name = (filename or "").lower()
    if name.endswith((".xlsx", ".xlsm")):
        return "xlsx"
    if name.endswith(".docx"):
        return "docx"
    if name.endswith(".pdf"):
        return "pdf"
    return "file"


@router.post("/upload", response_model=RFPUploadResult)
async def upload_rfp(
    file: UploadFile,
    analyze: bool = Query(
        False,
        description="Use AI to read the whole document and extract sections + items "
        "(for narrative RFPs). Off = deterministic table parsing.",
    ),
    db: Session = Depends(get_db),
    cid: int = Depends(current_company_id),
):
    content = await file.read()
    fname = file.filename or ""

    if analyze:
        return _upload_with_ai(db, cid, fname, content)

    # --- deterministic table path (clean BoQ spreadsheets / tables) ---
    try:
        parsed = parse_rfp_file(fname, content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not parsed.scope_lines:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "No scope lines could be extracted. If this is a "
                "narrative RFP, retry with AI analysis.",
                "warnings": parsed.warnings,
            },
        )

    doc = RFPDocument(filename=fname, source_type=parsed.source_type, company_id=cid)
    for i, line in enumerate(parsed.scope_lines, start=1):
        doc.lines.append(
            RFPLine(
                company_id=cid,
                line_no=i,
                description=line.description,
                quantity=line.quantity,
                unit=line.unit,
            )
        )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return _upload_result(doc, parsed.warnings)


def _upload_with_ai(db: Session, cid: int, fname: str, content: bytes) -> RFPUploadResult:
    try:
        text = extract_full_text(fname, content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not text.strip():
        raise HTTPException(status_code=422, detail="No readable text in the document.")

    try:
        analyzed = get_matcher().analyze_rfp(text)
    except Exception as e:  # surface provider/key errors clearly
        raise HTTPException(status_code=502, detail=f"AI analysis failed: {e}")

    doc = RFPDocument(filename=fname, source_type=_source_type(fname), company_id=cid)
    line_no = 0
    for s_no, section in enumerate(analyzed.sections, start=1):
        for item in section.items:
            if not (item.description or "").strip():
                continue
            line_no += 1
            doc.lines.append(
                RFPLine(
                    company_id=cid,
                    line_no=line_no,
                    section_no=s_no,
                    section_title=section.title,
                    description=item.description,
                    quantity=item.quantity,
                    unit=item.unit,
                )
            )
    if not doc.lines:
        raise HTTPException(
            status_code=422, detail="AI analysis found no work items in this document."
        )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    warnings = [
        f"AI analysis: {len(analyzed.sections)} section(s), {line_no} item(s) extracted."
    ]
    return _upload_result(doc, warnings)


def _upload_result(doc: RFPDocument, warnings: list[str]) -> RFPUploadResult:
    return RFPUploadResult(
        rfp_id=doc.id,
        filename=doc.filename,
        source_type=doc.source_type,
        line_count=len(doc.lines),
        warnings=warnings,
        scope_lines=[ScopeLineOut.model_validate(ln) for ln in doc.lines],
    )


@router.get("", response_model=list[RFPDocumentOut])
def list_rfps(db: Session = Depends(get_db), cid: int = Depends(current_company_id)):
    rows = db.execute(
        select(RFPDocument, func.count(RFPLine.id).label("line_count"))
        .outerjoin(RFPLine, RFPLine.rfp_id == RFPDocument.id)
        .where(RFPDocument.company_id == cid)
        .group_by(RFPDocument.id)
        .order_by(RFPDocument.created_at.desc())
    ).all()
    return [_document_out(doc, count) for doc, count in rows]


def _owned_rfp(db: Session, rfp_id: int, cid: int) -> RFPDocument:
    doc = db.get(RFPDocument, rfp_id)
    if doc is None or doc.company_id != cid:
        raise HTTPException(status_code=404, detail=f"RFP {rfp_id} not found")
    return doc


@router.get("/{rfp_id}", response_model=RFPDetail)
def get_rfp(rfp_id: int, db: Session = Depends(get_db), cid: int = Depends(current_company_id)):
    doc = _owned_rfp(db, rfp_id, cid)
    lines = [ScopeLineOut.model_validate(ln) for ln in doc.lines]
    return RFPDetail(document=_document_out(doc, len(lines)), scope_lines=lines)


@router.delete("/{rfp_id}")
def delete_rfp(rfp_id: int, db: Session = Depends(get_db), cid: int = Depends(current_company_id)):
    doc = _owned_rfp(db, rfp_id, cid)
    db.delete(doc)
    db.commit()
    return {"deleted": rfp_id}
