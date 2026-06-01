"""
Automated Refresh Trigger (M6.3 — Performance-Health Feedback Loop).

Pure deterministic algorithm that flags pages needing review based on
staleness, traffic decay, and performance-health matrix triggers.
Operates over PerformanceRecord history already in the ledger (M6.2).
No I/O, no datetime.now(), no external calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from statistics import mean

from api.models.performance import PerformanceRecord

# Threshold constants (module-level)
STALENESS_DAYS = 180
TRAFFIC_DECAY_RATIO = 0.20
VULNERABLE_STAR_IMPRESSIONS = 100
VULNERABLE_STAR_HEALTH = 60
HIDDEN_GEM_HEALTH = 80
HIDDEN_GEM_IMPRESSIONS = 10


@dataclass(frozen=True)
class ReviewFlag:
    flagged: bool
    reasons: list[str] = field(default_factory=list)


def _parse_iso_date(value: str | None) -> date | None:
    """Parse an ISO-format date string to a date object, or None."""
    if value is None:
        return None
    # Handle both "YYYY-MM-DD" and "YYYY-MM-DDTHH:MM:SS..." formats
    return date.fromisoformat(value[:10])


def evaluate_refresh(
    records: list[PerformanceRecord],
    health_score: int,
    *,
    today: date,
) -> ReviewFlag:
    """
    Pure deterministic algorithm to flag pages needing review.
    No I/O, no datetime.now(), no external calls.
    """
    if not records:
        return ReviewFlag(flagged=False, reasons=[])

    # Sort by period ascending for deterministic processing
    sorted_records = sorted(records, key=lambda r: r.period)
    most_recent = sorted_records[-1]
    reasons: list[str] = []

    # --- STALENESS ---
    staleness_date = (
        _parse_iso_date(most_recent.last_technical_improvement_at)
        or _parse_iso_date(most_recent.created_at)
    )
    if staleness_date is not None:
        days_since_improvement = (today - staleness_date).days
        if days_since_improvement > STALENESS_DAYS:
            reasons.append("Staleness")

    # --- TRAFFIC DECAY ---
    if len(sorted_records) >= 2:
        recent_3 = sorted_records[-3:] if len(sorted_records) >= 3 else sorted_records
        clicks_3mo_avg = mean(r.gsc_clicks_mo for r in recent_3)
        clicks_1mo = most_recent.gsc_clicks_mo

        if clicks_3mo_avg > 0:
            decay_ratio = (clicks_3mo_avg - clicks_1mo) / clicks_3mo_avg
            if decay_ratio > TRAFFIC_DECAY_RATIO:
                reasons.append("Traffic Decay")

    # --- VULNERABLE STAR ---
    if (
        most_recent.gsc_impressions_mo >= VULNERABLE_STAR_IMPRESSIONS
        and health_score < VULNERABLE_STAR_HEALTH
    ):
        reasons.append("Vulnerable Star")

    # --- HIDDEN GEM ---
    if (
        health_score >= HIDDEN_GEM_HEALTH
        and most_recent.gsc_clicks_mo == 0
        and most_recent.gsc_impressions_mo < HIDDEN_GEM_IMPRESSIONS
    ):
        reasons.append("Hidden Gem")

    return ReviewFlag(flagged=bool(reasons), reasons=reasons)
