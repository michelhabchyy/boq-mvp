"""Test fixtures.

Tests run inside a DB transaction that is ALWAYS rolled back — nothing is ever
committed to the database, so it is safe to run against any environment. The
app's internal ``commit()`` calls are contained in SAVEPOINTs that the outer
rollback discards (the standard SQLAlchemy "join an external transaction"
pattern).

Env:
  TAQDEER_SKIP_INIT=1   set automatically so app boot never mutates a real DB.
  TEST_DATABASE_URL     point tests at a throwaway DB (used in CI).
  TEST_INIT_DB=1        create the schema once before tests (CI, fresh DB).
"""

import os
import uuid

# Must be set BEFORE importing the app so its lifespan doesn't touch a real DB.
os.environ["TAQDEER_SKIP_INIT"] = "1"
os.environ.setdefault("LLM_PROVIDER", "stub")
os.environ.setdefault("EMBED_PROVIDER", "stub")
if os.environ.get("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import event  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app import models  # noqa: E402
from app.auth import create_access_token, hash_password  # noqa: E402
from app.db import engine, get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    if os.environ.get("TEST_INIT_DB") == "1":
        from app.db import init_db

        init_db()
    yield


@pytest.fixture
def db():
    """A session bound to a transaction that is rolled back after the test."""
    connection = engine.connect()
    trans = connection.begin()
    session = Session(bind=connection)
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess, transaction):
        if transaction.nested and not transaction._parent.nested:
            sess.begin_nested()

    app.dependency_overrides[get_db] = lambda: session
    try:
        yield session
    finally:
        app.dependency_overrides.pop(get_db, None)
        session.close()
        trans.rollback()
        connection.close()


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


# --- factories --------------------------------------------------------------


@pytest.fixture
def make_company(db):
    def _make(name="Test Co"):
        plan = db.query(models.Plan).first()
        if plan is None:
            plan = models.Plan(name=f"Plan-{uuid.uuid4().hex[:8]}", weekly_token_limit=1_000_000)
            db.add(plan)
            db.flush()
        co = models.Company(name=name, is_active=True, plan_id=plan.id, weekly_tokens_used=0)
        db.add(co)
        db.flush()
        return co

    return _make


@pytest.fixture
def make_user(db):
    def _make(company=None, role="reviewer", subcontractor_id=None, password="pw-secret-123", active=True):
        u = models.User(
            username=f"u_{uuid.uuid4().hex[:10]}",
            full_name="Test User",
            password_hash=hash_password(password),
            role=role,
            company_id=(company.id if company else None),
            subcontractor_id=subcontractor_id,
            is_active=active,
        )
        db.add(u)
        db.flush()
        return u

    return _make


@pytest.fixture
def make_sub(db):
    def _make(company, name="Sub"):
        s = models.Subcontractor(company_id=company.id, name=f"{name}-{uuid.uuid4().hex[:6]}", is_active=True)
        db.add(s)
        db.flush()
        return s

    return _make


@pytest.fixture
def make_item(db):
    def _make(company, subcontractor_id=None, code=None, desc="Cable"):
        it = models.CatalogItem(
            company_id=company.id,
            subcontractor_id=subcontractor_id,
            item_code=code or f"T-{uuid.uuid4().hex[:8]}",
            description_en=desc,
            unit="m",
            unit_cost=10,
        )
        db.add(it)
        db.flush()
        return it

    return _make


@pytest.fixture
def make_rfp(db):
    def _make(company, filename="rfp.xlsx"):
        d = models.RFPDocument(company_id=company.id, filename=filename, source_type="xlsx", status="ready")
        db.add(d)
        db.flush()
        return d

    return _make


@pytest.fixture
def token():
    """Build a bearer-auth header for a user, optionally impersonating a company."""
    def _token(user, company_id=None):
        h = {"Authorization": f"Bearer {create_access_token(user)}"}
        if company_id is not None:
            h["X-Company-Id"] = str(company_id)
        return h

    return _token
