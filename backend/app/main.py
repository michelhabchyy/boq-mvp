"""FastAPI application entrypoint.

Step 1 exposes two health checks:
  GET /health      -> app is up
  GET /db/health   -> Postgres is reachable AND pgvector is installed
"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .auth import get_current_user
from .config import settings
from .db import engine, init_db
from .routers import (
    auth,
    boq,
    catalog,
    companies,
    dashboard,
    documents,
    matching,
    my_items,
    output,
    plans,
    rfp,
    subcontractors,
    usage,
    users,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once on startup: make sure the vector extension is available.
    init_db()
    yield
    # (nothing to clean up yet)


# Interactive docs are disabled unless DOCS_ENABLED=true (dev only) — don't
# expose the full API surface/schemas in production.
_docs = settings.docs_enabled
app = FastAPI(
    title="BoQ Automation API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if _docs else None,
    redoc_url="/redoc" if _docs else None,
    openapi_url="/openapi.json" if _docs else None,
)

# Allowed browser origins come from CORS_ORIGINS (the frontend URL[s]).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

# auth/login is public; every other endpoint authenticates via its own
# dependency (require_owner / require_company_admin / current_company_id), which
# also enforces tenant scoping. No route is left unauthenticated.
app.include_router(auth.router)
app.include_router(companies.router)  # owner-only
app.include_router(plans.router)  # owner-only
app.include_router(users.router)  # company-admin-only
app.include_router(subcontractors.router)  # company-admin-only
app.include_router(my_items.router)  # subcontractor-only
app.include_router(catalog.router)
app.include_router(rfp.router)
app.include_router(matching.router)
app.include_router(boq.router)
app.include_router(output.router)
app.include_router(usage.router)
app.include_router(dashboard.router)
app.include_router(documents.router)


@app.get("/health")
def health():
    return {"status": "ok", "env": settings.app_env}


@app.get("/db/health")
def db_health(_user=Depends(get_current_user)):
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version()")).scalar()
        pgvector_version = conn.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        ).scalar()
    return {
        "database": "connected",
        "postgres": version,
        "pgvector": pgvector_version,
    }
