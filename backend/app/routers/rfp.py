"""RFP endpoints: upload a scope-of-work, list, fetch, delete."""

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import current_company_id
from ..db import SessionLocal, get_db
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
        status=doc.status,
        error=doc.error,
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
    background: BackgroundTasks,
    analyze: bool = Query(
        False,
        description="Use AI to read the whole document and extract sections + items "
        "(runs in the background). Off = deterministic table parsing (synchronous).",
    ),
    description: str = Form(""),
    sample: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    cid: int = Depends(current_company_id),
):
    content = await file.read()
    fname = file.filename or ""
    guidance = (description or "").strip()
    sample_fname = sample.filename if sample else ""
    sample_content = await sample.read() if sample else None

    if analyze:
        if _source_type(fname) == "file":
            raise HTTPException(400, "Unsupported file type. Upload .xlsx, .docx, or .pdf.")
        # Create the doc immediately and analyze in the background so the request
        # returns right away (no timeout on large/slow AI analysis).
        doc = RFPDocument(
            filename=fname,
            source_type=_source_type(fname),
            company_id=cid,
            status="analyzing",
            notes=guidance or None,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        background.add_task(
            _run_ai_analysis, doc.id, cid, fname, content, guidance, sample_fname, sample_content
        )
        return RFPUploadResult(
            rfp_id=doc.id,
            filename=doc.filename,
            source_type=doc.source_type,
            status="analyzing",
            line_count=0,
            warnings=["AI analysis started — large files can take up to a minute."],
            scope_lines=[],
        )

    # --- deterministic table path (clean BoQ spreadsheets / tables), synchronous ---
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

    doc = RFPDocument(
        filename=fname,
        source_type=parsed.source_type,
        company_id=cid,
        status="ready",
        notes=guidance or None,
    )
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
    return RFPUploadResult(
        rfp_id=doc.id,
        filename=doc.filename,
        source_type=doc.source_type,
        status="ready",
        line_count=len(doc.lines),
        warnings=parsed.warnings,
        scope_lines=[ScopeLineOut.model_validate(ln) for ln in doc.lines],
    )


def _run_ai_analysis(
    rfp_id: int,
    company_id: int,
    fname: str,
    content: bytes,
    guidance: str = "",
    sample_fname: str = "",
    sample_content: bytes | None = None,
) -> None:
    """Background worker: extract text, run the LLM (with the user's guidance +
    optional reference BoQ sample), persist sections/items, and set status.
    Uses its own DB session (the request's is already closed)."""
    db = SessionLocal()
    try:
        try:
            text = extract_full_text(fname, content)
            if not text.strip():
                raise ValueError(
                    "No readable text found (a scanned/image PDF needs OCR)."
                )
            sample_text = ""
            if sample_content:
                try:
                    sample_text = extract_full_text(sample_fname, sample_content)
                except Exception:
                    sample_text = ""  # bad sample is non-fatal
            analyzed = get_matcher().analyze_rfp(
                text, guidance=guidance, sample_text=sample_text
            )
            line_no = 0
            for s_no, section in enumerate(analyzed.sections, start=1):
                for item in section.items:
                    if not (item.description or "").strip():
                        continue
                    line_no += 1
                    db.add(
                        RFPLine(
                            company_id=company_id,
                            rfp_id=rfp_id,
                            line_no=line_no,
                            section_no=s_no,
                            section_title=section.title,
                            description=item.description,
                            quantity=item.quantity,
                            unit=item.unit,
                        )
                    )
            if line_no == 0:
                raise ValueError("AI analysis found no work items in this document.")
            doc = db.get(RFPDocument, rfp_id)
            if doc is not None:
                doc.status = "ready"
                doc.error = None
            db.commit()
        except Exception as e:
            db.rollback()
            doc = db.get(RFPDocument, rfp_id)
            if doc is not None:
                doc.status = "failed"
                doc.error = str(e)[:500]
                db.commit()
    finally:
        db.close()


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
