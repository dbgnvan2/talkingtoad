"""AIRouter — centralised LLM provider orchestrator (v2.6 M2.1 / Cycle Z).

Per docs/pending/2026-05-29_m2_airouter.md (skeleton-first scope, approved
2026-05-29).

This module is the single entry point for every LLM call in the codebase.
Callers go through ``ai_router.call_text(...)`` or
``ai_router.call_vision(...)``; the router selects a provider, resolves
credentials, dispatches to a driver under ``api/services/providers/``,
and records usage metadata.

Stub layers in this cycle (concrete implementations land in later M2.x):
    - ``_lookup_customer_credentials`` → always returns None (M2.3 wires
      to the customer_ai_credentials table once it exists).
    - ``_log_usage`` → INFO-log only (M2.5 wires to the ai_usage table).
    - ``cost_estimate_usd`` on AIResponse is always 0.0 (M2.2 wires the
      pricing table).

Thread-safety: module-level singleton instantiation. FastAPI workers
run async-single-threaded; the module load is the natural single-init
point. No lazy-init lock dance needed.

Negative constraints (enforced):
    - No API keys cached in singleton state.
    - No raw prompt/response text in log_usage metadata.
    - No provider SDK imports in any caller — drivers use httpx directly.
    - No silent failures: hard errors raise; soft truncation flags.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Driver Protocol — kept behind TYPE_CHECKING so base.py can import
    # AIResponse / ModelConfig from us without a circular import at
    # runtime.
    from api.services.providers.base import ProviderDriver

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

SYSTEM_CONTEXT_ID = "system_account"
"""Reserved customer_id used when no per-customer identity flows in.

Until M2.3 (customer_ai_credentials) and a multi-tenant identity model
land, every authenticated call uses this constant. The usage logger
distinguishes system-funded traffic from real customer traffic via this
ID so per-customer billing rollups can be built later without retroactive
data backfill."""


_SAFE_METADATA_KEYS: frozenset[str] = frozenset({
    "customer_id",
    "provider",
    "model",
    "input_token_count",
    "output_token_count",
    "cost_estimate_usd",
    "task_type",
    "success",
    "error_message",
    "timestamp",
})
"""Whitelist of keys allowed in log_usage metadata.

Privacy guard: raw prompt or response text MUST NOT be persisted to the
usage log (prompts can contain PII, customer content, etc.). Any key
not in this set is silently dropped by ``_log_usage``. The whitelist is
audited by ``tests/test_ai_router.py``."""


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ModelConfig:
    """Sparse model-call configuration.

    Intentionally minimal (3 fields). Provider-specific knobs like
    ``top_p``, ``frequency_penalty``, ``presence_penalty`` are NOT
    surfaced here — that would leak the abstraction and force every
    driver to handle every provider's parameter set. The user / system
    architect approved this sparse interface 2026-05-29.

    To add a parameter in the future, weigh: does every supported provider
    (OpenAI, Gemini, Anthropic, DeepSeek) implement it consistently? If
    not, it doesn't belong here — it belongs in a provider-specific
    config object passed alongside.
    """

    model: str
    """The provider-specific model identifier (e.g. ``"gpt-4o"``,
    ``"gemini-2.0-flash"``). The router does NOT validate this string;
    the driver passes it through to the provider API."""

    max_tokens: int | None = None
    """Hard cap on output tokens. ``None`` means use the provider default."""

    temperature: float = 0.2
    """Sampling temperature. Default 0.2 matches the existing rewriter
    behaviour (low randomness for faithful rewriting)."""


@dataclass(frozen=True)
class AIResponse:
    """Unified result envelope returned by every driver.

    Hard failures raise (see exception hierarchy below); this dataclass
    is only constructed on a successful or soft-failure call. A "soft
    failure" today is exactly one case: the provider truncated the
    response at the ``max_tokens`` boundary. Callers detect this via
    ``truncated``.
    """

    content: str
    """The LLM's response text. May be empty if the provider returned
    no parseable content; the driver guarantees this is a string."""

    provider_id: str
    """Short provider identifier — ``"openai"``, ``"gemini"``, ..."""

    model: str
    """Echo of the requested ``ModelConfig.model``."""

    input_token_count: int
    """Tokens consumed by the prompt + system instruction. 0 if the
    provider didn't return usage data."""

    output_token_count: int
    """Tokens produced in the response. 0 if the provider didn't return
    usage data."""

    cost_estimate_usd: float
    """USD cost estimate, computed from the pricing table.
    TODO(M2.2): always 0.0 today; pricing table lands in M2.2."""

    truncated: bool
    """``True`` iff the response stopped because of ``max_tokens``. The
    caller decides whether to surface this to the end user — the router
    treats it as a soft success, NOT a failure."""


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------

