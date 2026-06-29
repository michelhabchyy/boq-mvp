"""Application settings, loaded from the root .env file.

pydantic-settings reads environment variables (and the .env file) and
validates them into a typed object. Import `settings` anywhere you need config.
"""

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# config.py lives at: <repo>/backend/app/config.py
# parents[0]=app  parents[1]=backend  parents[2]=<repo root>
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",  # ignore vars we haven't modeled yet (e.g. future keys)
    )

    app_env: str = "development"
    database_url: str  # required — app won't start without it

    # Interactive API docs (/docs, /redoc, /openapi.json). OFF by default — turn
    # on only in development. Never expose the full API surface in production.
    docs_enabled: bool = False

    # Comma-separated list of allowed browser origins (the frontend URL[s]).
    # In production set e.g. "https://app.yourco.com".
    cors_origins: str = "http://localhost:3000"

    # Login brute-force protection: max attempts per IP per window (seconds).
    login_max_attempts: int = 5
    login_window_seconds: int = 60

    # Largest single file accepted by upload endpoints (RFP, catalog, documents).
    max_upload_mb: int = 25

    # --- Observability ---
    # Root log level (DEBUG / INFO / WARNING / ERROR).
    log_level: str = "INFO"
    # Sentry error tracking. Leave empty to disable; set the DSN in production.
    sentry_dsn: str | None = None
    # Fraction of requests traced for performance (0.0–1.0). Keep low in prod.
    sentry_traces_sample_rate: float = 0.0

    @field_validator("database_url")
    @classmethod
    def use_psycopg3_driver(cls, v: str) -> str:
        """Force the psycopg (v3) driver, which is what requirements.txt ships.

        A bare `postgresql://` URL makes SQLAlchemy pick the legacy psycopg2
        dialect; we rewrite it to `postgresql+psycopg://` so a fresh install
        works without psycopg2. (Already-qualified URLs are left as-is.)
        """
        if v.startswith("postgresql://"):
            return "postgresql+psycopg://" + v[len("postgresql://"):]
        return v

    # --- Embeddings (Stage 2) ---
    # Which provider the embed interface uses. "stub" works with no API key.
    # Swap to "openai" / "cohere" / "voyage" later by setting this + the key.
    embed_provider: str = "stub"
    # Vector dimension. MUST match the active provider's output and the pgvector
    # column. Changing it later requires resetting the embedding column
    # (POST /catalog/embeddings/reset). Stub produces vectors of this size.
    embed_dim: int = 1536
    embed_model: str | None = None  # provider-specific model name, optional

    # --- Matching engine (Stage 4) ---
    # LLM provider for assembly decomposition. "stub" runs offline (no key).
    # Set to "anthropic" + ANTHROPIC_API_KEY to use Claude.
    llm_provider: str = "stub"
    llm_model: str = "claude-opus-4-8"
    # Components at or below this confidence are flagged for human review.
    match_confidence_threshold: float = 0.6
    # How many catalog candidates to retrieve per scope line and show the LLM.
    match_top_k: int = 8
    # Scope lines priced per LLM call. Batching cuts cost/calls vs one-per-line.
    match_batch_size: int = 20
    # Billing markup on AI tokens: companies/users are charged this multiple of
    # the tokens actually consumed from the platform's API key (e.g. 1.25 = +25%).
    # Plan weekly limits are expressed in these BILLED tokens.
    token_billing_multiplier: float = 1.25

    # --- Authentication ---
    # Secret used to sign JWTs. CHANGE THIS per deployment (any long random string).
    auth_secret: str = "dev-insecure-change-me-please"
    access_token_expire_minutes: int = 60 * 12  # 12 hours
    # Seed admin: created once on first startup if no users exist. Set real
    # values in .env per company copy, then log in and create more users.
    seed_admin_username: str = "KarimMichel123"
    seed_admin_password: str = "KarimMichel123"

    # Placeholders for later steps (optional now)
    azure_docintel_endpoint: str | None = None
    azure_docintel_key: str | None = None
    openai_api_key: str | None = None
    cohere_api_key: str | None = None
    voyage_api_key: str | None = None
    anthropic_api_key: str | None = None


    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
