"""Configurable LLM interface for the matching engine.

The matching engine only calls `get_matcher().propose_assembly(scope, candidates)`
and receives a validated `LLMAssembly`. Two providers:

  * "stub"      — offline, no key. Picks the top retrieved candidate so the whole
                  pipeline runs and Stage 5 can be built. Not real reasoning.
  * "anthropic" — Claude via the official SDK, using STRUCTURED OUTPUTS so the
                  model is constrained to emit schema-valid JSON (no fragile
                  text parsing). The editable system/user prompts live in
                  app/prompts/*.txt.

Switch providers with LLM_PROVIDER in .env. The LLMAssembly schema below is the
contract between the prompt and the engine — edit prompts freely; change the
schema only if you also update the engine.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from .config import settings

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"


# --- The structured output contract -----------------------------------------


class LLMComponent(BaseModel):
    # Must be one of the candidate codes, or null if nothing fits.
    catalog_item_code: str | None
    # Quantity of this item needed per ONE unit of the scope line.
    quantity_per_unit: float
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str


class LLMAssembly(BaseModel):
    scope_understanding: str
    overall_confidence: float = Field(ge=0.0, le=1.0)
    components: list[LLMComponent]


class LLMLineResult(BaseModel):
    line_index: int  # which scope line in the batch this is for
    overall_confidence: float = Field(ge=0.0, le=1.0)
    components: list[LLMComponent]


class LLMBatch(BaseModel):
    results: list[LLMLineResult]


# RFP analysis contract (narrative document -> sections -> items)


class AnalyzedItem(BaseModel):
    description: str
    quantity: float | None
    unit: str | None


class AnalyzedSection(BaseModel):
    title: str
    items: list[AnalyzedItem]


class AnalyzedRFP(BaseModel):
    sections: list[AnalyzedSection]


# --- Prompt loading (read each call so edits apply without a restart) --------


def _load_prompt(name: str) -> str:
    return (PROMPT_DIR / name).read_text(encoding="utf-8")


def _format_candidates(candidates: list[dict]) -> str:
    if not candidates:
        return "  (no candidates found)"
    lines = []
    for c in candidates:
        lines.append(
            f"  - code={c['code']} | unit={c.get('unit')} | brand={c.get('brand')}\n"
            f"      EN: {c.get('description_en')}\n"
            f"      AR: {c.get('description_ar')}"
        )
    return "\n".join(lines)


def render_user_prompt(scope: dict, candidates: list[dict]) -> str:
    return _load_prompt("matching_user.txt").format(
        description=scope.get("description"),
        quantity=scope.get("quantity"),
        unit=scope.get("unit"),
        candidates=_format_candidates(candidates),
    )


def render_batch_user_prompt(lines: list[dict]) -> str:
    """Build ONE prompt covering many scope lines, each with its own candidates.
    `lines` = [{index, scope:{description,quantity,unit}, candidates:[...]}]."""
    blocks = []
    for ln in lines:
        s = ln["scope"]
        blocks.append(
            f"=== LINE {ln['index']} ===\n"
            f"Description: {s.get('description')}\n"
            f"Quantity: {s.get('quantity')}  Unit: {s.get('unit')}\n"
            f"Candidates (choose only from these codes):\n"
            f"{_format_candidates(ln['candidates'])}"
        )
    header = (
        "Price EVERY scope line below against this contractor's catalog. For each "
        "line return its line_index and the catalog item(s) it needs (an assembly "
        "may be several items), each with quantity_per_unit, confidence and reason. "
        "Match across Arabic/English by meaning; choose only from that line's "
        "candidate codes, or null if none fits.\n\n"
    )
    return header + "\n\n".join(blocks)


# --- Providers ---------------------------------------------------------------


class StubMatcher:
    """Offline placeholder: pick the single best-retrieved candidate.

    Confidence comes from the retrieval similarity, so genuinely weak matches
    score low and get flagged — enough to exercise Stage 5 end-to-end. This does
    NOT reason about assemblies; switch to the anthropic provider for that.
    """

    def propose_assembly(self, scope: dict, candidates: list[dict]) -> LLMAssembly:
        if not candidates:
            return LLMAssembly(
                scope_understanding=scope.get("description", ""),
                overall_confidence=0.1,
                components=[
                    LLMComponent(
                        catalog_item_code=None,
                        quantity_per_unit=1.0,
                        confidence=0.1,
                        reason="stub: no catalog candidates retrieved",
                    )
                ],
            )
        top = candidates[0]
        sim = float(top.get("similarity") or 0.0)
        conf = round(max(0.0, min(0.99, sim)), 2)
        return LLMAssembly(
            scope_understanding=scope.get("description", ""),
            overall_confidence=conf,
            components=[
                LLMComponent(
                    catalog_item_code=top["code"],
                    quantity_per_unit=1.0,
                    confidence=conf,
                    reason="stub: top lexical match by vector similarity",
                )
            ],
        )

    def propose_batch(self, lines: list[dict]) -> LLMBatch:
        results = []
        for ln in lines:
            a = self.propose_assembly(ln["scope"], ln["candidates"])
            results.append(
                LLMLineResult(
                    line_index=ln["index"],
                    overall_confidence=a.overall_confidence,
                    components=a.components,
                )
            )
        return LLMBatch(results=results)

    def analyze_rfp(self, document_text: str, guidance: str = "", sample_text: str = "") -> AnalyzedRFP:
        # Offline placeholder: keep non-trivial lines as one section. NOT real
        # analysis — use the anthropic provider for genuine structuring.
        items = []
        for raw in document_text.splitlines():
            t = raw.strip()
            if len(t) > 12 and not t.startswith("[Table") and not t.startswith("# Sheet"):
                items.append(AnalyzedItem(description=t[:300], quantity=None, unit=None))
        return AnalyzedRFP(sections=[AnalyzedSection(title="Scope of Work", items=items[:50])])


class AnthropicMatcher:
    """Claude via the Anthropic SDK with structured outputs (constrained JSON)."""

    def __init__(self):
        import anthropic  # lazy import so stub users don't need the SDK/key

        if not settings.anthropic_api_key:
            raise RuntimeError(
                "LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set in .env."
            )
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.llm_model

    def propose_assembly(self, scope: dict, candidates: list[dict]) -> LLMAssembly:
        response = self._client.messages.parse(
            model=self._model,
            max_tokens=2048,
            system=_load_prompt("matching_system.txt"),
            messages=[
                {"role": "user", "content": render_user_prompt(scope, candidates)}
            ],
            output_format=LLMAssembly,  # structured outputs → schema-valid JSON
        )
        parsed = response.parsed_output
        if parsed is None:
            # Refusal or truncation — surface as a flagged, unmatched line.
            return LLMAssembly(
                scope_understanding=scope.get("description", ""),
                overall_confidence=0.0,
                components=[
                    LLMComponent(
                        catalog_item_code=None,
                        quantity_per_unit=1.0,
                        confidence=0.0,
                        reason=f"LLM returned no structured output "
                        f"(stop_reason={response.stop_reason})",
                    )
                ],
            )
        return parsed

    def propose_batch(self, lines: list[dict]) -> LLMBatch:
        """Price many scope lines in ONE call (far fewer calls than per-line)."""
        return self._batch_call(_load_prompt("matching_system.txt"), lines)

    def _batch_call(self, system: str, lines: list[dict], depth: int = 0) -> LLMBatch:
        try:
            response = self._client.messages.parse(
                model=self._model,
                max_tokens=16000,
                system=system,
                messages=[{"role": "user", "content": render_batch_user_prompt(lines)}],
                output_format=LLMBatch,
            )
            return response.parsed_output or LLMBatch(results=[])
        except Exception:
            # Output too long for one response: split the batch and retry.
            if depth < 4 and len(lines) > 1:
                mid = len(lines) // 2
                first = self._batch_call(system, lines[:mid], depth + 1)
                second = self._batch_call(system, lines[mid:], depth + 1)
                return LLMBatch(results=first.results + second.results)
            return LLMBatch(results=[])

    def analyze_rfp(self, document_text: str, guidance: str = "", sample_text: str = "") -> AnalyzedRFP:
        # Large RFPs would overflow a single response's token cap and truncate the
        # JSON. Split the document into chunks (preferring sheet/page boundaries),
        # analyze each, and merge — so each call's output stays complete. The
        # user's guidance + an optional reference BoQ sample are prepended to every
        # chunk so they steer the structure consistently.
        system = _load_prompt("rfp_analysis_system.txt")
        preamble = _analysis_preamble(guidance, sample_text)
        sections: list[AnalyzedSection] = []
        for chunk in _chunk_text(document_text):
            sections.extend(self._analyze_chunk(system, preamble + chunk))
        return AnalyzedRFP(sections=_merge_sections(sections))

    def _analyze_chunk(self, system: str, chunk: str, depth: int = 0) -> list[AnalyzedSection]:
        try:
            response = self._client.messages.parse(
                model=self._model,
                max_tokens=16000,
                system=system,
                messages=[{"role": "user", "content": chunk}],
                output_format=AnalyzedRFP,
            )
            return response.parsed_output.sections if response.parsed_output else []
        except Exception:
            # Output still too long (or a transient error): split and retry.
            if depth < 3 and len(chunk) > 2000:
                mid = chunk.rfind("\n", 0, len(chunk) // 2)
                if mid <= 0:
                    mid = len(chunk) // 2
                return self._analyze_chunk(system, chunk[:mid], depth + 1) + self._analyze_chunk(
                    system, chunk[mid:], depth + 1
                )
            return []


_PROVIDERS = {
    "stub": StubMatcher,
    "anthropic": AnthropicMatcher,
}


def get_matcher():
    provider = (settings.llm_provider or "stub").lower()
    factory = _PROVIDERS.get(provider)
    if factory is None:
        raise ValueError(
            f"Unknown LLM_PROVIDER='{provider}'. Options: {', '.join(_PROVIDERS)}."
        )
    return factory()


def _chunk_text(text: str, max_chars: int = 30000) -> list[str]:
    """Split flattened RFP text into chunks for analysis ONLY when it's large —
    a normal RFP fits in one chunk (one call). Breaks on line boundaries and
    prefers Excel sheet / PDF page boundaries."""
    lines = text.split("\n")
    chunks: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for line in lines:
        boundary = line.startswith("# Sheet:") or line.startswith("[Page ")
        if cur and (cur_len + len(line) + 1 > max_chars or (boundary and cur_len > max_chars * 0.5)):
            chunks.append("\n".join(cur))
            cur, cur_len = [], 0
        cur.append(line)
        cur_len += len(line) + 1
    if cur:
        chunks.append("\n".join(cur))
    return chunks or [text]


def _analysis_preamble(guidance: str = "", sample_text: str = "") -> str:
    """User-provided context prepended to each analysis chunk. Empty if none."""
    parts = []
    if guidance and guidance.strip():
        parts.append(
            "USER GUIDANCE — important context for interpreting this RFP "
            "(follow it):\n" + guidance.strip()
        )
    if sample_text and sample_text.strip():
        # Cap the sample so it conveys structure without ballooning tokens.
        parts.append(
            "REFERENCE BoQ SAMPLE — mirror its structure, columns and section "
            "style where it fits this RFP:\n" + sample_text.strip()[:4000]
        )
    return ("\n\n".join(parts) + "\n\n---\n\n") if parts else ""


def _merge_sections(sections: list[AnalyzedSection]) -> list[AnalyzedSection]:
    """Combine sections that share a title (e.g. one split across chunks)."""
    merged: dict[str, AnalyzedSection] = {}
    order: list[str] = []
    for s in sections:
        key = (s.title or "").strip().lower()
        if key not in merged:
            merged[key] = AnalyzedSection(title=s.title, items=list(s.items))
            order.append(key)
        else:
            merged[key].items.extend(s.items)
    return [merged[k] for k in order]
