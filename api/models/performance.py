"""
PerformanceRecord Pydantic model (M6.2 — Performance Ledger).

One row per URL per calendar month, tracking lifecycle dates and
monthly GSC-style performance metrics.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PerformanceRecord(BaseModel):
    """A single row in the performance ledger — one URL for one calendar month."""
    url: str
    period: str  # "YYYY-MM"
    created_at: str | None = None  # page first-seen (ISO)
    last_technical_improvement_at: str | None = None  # last WP fix / clean re-scan (ISO)
    gsc_clicks_mo: int = 0
    gsc_impressions_mo: int = 0
    gsc_ctr_mo: float = 0.0
    gsc_avg_position_mo: float = 0.0
    recorded_at: str | None = None  # when this row was written (ISO)

    # ── Performance Bundle ingestion (2026-08-06 spec, PB1) ─────────────────
    # GA4 + index-state fields, populated from an ingested PerformanceBundle
    # (produced by the sibling reporting app). All default None — "no GA4
    # source" must stay distinguishable from "zero sessions" (P2), so callers
    # must never coerce None → 0. index_state controlled vocab: indexed |
    # crawled_not_indexed | discovered_not_indexed | excluded_noindex |
    # not_in_gsc | unknown.
    ga4_sessions_mo: int | None = None
    ga4_engaged_sessions_mo: int | None = None
    ga4_engagement_rate_mo: float | None = None
    ga4_conversions_mo: int | None = None
    ga4_ai_referral_sessions_mo: int | None = None
    index_state: str | None = None
    source_generated_at: str | None = None  # the bundle's generated_at (freshness, PB8)
