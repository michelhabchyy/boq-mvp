"""Database engine and session setup (SQLAlchemy 2.x, sync).

We use a synchronous engine for simplicity — FastAPI runs sync route handlers
in a threadpool, which is plenty for a single-operator MVP.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings

# pool_pre_ping checks a connection is alive before using it (avoids stale
# connections after the DB restarts).
engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)

SessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, future=True
)

# Base class for ORM models (tables are defined in later steps).
Base = declarative_base()


def init_db() -> None:
    """Ensure pgvector exists and all tables are created. Run once at startup."""
    from . import models  # noqa: F401 — registers models on Base.metadata
    from .config import settings

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)

    # Idempotent migrations for tables that predate later features.
    # create_all does not ALTER existing tables, so we do it explicitly.
    with engine.begin() as conn:
        # Stage 2: embedding column.
        conn.execute(
            text(
                "ALTER TABLE catalog_items "
                f"ADD COLUMN IF NOT EXISTS embedding vector({int(settings.embed_dim)})"
            )
        )
        # Single unit_cost replacing material_cost + labour_cost (+ markup dropped).
        # Backfill legacy rows ONCE: new ORM rows insert their own value (never
        # NULL), so only pre-existing rows get summed from the old columns.
        conn.execute(text("ALTER TABLE catalog_items ADD COLUMN IF NOT EXISTS unit_cost NUMERIC(14,2)"))
        # Backfill only on upgraded DBs that still have the old cost columns.
        has_legacy = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'catalog_items' AND column_name = 'material_cost'"
            )
        ).first()
        if has_legacy:
            conn.execute(
                text(
                    "UPDATE catalog_items SET unit_cost = "
                    "COALESCE(material_cost,0) + COALESCE(labour_cost,0) "
                    "WHERE unit_cost IS NULL"
                )
            )
        # Old cost columns are replaced by unit_cost — drop them so bulk inserts
        # (which no longer supply them) don't trip their NOT NULL constraint.
        conn.execute(text("ALTER TABLE catalog_items DROP COLUMN IF EXISTS material_cost"))
        conn.execute(text("ALTER TABLE catalog_items DROP COLUMN IF EXISTS labour_cost"))
        conn.execute(text("ALTER TABLE catalog_items DROP COLUMN IF EXISTS markup"))
        # Project financials (planned vs actual) + optional RFP link.
        conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS rfp_id INTEGER"))
        conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS planned_value NUMERIC(16,2)"))
        conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS contract_value NUMERIC(16,2)"))
        conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS actual_cost NUMERIC(16,2)"))
        conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS currency VARCHAR(8) DEFAULT 'SAR'"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_projects_rfp_id ON projects (rfp_id)"))
        # Count unit alongside the measure unit.
        conn.execute(text("ALTER TABLE catalog_items ADD COLUMN IF NOT EXISTS count_unit VARCHAR(50)"))
        # Advanced catalog fields: industry/category/supplier/model/link/notes.
        conn.execute(text("ALTER TABLE catalog_items ADD COLUMN IF NOT EXISTS industry VARCHAR(120)"))
        conn.execute(text("ALTER TABLE catalog_items ADD COLUMN IF NOT EXISTS category VARCHAR(120)"))
        conn.execute(text("ALTER TABLE catalog_items ADD COLUMN IF NOT EXISTS supplier VARCHAR(200)"))
        conn.execute(text("ALTER TABLE catalog_items ADD COLUMN IF NOT EXISTS model_number VARCHAR(120)"))
        conn.execute(text("ALTER TABLE catalog_items ADD COLUMN IF NOT EXISTS link TEXT"))
        conn.execute(text("ALTER TABLE catalog_items ADD COLUMN IF NOT EXISTS notes TEXT"))
        conn.execute(text("ALTER TABLE catalog_items ADD COLUMN IF NOT EXISTS last_edited_at TIMESTAMPTZ"))
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_catalog_items_industry ON catalog_items (industry)")
        )
        # Subcontractors: link columns on users + catalog_items, snapshot on boq.
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS subcontractor_id INTEGER"))
        # Two-factor auth (TOTP).
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_secret VARCHAR(64)"))
        conn.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_enabled BOOLEAN DEFAULT FALSE NOT NULL")
        )
        conn.execute(text("ALTER TABLE catalog_items ADD COLUMN IF NOT EXISTS subcontractor_id INTEGER"))
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_catalog_items_subcontractor_id ON catalog_items (subcontractor_id)")
        )
        conn.execute(text("ALTER TABLE boq_lines ADD COLUMN IF NOT EXISTS subcontractor VARCHAR(200)"))
        # AI RFP analysis: section grouping columns on rfp_lines.
        conn.execute(
            text("ALTER TABLE rfp_lines ADD COLUMN IF NOT EXISTS section_no INTEGER DEFAULT 0")
        )
        conn.execute(
            text("ALTER TABLE rfp_lines ADD COLUMN IF NOT EXISTS section_title VARCHAR(300)")
        )
        # Link RFPs to a project (optional).
        conn.execute(text("ALTER TABLE rfp_documents ADD COLUMN IF NOT EXISTS project_id INTEGER"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_rfp_documents_project_id ON rfp_documents (project_id)"))
        # Background AI analysis: status + error on rfp_documents.
        conn.execute(
            text("ALTER TABLE rfp_documents ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'ready'")
        )
        conn.execute(text("ALTER TABLE rfp_documents ADD COLUMN IF NOT EXISTS error TEXT"))
        conn.execute(text("ALTER TABLE rfp_documents ADD COLUMN IF NOT EXISTS notes TEXT"))
        # Subscription plans + weekly token usage on companies.
        conn.execute(text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS plan_id INTEGER"))
        conn.execute(
            text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS weekly_tokens_used INTEGER DEFAULT 0")
        )
        conn.execute(text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS week_start DATE"))
        conn.execute(
            text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS next_item_seq INTEGER DEFAULT 1")
        )
        # Token-usage ledger: actual_tokens column (added after the table shipped).
        conn.execute(
            text("ALTER TABLE token_usage ADD COLUMN IF NOT EXISTS actual_tokens INTEGER DEFAULT 0")
        )
        # Multi-tenancy: company_id on every tenant-owned table.
        for table in ("users", "catalog_items", "rfp_documents", "rfp_lines", "boq_lines"):
            conn.execute(
                text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS company_id INTEGER")
            )
            if table != "users":
                conn.execute(
                    text(
                        f"CREATE INDEX IF NOT EXISTS ix_{table}_company_id "
                        f"ON {table} (company_id)"
                    )
                )
        # item_code was globally unique before multi-tenancy; now unique per
        # company. Drop the old global unique index/constraint, add the composite.
        conn.execute(text("DROP INDEX IF EXISTS ix_catalog_items_item_code"))
        conn.execute(
            text("ALTER TABLE catalog_items DROP CONSTRAINT IF EXISTS catalog_items_item_code_key")
        )
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_catalog_company_code "
                "ON catalog_items (company_id, item_code)"
            )
        )
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_catalog_items_item_code ON catalog_items (item_code)")
        )

    # Create the seed owner (platform super-admin) on first run.
    from .auth import seed_owner

    seed_owner()

    # Seed default subscription plans (idempotent).
    from .usage import seed_plans

    seed_plans()


def get_db():
    """FastAPI dependency that yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
