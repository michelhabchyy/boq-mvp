"""Lightweight in-memory rate limiting (login brute-force protection).

Per-process and per-IP — fine for a single backend instance. If you scale to
multiple instances/workers, move this to a shared store (e.g. Redis), since each
process keeps its own counters.
"""

import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

from .config import settings

_hits: dict[str, list[float]] = defaultdict(list)


def _client_ip(request: Request) -> str:
    # Behind a proxy/CDN (Render, Vercel, etc.) the real IP is in X-Forwarded-For.
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def login_rate_limit(request: Request) -> None:
    """Dependency for the login route. Raises 429 when an IP exceeds the limit."""
    now = time.time()
    window = settings.login_window_seconds
    ip = _client_ip(request)
    hits = _hits[ip]

    cutoff = now - window
    while hits and hits[0] < cutoff:
        hits.pop(0)

    if len(hits) >= settings.login_max_attempts:
        retry = int(window - (now - hits[0])) + 1
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please wait and try again.",
            headers={"Retry-After": str(max(1, retry))},
        )

    hits.append(now)
    # Opportunistic cleanup so the dict doesn't grow unbounded.
    if len(_hits) > 10000:
        for k in [k for k, v in _hits.items() if not v or v[-1] < cutoff]:
            _hits.pop(k, None)