class AIRouterError(Exception):
    """Base class for everything the router can raise. Calling routers
    should catch this to map every AI-call failure to a single 5xx /
    402 response shape."""


class ProviderAuthError(AIRouterError):
    """Raised when no credentials are available: neither a customer key
    nor a system env key. The advisor / AI routers should map this to
    HTTP 402 (Payment Required) with a user-facing message asking the
    customer to set an API key in Settings.

    Code paths:
        - Customer hasn't set their own key AND no system env fallback.
        - Customer's key was deleted between credential lookup and call
          (race condition — vanishingly rare but possible)."""


class ProviderAPIError(AIRouterError):
    """Raised when a provider HTTP call fails hard: transport error
    (DNS, timeout, connection reset), non-200 response, or a
    parse-time KeyError because the response shape didn't match what
    the driver expects.

    Triggers an entry in the usage log with ``success=False`` — the
    router's try/except in ``call_text`` / ``call_vision`` wraps the
    driver call to ensure this happens even when the underlying
    HTTP error preempts the success-path logging."""


# ---------------------------------------------------------------------------
# Stub layers — concrete implementations land in M2.3 + M2.5
# ---------------------------------------------------------------------------

def _lookup_customer_credentials(
    customer_id: str, provider: str
) -> str | None:
    """Resolve a per-customer API key for the given provider.

    TODO(M2.3): wire to ``customer_ai_credentials`` table with Fernet
    decryption. The table doesn't exist yet — this stub always returns
    None, forcing the caller to fall through to the system env key.

    Returning None vs raising: None is the natural "no key set"
    signal. Callers handle None explicitly.
    """
    return None


def _log_usage(metadata: dict) -> None:
    """Record an ai_usage event.

    TODO(M2.5): persist to ``ai_usage`` table for billing rollups.
    Until M2.5 lands, this emits a structured INFO log entry — good
    enough for observability while we ship M2.1.

    Privacy contract: ``metadata`` keys outside ``_SAFE_METADATA_KEYS``
    are silently dropped. This is the firewall that keeps prompt /
    response text out of the usage log. The whitelist is enforced
    deliberately silently (not as an assertion) because a missed
    sanitisation upstream should never crash a paid AI call — it
    should just leave less detail in the audit trail.
    """
    safe = {k: v for k, v in metadata.items() if k in _SAFE_METADATA_KEYS}
    logger.info("ai_usage", extra=safe)


# ---------------------------------------------------------------------------
# Driver registry + selection
# ---------------------------------------------------------------------------

def _get_drivers() -> dict[str, "ProviderDriver"]:
    """Build the driver registry. Function-scoped to defer provider
    module imports until first call — avoids importing httpx-using
    modules at AIRouter import time (faster cold start, easier mocking).
    """
    from api.services.providers.gemini import GeminiDriver
    from api.services.providers.openai import OpenAIDriver

    return {
        "openai": OpenAIDriver(),
        "gemini": GeminiDriver(),
    }


_PROVIDER_ENV_VARS = {
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
}
"""Env var name to read for each provider's system-default key. Until
per-customer credentials land (M2.3), these env vars are the *only*
source of API keys."""


_DEFAULT_PROVIDER_PREFERENCE = ("openai", "gemini")
"""Provider try-order when the caller hasn't expressed a preference.
Matches the existing rewriter behaviour (OpenAI preferred, Gemini fallback)."""


# ---------------------------------------------------------------------------
# The router itself
# ---------------------------------------------------------------------------

