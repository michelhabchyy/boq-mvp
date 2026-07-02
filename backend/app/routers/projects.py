"""Company project pipeline — track opportunities from lead → bidding →
shortlisted → awarded → in progress → completed (or lost). Company-scoped:
admins manage; reviewers (and the owner acting on a company) can view.
"""

import re

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import admin_company_id, current_company_id, get_current_user
from ..db import get_db
from ..models import BoqLine, Project, ProjectEvent, ProjectFile, RFPDocument, User
from ..observability import get_logger
from ..schemas import (
    PROJECT_STATUSES,
    ProjectActivityOut,
    ProjectDetailOut,
    ProjectEventOut,
    ProjectFileOut,
    ProjectIn,
    ProjectOut,
    ProjectStatusIn,
    ProjectUpdate,
    RunnableRfpOut,
)
from ..uploads import read_upload_capped

FILE_KINDS = {"rfp", "boq_template"}
XLSX_MEDIA = "application/octet-stream"

router = APIRouter(prefix="/projects", tags=["projects"])
log = get_logger("projects")


def _owned(db: Session, project_id: int, cid: int) -> Project:
    p = db.get(Project, project_id)
    if p is None or p.company_id != cid:
        raise HTTPException(404, f"Project {project_id} not found")
    return p


def _check_status(status: str) -> None:
    if status not in PROJECT_STATUSES:
        raise HTTPException(400, f"status must be one of {PROJECT_STATUSES}")


def _check_rfp(db: Session, rfp_id: int | None, cid: int) -> None:
    """A linked RFP must belong to the same company."""
    if rfp_id is not None:
        doc = db.get(RFPDocument, rfp_id)
        if doc is None or doc.company_id != cid:
            raise HTTPException(404, f"RFP {rfp_id} not found")


def _boq_total(db: Session, rfp_id: int, cid: int) -> float:
    total = db.execute(
        select(func.coalesce(func.sum(BoqLine.line_total), 0)).where(
            BoqLine.rfp_id == rfp_id, BoqLine.company_id == cid
        )
    ).scalar_one()
    return float(total)


def _log_event(db, project, from_status, to_status, user, note=None):
    db.add(
        ProjectEvent(
            project_id=project.id,
            company_id=project.company_id,
            from_status=from_status,
            to_status=to_status,
            note=(note or None),
            user_id=getattr(user, "id", None),
            username=(getattr(user, "full_name", None) or getattr(user, "username", None)),
        )
    )


