"""Logging + (optional) Sentry error tracking.

`configure_logging()` sets up structured-ish console logging once at startup.
`init_sentry()` turns on Sentry only when SENTRY_DSN is set, and degrades
gracefully (no-op) if the SDK isn't installed.
"""

from __future__ import annotations

import logging
import sys

from .config import settings

_configured = False


def configure_logging() -> None:
    global _configured
    if _configured:
        return
    level = getattr(logging, (settings.log_level or "INFO").upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)-7s %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    # Uvicorn access logs are noisy and duplicate our request middleware.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    _configured = True


def init_sentry() -> None:
    """Enable Sentry if a DSN is configured and the SDK is available."""
    if not settings.sentry_dsn:
        return
    try:
        import sentry_sdk
    except ImportError:  # SDK not installed — log and carry on
        logging.getLogger("app").warning(
            "SENTRY_DSN is set but sentry-sdk is not installed; error tracking disabled."
        )
        return
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,
    )
    logging.getLogger("app").info("Sentry initialised (env=%s).", settings.app_env)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
