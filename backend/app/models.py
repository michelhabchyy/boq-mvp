"""Database models.

Multi-tenant: one deployment serves many companies from one database. Every
tenant-owned row carries a `company_id`, and all queries filter by it. The
platform 'owner' (company_id NULL) provisions companies and their admins.
"""

from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .config import settings
from .db import Base


class Plan(Base):
    """A subscription tier with a weekly LLM-token allowance. The owner edits
    limits and assigns plans to companies to control AI cost."""

    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    weekly_token_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Company(Base):
    """A tenant. All of a company's catalog / RFPs / BoQs are scoped to it."""

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Subscription + weekly LLM-token usage (resets each ISO week).
    plan_id: Mapped[int | None] = mapped_column(
        ForeignKey("plans.id", ondelete="SET NULL"), nullable=True
    )
    plan: Mapped["Plan | None"] = relationship()
    weekly_tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    week_start: Mapped[date | None] = mapped_column(Date)
    # Monotonic counter for auto-generated catalog item codes. Only ever
    # increases, so a code is NEVER reused — even after its item is deleted.
    next_item_seq: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Subcontractor(Base):
    """A subcontractor within a contractor company. Has its own login users and
    its own catalog items, which pool into the company catalog tagged by sub."""

    __tablename__ = "subcontractors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    trade: Mapped[str | None] = mapped_column(String(120))  # e.g. Electrical, Plumbing
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class User(Base):
    """An application user.

    Roles:
      'owner'        — platform super-admin (you). company_id NULL. Provisions
                       companies + their first admin. No BoQ work.
      'admin'        — company admin (the contractor). Manages users,
                       subcontractors, catalog, and all RFP/BoQ work.
      'reviewer'     — company user. RFP / matching / review / export; reads catalog.
      'subcontractor'— belongs to a subcontractor; can ONLY manage its own item
                       list. No access to RFPs, BoQs, or other subs.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="reviewer", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=True
    )
    # Set only for role='subcontractor' — which subcontractor this login belongs to.
    subcontractor_id: Mapped[int | None] = mapped_column(
        ForeignKey("subcontractors.id", ondelete="CASCADE"), index=True, nullable=True
    )
    # TOTP two-factor auth. Secret is set during enrolment; totp_enabled flips
    # true only after the first code is verified.
    totp_secret: Mapped[str | None] = mapped_column(String(64))
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TokenUsage(Base):
    """One row per AI operation, attributing tokens to the user who triggered it.

    The company-level weekly counter (Company.weekly_tokens_used) enforces the
    quota; this ledger powers the per-user 'who spent what' tracker and history.
    """

    __tablename__ = "token_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Null only if the triggering user was later deleted.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    kind: Mapped[str] = mapped_column(String(20), default="", nullable=False)  # analysis | matching
    # tokens = what the company/user is CHARGED (actual × billing multiplier);
    # actual_tokens = what was really consumed from the platform API key.
    tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    actual_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )


class ItemAudit(Base):
    """A history record of catalog item edits and deletions, so a company (and
    its subcontractors) can review what changed and when. item_code is kept even
    after the item row is gone — this is also the registry of 'used' codes that
    must never be reissued."""

    __tablename__ = "item_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Set when the change concerns a subcontractor's own item (scopes their view).
    subcontractor_id: Mapped[int | None] = mapped_column(
        ForeignKey("subcontractors.id", ondelete="SET NULL"), index=True, nullable=True
    )
    item_code: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    item_description: Mapped[str | None] = mapped_column(Text)  # snapshot for context
    action: Mapped[str] = mapped_column(String(20), nullable=False)  # edited | deleted
    details: Mapped[str | None] = mapped_column(Text)  # human-readable change summary
    # Who did it — id may go null if the user is later deleted; keep a name snapshot.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    username: Mapped[str | None] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )


class Document(Base):
    """An official (signed) file shared along a relationship:

      * subcontractor_id IS NULL  -> sent by the platform OWNER to the COMPANY
      * subcontractor_id IS SET    -> sent by the COMPANY to that SUBCONTRACTOR

    The recipient can list, preview and download; only the sender (or the owner)
    may delete. File bytes live in the DB (BYTEA) so they persist on hosts with
    an ephemeral filesystem.
    """

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )
    subcontractor_id: Mapped[int | None] = mapped_column(
        ForeignKey("subcontractors.id", ondelete="CASCADE"), index=True, nullable=True
    )
    title: Mapped[str | None] = mapped_column(String(300))
    filename: Mapped[str] = mapped_column(String(400), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(150))
    size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    uploaded_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    uploaded_by_name: Mapped[str | None] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )


class RecoveryCode(Base):
    """A single-use 2FA backup code. Only the hash is stored; the plaintext is
    shown to the user once at generation."""

    __tablename__ = "recovery_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    code_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CatalogItem(Base):
    __tablename__ = "catalog_items"
    # item_code is unique PER company (two companies may share a code).
    __table_args__ = (
        UniqueConstraint("company_id", "item_code", name="uq_catalog_company_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # Which subcontractor supplied this item/price; NULL = the contractor's own.
    subcontractor_id: Mapped[int | None] = mapped_column(
        ForeignKey("subcontractors.id", ondelete="SET NULL"), index=True, nullable=True
    )
    subcontractor: Mapped["Subcontractor | None"] = relationship()

    item_code: Mapped[str] = mapped_column(String(100), index=True, nullable=False)

    description_ar: Mapped[str | None] = mapped_column(Text)
    description_en: Mapped[str | None] = mapped_column(Text)
    # Unit of MEASURE (m, m², kg, L …) — this is what flows into the BoQ.
    unit: Mapped[str | None] = mapped_column(String(50))
    # COUNT unit (each, piece, no., set, box, roll …) — how the item is counted.
    count_unit: Mapped[str | None] = mapped_column(String(50))

    # Single all-in cost per unit (material + labour combined). No markup is
    # applied — the BoQ price equals this cost.
    unit_cost: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    brand: Mapped[str | None] = mapped_column(String(200))

    # --- Advanced classification & references ---
    # Trade/industry this item belongs to (e.g. Electrical, Plumbing, HVAC,
    # Civil). Indexed so the catalog can be filtered/grouped by industry.
    industry: Mapped[str | None] = mapped_column(String(120), index=True)
    # Finer grouping within an industry (e.g. "Cables", "Valves", "Lighting").
    category: Mapped[str | None] = mapped_column(String(120))
    # Where the item/price comes from (vendor/distributor name).
    supplier: Mapped[str | None] = mapped_column(String(200))
    # Manufacturer model / part number for precise identification.
    model_number: Mapped[str | None] = mapped_column(String(120))
    # Any reference URL: product page, datasheet, spec sheet, drawing, etc.
    link: Mapped[str | None] = mapped_column(Text)
    # Free-form notes / technical specifications.
    notes: Mapped[str | None] = mapped_column(Text)
    # When a SUBCONTRACTOR last edited this item — used to enforce the
    # one-edit-per-calendar-month limit on subcontractor self-service edits.
    last_edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(settings.embed_dim), nullable=True
    )


class RFPDocument(Base):
    """An uploaded RFP / scope-of-work and its extracted scope lines."""

    __tablename__ = "rfp_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[str] = mapped_column(String(10), nullable=False)  # xlsx|docx|pdf
    # AI analysis runs in the background: 'ready' (done / deterministic upload),
    # 'analyzing' (in progress), or 'failed' (see error).
    status: Mapped[str] = mapped_column(String(20), default="ready", nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    # Optional user-provided context that guides the AI analysis.
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    lines: Mapped[list["RFPLine"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="RFPLine.line_no",
    )


class RFPLine(Base):
    __tablename__ = "rfp_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )
    rfp_id: Mapped[int] = mapped_column(
        ForeignKey("rfp_documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    # Section grouping (from AI analysis). 0 / NULL for flat table uploads.
    section_no: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    section_title: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[float | None] = mapped_column(Numeric(16, 3))
    unit: Mapped[str | None] = mapped_column(String(50))

    document: Mapped["RFPDocument"] = relationship(back_populates="lines")


class BoqLine(Base):
    """A proposed BoQ line: one catalog item assigned to one RFP scope line."""

    __tablename__ = "boq_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )
    rfp_id: Mapped[int] = mapped_column(
        ForeignKey("rfp_documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    rfp_line_id: Mapped[int] = mapped_column(
        ForeignKey("rfp_lines.id", ondelete="CASCADE"), index=True, nullable=False
    )
    catalog_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("catalog_items.id", ondelete="SET NULL"), nullable=True
    )

    item_code: Mapped[str | None] = mapped_column(String(100))
    description_en: Mapped[str | None] = mapped_column(Text)
    description_ar: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str | None] = mapped_column(String(50))
    brand: Mapped[str | None] = mapped_column(String(200))
    subcontractor: Mapped[str | None] = mapped_column(String(200))  # snapshot of sub name

    quantity: Mapped[float] = mapped_column(Numeric(16, 3), default=0, nullable=False)
    unit_cost: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    markup: Mapped[float] = mapped_column(Numeric(7, 3), default=0, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    line_total: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)

    confidence: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