@router.get("", response_model=list[ProjectOut])
def list_projects(
    status: str | None = Query(None, description="Filter to a single pipeline status"),
    limit: int = Query(500, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    cid: int = Depends(current_company_id),
):
    stmt = select(Project).where(Project.company_id == cid).order_by(Project.updated_at.desc())
    if status:
        _check_status(status)
        stmt = stmt.where(Project.status == status)
    return db.execute(stmt.limit(limit).offset(offset)).scalars().all()


@router.get("/summary")
def projects_summary(db: Session = Depends(get_db), cid: int = Depends(current_company_id)):
    """Count of projects per pipeline status (for board headers / KPIs)."""
    rows = dict(
        db.execute(
            select(Project.status, func.count(Project.id))
            .where(Project.company_id == cid)
            .group_by(Project.status)
        ).all()
    )
    return {s: rows.get(s, 0) for s in PROJECT_STATUSES}


@router.get("/activity", response_model=list[ProjectActivityOut])
def activity(
    limit: int = Query(60, ge=1, le=200),
    db: Session = Depends(get_db),
    cid: int = Depends(current_company_id),
):
    """Company-wide feed of every pipeline update across all projects."""
    rows = db.execute(
        select(ProjectEvent, Project.name)
        .join(Project, Project.id == ProjectEvent.project_id)
        .where(ProjectEvent.company_id == cid)
        .order_by(ProjectEvent.created_at.desc(), ProjectEvent.id.desc())
        .limit(limit)
    ).all()
    return [
        ProjectActivityOut(
            id=e.id,
            project_id=e.project_id,
            project_name=name,
            from_status=e.from_status,
            to_status=e.to_status,
            note=e.note,
            username=e.username,
            created_at=e.created_at,
        )
        for e, name in rows
    ]


@router.get("/rfp-files", response_model=list[RunnableRfpOut])
def runnable_rfp_files(db: Session = Depends(get_db), cid: int = Depends(current_company_id)):
    """RFP files attached to projects — surfaced on the RFP page to run."""
    rows = db.execute(
        select(ProjectFile, Project.name)
        .join(Project, Project.id == ProjectFile.project_id)
        .where(ProjectFile.company_id == cid, ProjectFile.kind == "rfp")
        .order_by(ProjectFile.created_at.desc())
    ).all()
    return [
        RunnableRfpOut(
            file_id=pf.id, filename=pf.filename, project_id=pf.project_id,
            project_name=name, rfp_document_id=pf.rfp_document_id,
        )
        for pf, name in rows
    ]


@router.get("/{project_id}", response_model=ProjectDetailOut)
def get_project(project_id: int, db: Session = Depends(get_db), cid: int = Depends(current_company_id)):
    p = _owned(db, project_id, cid)
    events = (
        db.execute(
            select(ProjectEvent)
            .where(ProjectEvent.project_id == p.id)
            .order_by(ProjectEvent.created_at.desc(), ProjectEvent.id.desc())
        )
        .scalars()
        .all()
    )
    boq_total = None
    rfp_filename = None
    if p.rfp_id:
        rfp = db.get(RFPDocument, p.rfp_id)
        if rfp is not None and rfp.company_id == cid:
            rfp_filename = rfp.filename
            boq_total = _boq_total(db, p.rfp_id, cid)
    return ProjectDetailOut(
        project=ProjectOut.model_validate(p),
        events=[ProjectEventOut.model_validate(e) for e in events],
        boq_total=boq_total,
        rfp_filename=rfp_filename,
    )


@router.post("", response_model=ProjectOut)
def create_project(
    payload: ProjectIn,
    db: Session = Depends(get_db),
    cid: int = Depends(admin_company_id),
    user: User = Depends(get_current_user),
):
    status = payload.status or "lead"
    _check_status(status)
    _check_rfp(db, payload.rfp_id, cid)
    data = payload.model_dump(exclude={"status"})
    project = Project(**data, status=status, company_id=cid)
    db.add(project)
    db.flush()  # assign id
    _log_event(db, project, None, status, user, note="Project created")
    db.commit()
    db.refresh(project)
    log.info("Project %s created (company=%s, status=%s)", project.id, cid, status)
    return project


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    cid: int = Depends(admin_company_id),
):
    p = _owned(db, project_id, cid)
    fields = payload.model_dump(exclude_unset=True)
    if "rfp_id" in fields:
        _check_rfp(db, fields["rfp_id"], cid)
    for key, value in fields.items():
        setattr(p, key, value)
    db.commit()
    db.refresh(p)
    return p


@router.post("/{project_id}/status", response_model=ProjectDetailOut)
def change_status(
    project_id: int,
    payload: ProjectStatusIn,
    db: Session = Depends(get_db),
    cid: int = Depends(admin_company_id),
    user: User = Depends(get_current_user),
):
    p = _owned(db, project_id, cid)
    _check_status(payload.status)
    if payload.status != p.status:
        old = p.status
        p.status = payload.status
        _log_event(db, p, old, payload.status, user, note=payload.note)
        db.commit()
        db.refresh(p)
        log.info("Project %s %s -> %s", p.id, old, payload.status)
    elif payload.note:
        # Same status but a note was added — record it as a log entry.
        _log_event(db, p, p.status, p.status, user, note=payload.note)
        db.commit()
    return get_project(project_id, db, cid)


@router.delete("/{project_id}")
def delete_project(
    project_id: int, db: Session = Depends(get_db), cid: int = Depends(admin_company_id)
):
    p = _owned(db, project_id, cid)
    db.delete(p)
    db.commit()
    return {"deleted": project_id}