class AIRouter:
    """Singleton orchestrator. Use the module-level :data:`ai_router`
    instance; do NOT instantiate this class directly elsewhere — that
    would defeat the "single source of truth" property.

    No instance state holds API keys or customer data. Keys are fetched
    per call from ``_lookup_customer_credentials`` (M2.3 stub) or the
    process environment, used once for the HTTP call, and discarded.
    """

    def __init__(self) -> None:
        self._drivers: dict[str, "ProviderDriver"] | None = None

    def _drivers_lazy(self) -> dict[str, "ProviderDriver"]:
        if self._drivers is None:
            self._drivers = _get_drivers()
        return self._drivers

    # ── credential resolution ───────────────────────────────────────────
    def _resolve_credentials(
        self, customer_id: str
    ) -> tuple[str, str]:
        """Pick a (provider_id, api_key) pair using the fallback chain:

            1. Per-customer key for any supported provider (M2.3 stub).
            2. System env key for any supported provider.
            3. Raise ProviderAuthError.

        Returns the first provider in ``_DEFAULT_PROVIDER_PREFERENCE``
        that has a usable key. The customer-key check uses the same
        preference order — a customer who has set both OpenAI and Gemini
        keys gets OpenAI by default, matching the system-env behaviour.
        """
        # M2.3 stub — always returns None for now. Once M2.3 lands this
        # will resolve a real per-customer key. Keep the loop structure
        # so the logic does NOT need to change at M2.3 time.
        for provider in _DEFAULT_PROVIDER_PREFERENCE:
            customer_key = _lookup_customer_credentials(customer_id, provider)
            if customer_key:
                return provider, customer_key

        for provider in _DEFAULT_PROVIDER_PREFERENCE:
            env_var = _PROVIDER_ENV_VARS[provider]
            env_key = os.getenv(env_var, "").strip()
            if env_key:
                return provider, env_key

        raise ProviderAuthError(
            f"No AI credentials available for customer_id={customer_id!r}. "
            f"Set per-customer API key in Settings, or configure one of: "
            f"{', '.join(sorted(_PROVIDER_ENV_VARS.values()))}."
        )

    # ── text calls ──────────────────────────────────────────────────────
    async def call_text(
        self,
        *,
        customer_id: str,
        system_prompt: str,
        user_prompt: str,
        model_config: ModelConfig,
    ) -> AIResponse:
        return await self._call(
            customer_id=customer_id,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            image_bytes=None,
            image_mime=None,
            model_config=model_config,
        )

    # ── vision calls ────────────────────────────────────────────────────
    async def call_vision(
        self,
        *,
        customer_id: str,
        system_prompt: str,
        image_bytes: bytes,
        image_mime: str,
        model_config: ModelConfig,
    ) -> AIResponse:
        return await self._call(
            customer_id=customer_id,
            system_prompt=system_prompt,
            user_prompt="",
            image_bytes=image_bytes,
            image_mime=image_mime,
            model_config=model_config,
        )

    # ── shared dispatch path ────────────────────────────────────────────
    async def _call(
        self,
        *,
        customer_id: str,
        system_prompt: str,
        user_prompt: str,
        image_bytes: bytes | None,
        image_mime: str | None,
        model_config: ModelConfig,
    ) -> AIResponse:
        provider_id, api_key = self._resolve_credentials(customer_id)
        driver = self._drivers_lazy()[provider_id]

        # Wrap the driver call so log_usage fires even on hard error.
        # See Unit Test 3 (Isolation) — log_usage MUST be called even
        # when the provider raises a transport error. Without this
        # try/except wrapper the usage trail would silently disappear
        # exactly when something went wrong, breaking billing accuracy
        # for failed requests.
        try:
            if image_bytes is not None:
                response = await driver.call_vision(
                    api_key=api_key,
                    system_prompt=system_prompt,
                    image_bytes=image_bytes,
                    image_mime=image_mime or "image/jpeg",
                    model_config=model_config,
                )
            else:
                response = await driver.call_text(
                    api_key=api_key,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model_config=model_config,
                )
        except Exception as exc:
            _log_usage({
                "customer_id": customer_id,
                "provider": provider_id,
                "model": model_config.model,
                "input_token_count": 0,
                "output_token_count": 0,
                "cost_estimate_usd": 0.0,
                "success": False,
                "error_message": str(exc)[:500],
            })
            # Re-raise so the calling router can map this to 5xx / 402.
            raise

        _log_usage({
            "customer_id": customer_id,
            "provider": provider_id,
            "model": model_config.model,
            "input_token_count": response.input_token_count,
            "output_token_count": response.output_token_count,
            "cost_estimate_usd": response.cost_estimate_usd,
            "success": True,
            "error_message": None,
        })
        return response


# Module-level singleton. Importing modules use `ai_router.call_text(...)`
# directly; do NOT instantiate AIRouter() elsewhere.
ai_router = AIRouter()
