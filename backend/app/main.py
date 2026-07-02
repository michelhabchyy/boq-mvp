"""FastAPI application entrypoint.

Step 1 exposes two health checks:
  GET /health      -> app is up
  GET /db/health   -> Postgres is reachable AND pgvector is installed
"""

import os
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from .auth import get_current_user
from .config import settings
from .db import engine, init_db
from .observability import configure_logging, get_logger, init_sentry
from .routers import (
    auth,
    boq,
    capabilities,
    catalog,
    companies,
    dashboard,
    documents,
    matching,
    my_items,
    output,
    plans,
    projects,
    rfp,
    subcontractors,
    usage,
    users,
)


configure_logging()
init_sentry()
log = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once on startup: ensure schema/extension exist. Tests set
    # TAQDEER_SKIP_INIT so they never mutate a real database on app boot.
    if os.environ.get("TAQDEER_SKIP_INIT") != "1":
        init_db()
        log.info("Startup complete (env=%s).", settings.app_env)
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


# Static security headers applied to every API response (the API serves JSON +
# file downloads, so a tight default-src is safe). HSTS is added in production.
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
}


def _apply_security_headers(response) -> None:
    for k, v in _SECURITY_HEADERS.items():
        response.headers.setdefault(k, v)
    if settings.app_env != "development":
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
        )


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log each request's method, path, status and duration; attach security
    headers; log + surface any unhandled exception (errors never silent)."""
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        ms = (time.perf_counter() - start) * 1000
        log.exception("%s %s -> unhandled error after %.0fms", request.method, request.url.path, ms)
        raise
    ms = (time.perf_counter() - start) * 1000
    level = log.warning if response.status_code >= 500 else log.info
    level("%s %s -> %s (%.0fms)", request.method, request.url.path, response.status_code, ms)
    _apply_security_headers(response)
    return response

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
app.include_router(projects.router)
app.include_router(capabilities.router)


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
