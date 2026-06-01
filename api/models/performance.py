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
