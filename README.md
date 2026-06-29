# BoQ Automation (MVP)

Single-operator, bilingual (Arabic / English) Bill of Quantities automation pipeline.

Stack: **FastAPI** (backend) · **Next.js** (frontend) · **PostgreSQL + pgvector** (storage/search).

> No multi-tenancy, billing, auth, or onboarding — this is a tool you run by hand.

## Project layout

```
boq-mvp/
├── .env.example          # copy to .env, fill in values
├── docker-compose.yml    # Postgres + pgvector on host port 5433
├── backend/
│   ├── requirements.txt
│   └── app/
│       ├── config.py     # settings from .env
│       ├── db.py         # SQLAlchemy engine + pgvector bootstrap
│       └── main.py       # FastAPI app (/health, /db/health)
└── frontend/
    ├── package.json
    └── app/              # Next.js App Router (status page)
```

## Prerequisites

- Python 3.12+  ·  Node 18+  ·  Docker Desktop (for the database)

## Setup

### 1. Environment file

```powershell
Copy-Item .env.example .env
# then edit .env and set a real POSTGRES_PASSWORD (and match it in DATABASE_URL)
```

### 2. Database

**Option A — Docker (default, local data):**

```powershell
docker compose up -d
```

This starts Postgres+pgvector on `localhost:5433`. Data persists in a Docker volume.

**Option B — no Docker, test immediately:** create a free [Neon](https://neon.tech)
project and replace `DATABASE_URL` in `.env` with its connection string
(append `?sslmode=require`). pgvector is already available there. No other changes.

### 3. Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Check: open http://localhost:8000/db/health — you should see
`"database": "connected"` and a `pgvector` version.

### 4. Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 — the page shows live backend + pgvector status.

## Tests

Backend tests live in `backend/tests/` and focus on authentication, multi-tenant
isolation, and document access control. Every test runs inside a transaction that
is rolled back, so **nothing is ever committed** — they are safe to run against any
database.

```bash
cd backend
pip install -r requirements.txt
pytest                       # uses DATABASE_URL (schema must already exist)
```

To run against a throwaway database (as CI does), point it at a fresh
Postgres+pgvector and let it create the schema:

```bash
TEST_DATABASE_URL=postgresql://user:pass@host:5432/boq_test TEST_INIT_DB=1 pytest
```

CI (`.github/workflows/ci.yml`) spins up `pgvector/pgvector:pg17`, runs the suite,
and builds the frontend on every push/PR.

## Observability

- `LOG_LEVEL` (default `INFO`) controls backend logging; every request is logged
  with method, path, status and duration, and unhandled errors are logged with a
  stack trace.
- Set `SENTRY_DSN` to enable error tracking (optional; no-op when unset).
