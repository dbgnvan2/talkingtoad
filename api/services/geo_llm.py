"""R8 — LLM-driven GEO checks (audit remediation, 2026-07-04).

Implements three checks that a static heuristic can't do, via an LLM classifier
on the existing AI integration (reuses ``ai_analyzer``'s router + config-driven
model selection — no hardcoded model IDs, per llm-integration.md L1):

    CENTRAL_CLAIM_BURIED           — the main answer/claim is not near the top
    CHUNKS_NOT_SELF_CONTAINED      — sections can't stand alone when quoted
    PROMOTIONAL_CONTENT_INTERRUPTS — promo/CTA blocks interrupt the content

Standards: llm-integration.md (L4 structured output + parse; P14 error-as-content
guard) and external-api.md (the router owns timeout/retry). A failed/refused LLM
response is NEVER rendered as a finding.

P14: the LLM layer (``_call_llm``) raises :class:`AIAnalysisError` on any failure
instead of returning a sentinel error *string* — so an error can never be parsed
as a verdict. ``classify_geo_llm`` catches it and yields an empty verdict (``{}``),
``parse_geo_verdict`` still defends against empty/garbage/non-JSON output (L4).
"""

from __future__ import annotations

import json
import logging

from api.crawler.checkers.registry import make_issue
from api.services.ai_analyzer import AIAnalysisError

logger = logging.getLogger(__name__)

# verdict-key → issue code
_CODE = {
    "central_claim_buried": "CENTRAL_CLAIM_BURIED",
    "chunks_not_self_contained": "CHUNKS_NOT_SELF_CONTAINED",
    "promotional_content_interrupts": "PROMOTIONAL_CONTENT_INTERRUPTS",
}
_KEYS = tuple(_CODE)

_MAX_TEXT_CHARS = 6000

_PROMPT = (
    "You are a GEO (generative-engine-optimization) analyst. Judge the PAGE TEXT on three "
    "criteria and reply with ONLY a JSON object (no prose, no code fence):\n"
    '{"central_claim_buried": <bool>, "chunks_not_self_contained": <bool>, '
    '"promotional_content_interrupts": <bool>}\n'
    "Definitions:\n"
    "- central_claim_buried: the page's main answer/claim is NOT stated near the top "
    "(a reader must scroll past setup to find it).\n"
    "- chunks_not_self_contained: sections/paragraphs depend on earlier context and would be "
    "unclear if quoted alone by an AI answer engine.\n"
    "- promotional_content_interrupts: promotional or call-to-action blocks interrupt the "
    "informational flow.\n"
    "Respond true only when clearly the case.\n\nPAGE TEXT:\n"
)


def parse_geo_verdict(raw: str) -> dict:
    """Extract the ``{key: bool}`` verdict from an LLM response.

    Returns ``{}`` for empty output or any unparseable / non-JSON output (L4) —
    the caller then emits nothing. Only boolean values are kept. (Errors no
    longer arrive here as strings — ``_call_llm`` raises AIAnalysisError, P14.)
    """
    if not raw or not raw.strip():
        return {}
    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1
        data = json.loads(raw[start:end])
    except (ValueError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: bool(data[k]) for k in _KEYS if isinstance(data.get(k), bool)}


async def _call_llm(text: str) -> str:
    """Run the classifier prompt through the existing AI router. Reuses
    ai_analyzer's config-driven model (no hardcoded ID).

    Returns the raw LLM response string on success. Raises
    :class:`AIAnalysisError` on any failure (no key, provider error, timeout).
    (P14) It no longer returns an error-sentinel string that could be parsed
    as a verdict — failure is unambiguous and handled by ``classify_geo_llm``.
    """
    try:
        from api.services.ai_analyzer import (
            ai_router, _pick_model, _DEFAULT_TEXT_MODEL_BY_PROVIDER,
            SYSTEM_CONTEXT_ID, ModelConfig,
        )
        _provider, cfg = _pick_model(_DEFAULT_TEXT_MODEL_BY_PROVIDER)
        cfg = ModelConfig(model=cfg.model, max_tokens=200)
        response = await ai_router.call_text(
            customer_id=SYSTEM_CONTEXT_ID,
            system_prompt="",
            user_prompt=_PROMPT + (text or "")[:_MAX_TEXT_CHARS],
            model_config=cfg,
        )
        return response.content
    except Exception as exc:  # ProviderAuthError, timeouts, etc.
        logger.warning("geo_llm_failed", extra={"error": str(exc)})
        raise AIAnalysisError(f"GEO LLM classification failed: {exc}") from exc


async def classify_geo_llm(text: str) -> dict:
    """Return the ``{key: bool}`` GEO verdict for *text* (``{}`` on any failure).

    P14: a failed/refused LLM call raises AIAnalysisError inside ``_call_llm``;
    we catch it and return an empty verdict so no spurious finding is emitted.
    """
    try:
        raw = await _call_llm(text)
    except AIAnalysisError:
        return {}
    return parse_geo_verdict(raw)


def geo_llm_issues(url: str, verdict: dict) -> list:
    """Emit an issue per flagged check. Uses LITERAL make_issue calls so the
    catalogue-liveness grep recognises the codes as live."""
    out: list = []
    if verdict.get("central_claim_buried"):
        out.append(make_issue("CENTRAL_CLAIM_BURIED", url))
    if verdict.get("chunks_not_self_contained"):
        out.append(make_issue("CHUNKS_NOT_SELF_CONTAINED", url))
    if verdict.get("promotional_content_interrupts"):
        out.append(make_issue("PROMOTIONAL_CONTENT_INTERRUPTS", url))
    return out
