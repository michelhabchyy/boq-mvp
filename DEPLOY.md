# Deployment Guide

The app is **one** backend + **one** frontend + **one** database (multi-tenant).
It's host-agnostic: the backend runs anywhere that runs a container; the frontend
is a standard Next.js app (Vercel is easiest, or a container).

## Components
- **Database** — Neon (cloud Postgres + pgvector). Create a dedicated *production*
  project; copy its `DATABASE_URL` (with `?sslmode=require`).
- **Backend** — FastAPI container (`backend/Dockerfile`). Listens on `$PORT` (8000).
- **Frontend** — Next.js (`frontend/Dockerfile`, or deploy to Vercel).

## Pre-flight checklist (do these before going live)
- [ ] **Production Neon DB** created; `DATABASE_URL` ready.
- [ ] **`AUTH_SECRET`** set to a 64-char random string (`python -c "import secrets;print(secrets.token_hex(32))"`).
- [ ] **`SEED_ADMIN_USERNAME` / `SEED_ADMIN_PASSWORD`** set to real owner creds (the seed owner is created on first boot; or change the password after).
- [ ] **`CORS_ORIGINS`** = your frontend's public URL (e.g. `https://app.yourco.com`). Wrong value here = browser blocks all API calls.
- [ ] **`DOCS_ENABLED=false`** (default).
- [ ] **`OPENAI_API_KEY`** + **`ANTHROPIC_API_KEY`** set; `EMBED_PROVIDER=openai`, `LLM_PROVIDER=anthropic`.
- [ ] **`NEXT_PUBLIC_API_URL`** (frontend) = the backend's public URL (e.g. `https://api.yourco.com`). Baked at build time.
- [ ] Both services served over **HTTPS** (managed hosts do this automatically).
- [ ] Secrets set via the host's secret manager — **never** committed.

See `.env.production.example` for the full backend variable list.

## Backend — build & run (any container host)
```bash
cd backend
docker build -t boq-api .
docker run -p 8000:8000 --env-file your-prod.env boq-api
```
On a managed host (Render/Railway/Fly/Azure Container Apps): point it at `backend/`,
let it build the Dockerfile, set the env vars from the checklist, expose port 8000.

> On first boot the app auto-creates tables, enables pgvector, runs idempotent
> migrations, and seeds the owner. Run a **single instance** initially. If you
> scale to multiple instances later, run DB migrations as a one-off step rather
> than relying on concurrent startup (the migrations are idempotent but DDL on
> the same tables can contend).

## Frontend — two options
**A) Vercel (easiest):** import the repo, set root to `frontend/`, add env
`NEXT_PUBLIC_API_URL=https://api.yourco.com`, deploy. Auto HTTPS + domain.

**B) Container:**
```bash
cd frontend
docker build --build-arg NEXT_PUBLIC_API_URL=https://api.yourco.com -t boq-web .
docker run -p 3000:3000 boq-web
```

## DNS
- `app.yourco.com` → frontend
- `api.yourco.com` → backend
- Set `CORS_ORIGINS` (backend) and `NEXT_PUBLIC_API_URL` (frontend) to match.

## After first deploy
1. Log in as the seed owner → change the password (or you set a strong one via `SEED_ADMIN_PASSWORD`).
2. Create a company + its admin (Companies screen).
3. That admin loads the catalog / creates subcontractors, then runs RFPs.

## Recommended next hardening (not blockers)
- Error monitoring (e.g. Sentry) + log retention.
- Move login rate-limiting to Redis if you run multiple backend instances
  (current limiter is per-process/in-memory).
- Per-tenant usage/cost tracking for OpenAI + Anthropic spend.
- Upload size limits at the proxy.
