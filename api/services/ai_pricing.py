"""LLM provider pricing table + PriceLookup service (v2.6 M2.2 / Cycle AA).

Per docs/pending/2026-05-29_m2_pricing_table.md (approved 2026-05-29).

Single source of truth for "how many dollars does N tokens of model M cost?".
Drivers in ``api/services/providers/`` MUST NOT compute money themselves
(architecture test enforces this); they emit a placeholder
``cost_estimate_usd=0.0`` and AIRouter overwrites it with the real
PriceLookup value via ``dataclasses.replace`` after the call returns.

Why this module is Python (not JSON):
    - ``decimal.Decimal`` literals are native here (JSON has no Decimal type;
      you'd be storing strings and parsing on load — losing the type-check
      we get for free in Python).
    - The mapping is wrapped in ``MappingProxyType`` so it's runtime-
      immutable in Python; an equivalent JSON-loaded dict would need a
      separate read-once wrapper to get the same guarantee.
    - Matches the existing pattern in ``ai_router.py`` (all constants in
      code).
    - Trade-off accepted: changing a price requires a deploy, not a config
      edit. Pricing changes are infrequent (months, not days), so the
      trade is acceptable for v3.0.

Why ``Decimal`` not ``float``:
    Financial arithmetic with floats accumulates rounding error
    (``0.1 + 0.2 != 0.3``). For per-call cost estimates measured in
    millionths-of-a-dollar, a single float multiplication is fine, but
    sums-of-thousands-of-rows for monthly billing are not. We use Decimal
    end-to-end inside this module, and convert to float only at the
    AIResponse boundary where the field is typed ``float`` for
    JSON-serialisation friendliness.

Update cadence:
    Review prices every 90 days. The ``LAST_REVIEWED`` constant signals
    staleness — see PLAN-V3.0.md M2.2.
"""

from __future__ import annotations

from decimal import Decimal
from types import MappingProxyType
from typing import Mapping

from api.services.ai_router import UnknownModelError


# ---------------------------------------------------------------------------
# Staleness marker
# ---------------------------------------------------------------------------

LAST_REVIEWED: str = "2026-05-27"
"""ISO date when the prices below were last audited against provider
public pricing pages. If this is more than 90 days stale, expect drift
and review before relying on cost estimates for billing decisions."""


# ---------------------------------------------------------------------------
# The pricing table
# ---------------------------------------------------------------------------

# Per-1M-token unit prices in USD. Schema for each entry:
#   {
#     "input_per_1m":  Decimal,   # USD per 1,000,000 prompt tokens
#     "output_per_1m": Decimal,   # USD per 1,000,000 completion tokens
#     "vision":        bool,      # does this model accept image inputs?
#   }
#
# Sourced from provider public pricing pages on 2026-05-27. Per PLAN-V3.0.md
# M2.2 plus one addition (gemini-1.5-flash) since api/services/ai_analyzer.py
# still references that model string directly until its M2-followup migration.
_PRICING_RAW: dict[tuple[str, str], dict] = {
    # OpenAI ───────────────────────────────────────────────────────────────
    ("openai", "gpt-4o"): {
        "input_per_1m":  Decimal("2.50"),
        "output_per_1m": Decimal("10.00"),
        "vision": True,
    },
    ("openai", "gpt-4o-mini"): {
        "input_per_1m":  Decimal("0.15"),
        "output_per_1m": Decimal("0.60"),
        "vision": True,
    },
    # Gemini ───────────────────────────────────────────────────────────────
    ("gemini", "gemini-2.0-flash"): {
        "input_per_1m":  Decimal("0.075"),
        "output_per_1m": Decimal("0.30"),
        "vision": True,
    },
    ("gemini", "gemini-1.5-flash"): {
        # Added beyond PLAN-V3.0.md M2.2 because ai_analyzer.py still calls
        # this model string directly. Same per-token rate as the 2.0 flash
        # tier per Google's published pricing.
        "input_per_1m":  Decimal("0.075"),
        "output_per_1m": Decimal("0.30"),
        "vision": True,
    },
    ("gemini", "gemini-1.5-flash-8b"): {
        "input_per_1m":  Decimal("0.04"),
        "output_per_1m": Decimal("0.15"),
        "vision": False,
    },
    # Anthropic ────────────────────────────────────────────────────────────
    ("anthropic", "claude-3-5-sonnet"): {
        "input_per_1m":  Decimal("3.00"),
        "output_per_1m": Decimal("15.00"),
        "vision": True,
    },
    ("anthropic", "claude-3-5-haiku"): {
        "input_per_1m":  Decimal("0.80"),
        "output_per_1m": Decimal("4.00"),
        "vision": True,
    },
    # DeepSeek ─────────────────────────────────────────────────────────────
    ("deepseek", "deepseek-chat"): {
        "input_per_1m":  Decimal("0.27"),
        "output_per_1m": Decimal("1.10"),
        "vision": False,
    },
}

