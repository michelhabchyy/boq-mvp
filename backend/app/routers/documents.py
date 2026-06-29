"""Official (signed) document exchange along two relationships:

  * OWNER  -> COMPANY        (subcontractor_id IS NULL)
  * COMPANY -> SUBCONTRACTOR (subcontractor_id IS SET)

The sender uploads; the recipient lists, previews and downloads; only the sender
(or the platform owner) can delete. Files are stored in the DB as BYTEA.
"""

import re

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import (
    admin_company_id,
    current_company_id,
    get_current_user,
    require_owner,
    require_subcontractor,
)
from ..db import get_db
from ..models import Company, Document, Subcontractor, User
from ..schemas import DocumentOut
from ..uploads import read_upload_capped

router = APIRouter(prefix="/documents", tags=["documents"])


async def _read_upload(file: UploadFile) -> bytes:
    data = await read_upload_capped(file)  # caps memory + size (413 if too big)
    if not data:
        raise HTTPException(400, "The uploaded file is empty.")
    return data


def _new_doc(company_id, subcontractor_id, file, data, title, user) -> Document:
    return Document(
        company_id=company_id,
        subcontractor_id=subcontractor_id,
        title=(title or "").strip() or None,
        filename=file.filename or "document",
        content_type=file.content_type,
        size=len(data),
        data=data,
        uploaded_by_user_id=user.id,
        uploaded_by_name=(user.full_name or user.username),
    )


def _owned_sub(db: Session, sub_id: int, cid: int) -> Subcontractor:
    sub = db.get(Subcontractor, sub_id)
    if sub is None or sub.company_id != cid:
        raise HTTPException(404, f"Subcontractor {sub_id} not found")
    return sub


# --- access control ---------------------------------------------------------


def _can_view(user: User, doc: Document) -> bool:
    if user.role == "owner":
        return True
    if doc.subcontractor_id is None:  # owner -> company
        return user.role in ("admin", "reviewer") and user.company_id == doc.company_id
    # company -> subcontractor
    if user.role in ("admin", "reviewer") and user.company_id == doc.company_id:
        return True
    return user.role == "subcontractor" and user.subcontractor_id == doc.subcontractor_id


def _can_delete(user: User, doc: Document) -> bool:
    if user.role == "owner":
        return True
    if doc.subcontractor_id is None:  # only the owner (sender) deletes these
        return False
    return user.role == "admin" and user.company_id == doc.company_id


# --- OWNER -> COMPANY -------------------------------------------------------


@router.post("/company/{company_id}", response_model=DocumentOut)
async def upload_to_company(
    company_id: int,
    file: UploadFile = File(...),
    title: str = Form(""),
    db: Session = Depends(get_db),
    owner: User = Depends(require_owner),
):
    if db.get(Company, company_id) is None:
        raise HTTPException(404, f"Company {company_id} not found")
    data = await _read_upload(file)
    doc = _new_doc(company_id, None, file, data, title, owner)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@router.get("/company/{company_id}", response_model=list[DocumentOut])
def list_company_docs(
    company_id: int,
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    owner: User = Depends(require_owner),
):
    return (
        db.execute(
            select(Document)
            .where(Document.company_id == company_id, Document.subcontractor_id.is_(None))
            .order_by(Document.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )


@router.get("/inbox", response_model=list[DocumentOut])
def company_inbox(
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    cid: int = Depends(current_company_id),
):
    """Documents the platform owner has shared with this company."""
    return (
        db.execute(
            select(Document)
            .where(Document.company_id == cid, Document.subcontractor_id.is_(None))
            .order_by(Document.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )


# --- COMPANY -> SUBCONTRACTOR -----------------------------------------------


@router.post("/subcontractor/{sub_id}", response_model=DocumentOut)
async def upload_to_sub(
    sub_id: int,
    file: UploadFile = File(...),
    title: str = Form(""),
    db: Session = Depends(get_db),
    cid: int = Depends(admin_company_id),
    user: User = Depends(get_current_user),
):
    _owned_sub(db, sub_id, cid)
    data = await _read_upload(file)
    doc = _new_doc(cid, sub_id, file, data, title, user)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@router.get("/subcontractor/{sub_id}", response_model=list[DocumentOut])
def list_sub_docs(
    sub_id: int,
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    cid: int = Depends(current_company_id),
):
    _owned_sub(db, sub_id, cid)
    return (
        db.execute(
            select(Document)
            .where(Document.subcontractor_id == sub_id, Document.company_id == cid)
            .order_by(Document.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )


@router.get("/my", response_model=list[DocumentOut])
def my_docs(
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    me: User = Depends(require_subcontractor),
):
    """Documents this subcontractor's contractor has shared with them."""
    return (
        db.execute(
            select(Document)
            .where(Document.subcontractor_id == me.subcontractor_id)
            .order_by(Document.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )


# --- download / delete (shared) ---------------------------------------------


@router.get("/{doc_id}/download")
def download_document(
    doc_id: int,
    inline: bool = Query(False, description="Preview inline instead of downloading"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    doc = db.get(Document, doc_id)
    if doc is None or not _can_view(user, doc):
        raise HTTPException(404, f"Document {doc_id} not found")
    safe = re.sub(r'[^A-Za-z0-9._ -]', "_", doc.filename) or "document"
    disp = "inline" if inline else "attachment"
    return Response(
        content=doc.data,
        media_type=doc.content_type or "application/octet-stream",
        headers={"Content-Disposition": f'{disp}; filename="{safe}"'},
    )


@router.delete("/{doc_id}")
def delete_document(
    doc_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    doc = db.get(Document, doc_id)
    if doc is None or not _can_view(user, doc):
        raise HTTPException(404, f"Document {doc_id} not found")
    if not _can_delete(user, doc):
        raise HTTPException(403, "Only the sender can delete this document.")
    db.delete(doc)
    db.commit()
    return {"deleted": doc_id}
