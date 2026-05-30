"""Usage-aggregation API DTOs (v2.6 M2.6 / Cycle EE).

Pydantic response models for ``GET /api/ai/usage/stats``. Designed for
JSON consumption by the future Settings dashboard. All cost fields are
``float`` (JSON-friendly) but reconciliation-grade: the underlying SQL
aggregation snaps each row to integer cents before summing, so the
returned floats are exact to 2 decimal places regardless of input
float jitter.

See docs/pending/2026-05-29_m2_usage_aggregation_api.md §A for the
floating-point safety rationale.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProviderBreakdown(BaseModel):
    """Aggregated usage for one provider within the report period."""

    provider: str
    """Provider id — ``"openai"`` / ``"gemini"`` / ``"anthropic"`` etc."""

    call_count: int = Field(..., ge=0)
    """Total successful + failed calls to this provider in the period."""

    total_input_tokens: int = Field(..., ge=0)
    total_output_tokens: int = Field(..., ge=0)
    total_cost_usd: float = Field(..., ge=0.0)
    """Sum of per-row costs, reconciled to cents via integer-cents SQL
    aggregation. See module docstring."""

    failed_count: int = Field(..., ge=0)
    """Number of calls with ``success=0`` for this provider. Lets ops
    surface per-provider reliability issues."""


class ModelBreakdown(BaseModel):
    """Aggregated usage for one (provider, model) pair."""

    provider: str
    model: str
    call_count: int = Field(..., ge=0)
    total_cost_usd: float = Field(..., ge=0.0)


class UsageReport(BaseModel):
    """Aggregated billing report for a single customer over a date range.

    Returned by ``GET /api/ai/usage/stats``. The endpoint refuses any
    range longer than 90 days (``PERIOD_TOO_LARGE`` 400 error) — see
    :class:`api.services.usage_logger.UsageReader` for the cap.
    """

    period_start: str
    """Echo of the request ``start_date`` (ISO 8601 UTC)."""

    period_end: str
    """Echo of the request ``end_date`` (ISO 8601 UTC)."""

    customer_id: str
    """The customer whose usage this report covers. Derived server-side
    from the auth context — NOT accepted as a query parameter. Today
    always ``SYSTEM_CONTEXT_ID`` until the M2.3 identity model lands."""

    total_calls: int = Field(..., ge=0)
    successful_calls: int = Field(..., ge=0)
    failed_calls: int = Field(..., ge=0)
    total_input_tokens: int = Field(..., ge=0)
    total_output_tokens: int = Field(..., ge=0)
    total_cost_usd: float = Field(..., ge=0.0)
    """Top-line cost across all providers/models. Reconciliation-grade
    (cent-precise) per the module-docstring rationale."""

    by_provider: list[ProviderBreakdown]
    """Per-provider rollup. Empty list if no rows in the period."""

    by_model: list[ModelBreakdown]
    """Per-(provider, model) rollup. Empty list if no rows in the period."""
