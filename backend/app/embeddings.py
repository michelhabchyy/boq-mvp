"""Configurable text-embedding interface.

The rest of the engine only ever calls `get_embedder()` and uses two methods:
    embedder.embed_documents(list[str]) -> list[vector]
    embedder.embed_query(str)          -> vector

Which implementation you get is chosen by EMBED_PROVIDER in .env. Today only
the "stub" provider is wired (no API key needed) so the whole pipeline runs
end-to-end. To plug in a real provider later, implement its class below and
register it in `_PROVIDERS` — nothing else in the codebase changes.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

from .config import settings

# Split on anything that isn't a letter/digit. \w with re.UNICODE keeps Arabic.
_TOKEN_RE = re.compile(r"[^\w]+", re.UNICODE)


class Embedder(Protocol):
    dim: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


def _l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0:
        return vec
    return [x / norm for x in vec]


class StubEmbedder:
    """Deterministic, offline placeholder using a hashing bag-of-words.

    NOT semantically meaningful — it captures *lexical* overlap only (shared
    words, including Arabic, land in the same buckets). That's enough to prove
    vector storage + nearest-neighbour search work end-to-end. Replace with a
    real provider before relying on the match quality.
    """

    def __init__(self, dim: int):
        self.dim = dim

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in _TOKEN_RE.split((text or "").lower()):
            if not token:
                continue
            h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
            vec[h % self.dim] += 1.0
        return _l2_normalize(vec)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_one(text)


class OpenAIEmbedder:
    """OpenAI embeddings (text-embedding-3-small / -large).

    Both 3-* models accept a `dimensions` parameter, so we always request
    EMBED_DIM vectors — keeping the pgvector column size fixed regardless of the
    model. 3-large truncated to 1536 gives the best multilingual (Arabic/English)
    quality; 3-small is the cheaper default.
    """

    _MAX_BATCH = 256  # stay well under OpenAI's per-request input cap

    def __init__(self, dim: int, model: str, api_key: str):
        from openai import OpenAI

        self.dim = dim
        self.model = model
        self.client = OpenAI(api_key=api_key)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # OpenAI rejects empty strings; substitute a space so indexes line up.
        clean = [t if (t and t.strip()) else " " for t in texts]
        out: list[list[float]] = []
        for i in range(0, len(clean), self._MAX_BATCH):
            batch = clean[i : i + self._MAX_BATCH]
            resp = self.client.embeddings.create(
                model=self.model, input=batch, dimensions=self.dim
            )
            out.extend(d.embedding for d in resp.data)
        return out

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


def _make_stub() -> Embedder:
    return StubEmbedder(dim=settings.embed_dim)


def _make_openai() -> Embedder:
    if not settings.openai_api_key:
        raise RuntimeError(
            "EMBED_PROVIDER=openai but OPENAI_API_KEY is not set in .env."
        )
    return OpenAIEmbedder(
        dim=settings.embed_dim,
        model=settings.embed_model or "text-embedding-3-small",
        api_key=settings.openai_api_key,
    )


def _not_implemented(name: str):
    def _factory() -> Embedder:
        raise NotImplementedError(
            f"EMBED_PROVIDER='{name}' is not wired yet. Implement its class in "
            f"embeddings.py and add it to _PROVIDERS, then set its API key in .env. "
            f"Until then use EMBED_PROVIDER=stub."
        )
    return _factory


_PROVIDERS = {
    "stub": _make_stub,
    "openai": _make_openai,
    "cohere": _not_implemented("cohere"),
    "voyage": _not_implemented("voyage"),
}


def get_embedder() -> Embedder:
    provider = (settings.embed_provider or "stub").lower()
    factory = _PROVIDERS.get(provider)
    if factory is None:
        raise ValueError(
            f"Unknown EMBED_PROVIDER='{provider}'. "
            f"Options: {', '.join(_PROVIDERS)}."
        )
    return factory()


def build_embedding_text(
    description_en: str | None, description_ar: str | None, *extra: str | None
) -> str:
    """The text we embed for a catalog item: bilingual descriptions (EN + AR)
    plus any extra context terms (industry, category, brand, model) that sharpen
    semantic matching. Empty/None parts are dropped."""
    return "\n".join(p for p in (description_en, description_ar, *extra) if p)
