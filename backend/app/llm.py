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

    def analyze_rfp(self, document_text: str) -> AnalyzedRFP:
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

    def analyze_rfp(self, document_text: str) -> AnalyzedRFP:
        response = self._client.messages.parse(
            model=self._model,
            max_tokens=8192,
            system=_load_prompt("rfp_analysis_system.txt"),
            messages=[{"role": "user", "content": document_text}],
            output_format=AnalyzedRFP,
        )
        return response.parsed_output or AnalyzedRFP(sections=[])


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
