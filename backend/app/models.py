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
    unit: Mapped[str | None] = mapped_column(String(50))

    material_cost: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    labour_cost: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    markup: Mapped[float] = mapped_column(Numeric(7, 3), default=0, nullable=False)
    brand: Mapped[str | None] = mapped_column(String(200))

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
