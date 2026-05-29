"""
Rewriter service (Tool B) — Apply rewrite prompt to content.

Takes page content + rewrite prompt, produces one rewrite. No iteration,
no scoring, no variants. Simple and straightforward.

v2.6 M2.1 (Cycle Z): refactored to route every LLM call through
:class:`api.services.ai_router.AIRouter`. No direct provider HTTP calls
remain in this file. Per-customer credentials, usage tracking, and
provider selection are now centralised — see
``docs/pending/2026-05-29_m2_airouter.md``.

Behaviour preserved exactly:
    - Same prompt structure (system instruction + "Please rewrite the
      following content:\\n\\n{content}" user message).
    - Same temperature (0.2) for faithful rewriting.
    - Same return shape (:class:`RewriterResult` with ``rewrite`` and
      ``stopped_by_limit`` fields).
    - Same provider preference (OpenAI first, Gemini fallback) — now
      delegated to ``AIRouter._resolve_credentials``.
"""

import logging

from api.models.advisor import RewriterRequest, RewriterResult
from api.services.ai_router import (
    ModelConfig,
    SYSTEM_CONTEXT_ID,
    ai_router,
)

logger = logging.getLogger(__name__)


# Per-provider default models. AIRouter picks the provider via credential
# fallback; we pick the model. Matches the model strings the pre-refactor
# `_call_openai_rewriter` / `_call_gemini_rewriter` used.
_DEFAULT_MODELS_BY_PROVIDER = {
    "openai": "gpt-4o",
    "gemini": "gemini-2.0-flash",
}

# Temperature for rewrites — low to preserve source content fidelity.
_REWRITER_TEMPERATURE = 0.2


async def rewrite_page(request: RewriterRequest) -> RewriterResult:
    """Rewrite page content using an LLM via AIRouter.

    Args:
        request: RewriterRequest with content and prompt.

    Returns:
        RewriterResult with rewritten content and a stopped_by_limit
        flag for when the model hit max_tokens.

    Note on model selection: AIRouter picks the provider based on
    credential availability. We then look up the appropriate model
    string for that provider. This is intentionally a two-step process
    so that when M2.4 (per-task-type model routing) lands, the model
    lookup becomes a router call instead of a local dict, with the
    provider selection unchanged.
    """
    # First call uses an OpenAI default. AIRouter's credential resolution
    # decides which provider actually runs — we discover the real
    # provider from the response and (TODO M2.4) re-select the model
    # if it mismatches. For now the small model-mismatch case is harmless
    # (Gemini ignores model="gpt-4o" and uses whatever the URL specifies).
    #
    # The cleaner path is: ask AIRouter "which provider would you pick?"
    # before making the call so we can pick the right model upfront.
    # That refinement is M2.4 work — for now, pre-flight the selection
    # by attempting cheap resolution.
    try:
        provider, _key = ai_router._resolve_credentials(SYSTEM_CONTEXT_ID)
    except Exception:
        # If resolution would fail, let AIRouter raise the real
        # ProviderAuthError when we actually call below.
        provider = "openai"

    model = _DEFAULT_MODELS_BY_PROVIDER.get(provider, "gpt-4o")
    cfg = ModelConfig(model=model, temperature=_REWRITER_TEMPERATURE)

    response = await ai_router.call_text(
        customer_id=SYSTEM_CONTEXT_ID,
        system_prompt=request.prompt,
        user_prompt=f"Please rewrite the following content:\n\n{request.content}",
        model_config=cfg,
    )

    return RewriterResult(
        rewrite=response.content,
        stopped_by_limit=response.truncated,
    )