# --- project files (RFPs & BoQ templates) ----------------------------------


def _owned_file(db: Session, file_id: int, cid: int) -> ProjectFile:
    pf = db.get(ProjectFile, file_id)
    if pf is None or pf.company_id != cid:
        raise HTTPException(404, f"File {file_id} not found")
    return pf


@router.get("/{project_id}/files", response_model=list[ProjectFileOut])
def list_files(project_id: int, db: Session = Depends(get_db), cid: int = Depends(current_company_id)):
    _owned(db, project_id, cid)
    return (
        db.execute(
            select(ProjectFile).where(ProjectFile.project_id == project_id).order_by(ProjectFile.created_at.desc())
        ).scalars().all()
    )


@router.post("/{project_id}/files", response_model=ProjectFileOut)
async def upload_file(
    project_id: int,
    kind: str = Query("rfp", description="rfp | boq_template"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    cid: int = Depends(admin_company_id),
    user: User = Depends(get_current_user),
):
    _owned(db, project_id, cid)
    if kind not in FILE_KINDS:
        raise HTTPException(400, f"kind must be one of {sorted(FILE_KINDS)}")
    data = await read_upload_capped(file)
    if not data:
        raise HTTPException(400, "The uploaded file is empty.")
    pf = ProjectFile(
        project_id=project_id, company_id=cid, kind=kind,
        filename=file.filename or "file", content_type=file.content_type,
        size=len(data), data=data,
        uploaded_by_name=(user.full_name or user.username),
    )
    db.add(pf)
    db.commit()
    db.refresh(pf)
    return pf


@router.get("/files/{file_id}/download")
def download_file(file_id: int, db: Session = Depends(get_db), cid: int = Depends(current_company_id)):
    pf = _owned_file(db, file_id, cid)
    safe = re.sub(r'[^A-Za-z0-9._ -]', "_", pf.filename) or "file"
    return Response(
        content=pf.data,
        media_type=pf.content_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe}"'},
    )


@router.delete("/files/{file_id}")
def delete_file(file_id: int, db: Session = Depends(get_db), cid: int = Depends(admin_company_id)):
    pf = _owned_file(db, file_id, cid)
    db.delete(pf)
    db.commit()
    return {"deleted": file_id}


@router.post("/files/{file_id}/run")
def run_rfp_file(
    file_id: int,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    cid: int = Depends(admin_company_id),
    user: User = Depends(get_current_user),
):
    """Ingest an attached RFP file into the RFP workflow: create an RFPDocument
    (linked to the project) and run AI analysis in the background. If the project
    has a BoQ template attached, it's used as the reference sample."""
    from .rfp import _run_ai_analysis, _source_type  # local import avoids cycles

    pf = _owned_file(db, file_id, cid)
    if pf.kind != "rfp":
        raise HTTPException(400, "Only RFP files can be run.")
    st = _source_type(pf.filename)
    if st == "file":
        raise HTTPException(400, "Unsupported RFP file type. Use .xlsx, .docx, or .pdf.")

    doc = RFPDocument(
        filename=pf.filename, source_type=st, company_id=cid,
        project_id=pf.project_id, status="analyzing",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Use a BoQ template on the same project as the reference sample, if present.
    tmpl = db.execute(
        select(ProjectFile).where(
            ProjectFile.project_id == pf.project_id, ProjectFile.kind == "boq_template"
        ).order_by(ProjectFile.created_at.desc())
    ).scalars().first()
    sample_fname = tmpl.filename if tmpl else ""
    sample_content = tmpl.data if tmpl else None

    pf.rfp_document_id = doc.id
    db.commit()

    background.add_task(
        _run_ai_analysis, doc.id, cid, pf.filename, pf.data, "", sample_fname, sample_content, user.id
    )
    log.info("Project file %s run as RFP %s", file_id, doc.id)
    return {"rfp_id": doc.id, "status": "analyzing"}