# Runtime-immutable view. MappingProxyType is the read-only wrapper Python
# uses for `type.__dict__` and similar; it raises TypeError on any attempt
# to mutate. Callers cannot accidentally (or deliberately) add a pricing
# entry by mutating ``PRICING[...]`` at runtime — they'd have to edit this
# module and ship a new deploy.
PRICING: Mapping[tuple[str, str], dict] = MappingProxyType(_PRICING_RAW)


# ---------------------------------------------------------------------------
# PriceLookup service
# ---------------------------------------------------------------------------

_ONE_MILLION = Decimal("1000000")


class PriceLookup:
    """Stateless service that maps (provider, model, token counts) to a
    USD cost. Use the module-level :data:`price_lookup` instance.

    No state, no caching beyond the static PRICING table. Method is
    classmethod-style but kept as instance method so the module exports
    a singleton object — mirrors the AIRouter pattern and lets test
    code mock ``price_lookup.calculate_cost`` in one place.
    """

    def calculate_cost(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> Decimal:
        """Compute USD cost as a ``Decimal``.

        Raises:
            UnknownModelError: if ``(provider, model)`` has no pricing
                entry. Per the M2.2 spec's "no null costs" rule, we
                surface this as a hard failure rather than returning
                Decimal('0') — a silent zero would corrupt billing data.

        Notes:
            - Negative token counts are treated as zero. A driver that
              fails to extract tokens emits 0 (Cycle Z contract); we
              don't penalise the caller with a ValueError for a
              defensive case the upstream layer already handled.
            - The math: ``input_tokens / 1_000_000 * input_per_1m``
              plus the equivalent for output. Done in Decimal so the
              cents accumulate exactly across many calls.
        """
        key = (provider, model)
        entry = PRICING.get(key)
        if entry is None:
            raise UnknownModelError(
                f"No pricing entry for provider={provider!r} model={model!r}. "
                f"Either add it to api/services/ai_pricing.py PRICING, or "
                f"check for a typo in the caller's ModelConfig.model string. "
                f"Known models: {sorted({m for _, m in PRICING.keys()})}"
            )

        in_tokens = max(0, int(input_tokens))
        out_tokens = max(0, int(output_tokens))

        input_cost = (
            Decimal(in_tokens) / _ONE_MILLION * entry["input_per_1m"]
        )
        output_cost = (
            Decimal(out_tokens) / _ONE_MILLION * entry["output_per_1m"]
        )
        return input_cost + output_cost

    def supports_vision(self, provider: str, model: str) -> bool:
        """Convenience accessor for the ``vision`` flag. Useful for
        future AIRouter logic that wants to reject ``call_vision``
        against a text-only model before burning a request."""
        entry = PRICING.get((provider, model))
        if entry is None:
            raise UnknownModelError(
                f"No pricing entry for provider={provider!r} model={model!r}."
            )
        return bool(entry["vision"])


# Module-level singleton — import as ``from api.services.ai_pricing
# import price_lookup``. Do NOT instantiate PriceLookup() elsewhere.
price_lookup = PriceLookup()
