"""Company project pipeline — track opportunities from lead → bidding →
shortlisted → awarded → in progress → completed (or lost). Company-scoped:
admins manage; reviewers (and the owner acting on a company) can view.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import admin_company_id, current_company_id, get_current_user
from ..db import get_db
from ..models import Project, ProjectEvent, User
from ..observability import get_logger
from ..schemas import (
    PROJECT_STATUSES,
    ProjectActivityOut,
    ProjectDetailOut,
    ProjectEventOut,
    ProjectIn,
    ProjectOut,
    ProjectStatusIn,
    ProjectUpdate,
)

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
    return ProjectDetailOut(
        project=ProjectOut.model_validate(p),
        events=[ProjectEventOut.model_validate(e) for e in events],
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
    for key, value in payload.model_dump(exclude_unset=True).items():
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
