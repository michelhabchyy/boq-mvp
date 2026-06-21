"""Pydantic schemas for API input/output."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str | None
    role: str
    is_active: bool
    company_id: int | None
    subcontractor_id: int | None = None


class SubcontractorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    trade: str | None
    is_active: bool
    user_count: int = 0
    item_count: int = 0


class SubcontractorCreate(BaseModel):
    name: str
    trade: str | None = None


class SubcontractorUpdate(BaseModel):
    name: str | None = None
    trade: str | None = None
    is_active: bool | None = None


class SubUserCreate(BaseModel):
    username: str
    password: str
    full_name: str | None = None


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    weekly_token_limit: int


class PlanUpdate(BaseModel):
    name: str | None = None
    weekly_token_limit: int | None = None


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_active: bool
    user_count: int = 0
    plan_id: int | None = None
    plan_name: str | None = None
    weekly_token_limit: int = 0
    weekly_tokens_used: int = 0


class CompanyUsage(BaseModel):
    id: int
    name: str
    is_active: bool
    users: int
    catalog_items: int
    rfps: int
    boq_lines: int


class PlatformOverview(BaseModel):
    companies: int
    active: int
    disabled: int
    users: int
    catalog_items: int
    rfps: int
    boq_lines: int
    breakdown: list[CompanyUsage]


class CompanyCreate(BaseModel):
    """Owner creates a company and its first admin in one step."""

    name: str
    admin_username: str
    admin_password: str
    admin_full_name: str | None = None
    plan_id: int | None = None  # defaults to the cheapest plan if omitted


class CompanyUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None
    plan_id: int | None = None


class MyUsageOut(BaseModel):
    """The current user's own token spend + their company's weekly allowance.

    All token figures are BILLED tokens (actual consumption × billing_multiplier).
    """

    user_id: int
    tokens_this_week: int = 0
    tokens_all_time: int = 0
    company_weekly_limit: int = 0
    company_weekly_used: int = 0
    company_weekly_remaining: int = 0
    billing_multiplier: float = 1.0


class UserUsageOut(BaseModel):
    user_id: int | None = None
    username: str
    full_name: str | None = None
    role: str
    tokens_this_week: int = 0  # billed
    tokens_all_time: int = 0  # billed
    actual_this_week: int = 0  # raw tokens consumed from the API key


class CompanyUsageOut(BaseModel):
    """Per-user breakdown + company totals for the usage tracker."""

    company_weekly_limit: int = 0
    company_weekly_used: int = 0
    company_weekly_remaining: int = 0
    billing_multiplier: float = 1.0
    users: list[UserUsageOut] = []


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str | None = None
    role: str = "reviewer"  # 'admin' or 'reviewer'


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: str | None = None
    is_active: bool | None = None
    password: str | None = None


class CatalogItemOut(BaseModel):
    # from_attributes lets us build this straight from a SQLAlchemy row.
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_code: str
    description_ar: str | None
    description_en: str | None
    unit: str | None
    material_cost: float
    labour_cost: float
    markup: float
    brand: str | None
    subcontractor_id: int | None = None


class SearchHit(BaseModel):
    item: CatalogItemOut
    distance: float  # cosine distance (0 = identical, 2 = opposite)
    similarity: float  # 1 - distance, convenient 0..1-ish score


class EmbeddingStatus(BaseModel):
    provider: str
    dim: int
    total_items: int
    embedded_items: int


class EmbeddingBuildResult(BaseModel):
    provider: str
    dim: int
    embedded: int  # how many items had vectors written this run


class ScopeLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    line_no: int
    section_no: int
    section_title: str | None
    description: str
    quantity: float | None
    unit: str | None


class RFPDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    source_type: str
    status: str = "ready"
    error: str | None = None
    created_at: datetime
    line_count: int


class RFPUploadResult(BaseModel):
    rfp_id: int
    filename: str
    source_type: str
    status: str = "ready"
    line_count: int
    warnings: list[str]
    scope_lines: list[ScopeLineOut]


class RFPDetail(BaseModel):
    document: RFPDocumentOut
    scope_lines: list[ScopeLineOut]


class BoqLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rfp_id: int
    rfp_line_id: int
    catalog_item_id: int | None
    item_code: str | None
    description_en: str | None
    description_ar: str | None
    unit: str | None
    brand: str | None
    subcontractor: str | None = None
    quantity: float
    unit_cost: float
    markup: float
    unit_price: float
    line_total: float
    confidence: float
    needs_review: bool
    approved: bool
    notes: str | None


class BoqLineUpdate(BaseModel):
    """Reviewer edits. Only fields present in the request are applied."""

    quantity: float | None = None
    unit_price: float | None = None
    brand: str | None = None
    notes: str | None = None
    approved: bool | None = None
    # Set to an id to re-link to a different catalog item (re-snapshots price/
    # brand); set to null to unlink (mark unmatched). Omit to leave unchanged.
    catalog_item_id: int | None = None


class BoqLineCreate(BaseModel):
    """Reviewer adds an item the engine missed, under a scope line."""

    rfp_line_id: int
    catalog_item_id: int
    quantity: float = 1.0


class ScopeLineWithMatches(BaseModel):
    """A scope line plus its proposed catalog item(s) — the review-screen unit."""

    scope_line: ScopeLineOut
    boq_lines: list[BoqLineOut]


class MatchRunResult(BaseModel):
    rfp_id: int
    provider: str
    scope_lines_matched: int
    boq_lines_created: int
    flagged_for_review: int
    results: list[ScopeLineWithMatches]


class CatalogItemIn(BaseModel):
    item_code: str
    description_ar: str | None = None
    description_en: str | None = None
    unit: str | None = None
    material_cost: float = 0
    labour_cost: float = 0
    markup: float = 0
    brand: str | None = None


class CatalogItemPatch(BaseModel):
    item_code: str | None = None
    description_ar: str | None = None
    description_en: str | None = None
    unit: str | None = None
    material_cost: float | None = None
    labour_cost: float | None = None
    markup: float | None = None
    brand: str | None = None


class RowError(BaseModel):
    row: int  # 1-based row number in the source file (excluding the header)
    errors: list[str]


class CatalogUploadResult(BaseModel):
    loaded: int  # rows inserted or updated
    duplicates_in_file: int  # later rows that overrode an earlier same item_code
    skipped: int  # invalid rows skipped (only when skip_invalid=true)
    replaced_existing: bool  # whether the catalog was wiped before loading
    row_errors: list[RowError]
