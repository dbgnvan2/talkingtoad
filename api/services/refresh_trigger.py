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


# ── Page Priority Work Queue ranking (Authority Matrix) ──────────────────
# Lower priority_rank = work on it sooner. Buckets order the queue; within a
# bucket, worse health sorts first. Pure function — caller supplies today +
# the per-page data so it stays deterministic and testable.

# Bucket weights (lower = higher priority)
_BUCKET_VULNERABLE_STAR = 0   # earns traffic but structurally weak — fix first
_BUCKET_DECAY = 1             # traffic decaying
_BUCKET_STALE = 2            # overdue for a refresh
_BUCKET_LOW_HEALTH = 3       # poor health, no GSC signal to prioritise it higher
_BUCKET_HIDDEN_GEM = 4       # healthy but not found — opportunity, not urgent
_BUCKET_OK = 5               # nothing flagged, healthy


def classify_page_bucket(health_score: int, flag: ReviewFlag) -> tuple[int, str]:
    """Map a page's health + ReviewFlag to a (bucket_weight, bucket_label).

    Precedence matches the Authority Matrix: a Vulnerable Star outranks decay,
    which outranks staleness. Pages with no flag are ranked by health alone
    (so the queue is useful even when GSC is not connected).
    """
    reasons = set(flag.reasons)
    if "Vulnerable Star" in reasons:
        return _BUCKET_VULNERABLE_STAR, "Vulnerable Star"
    if "Traffic Decay" in reasons:
        return _BUCKET_DECAY, "Traffic Decay"
    if "Staleness" in reasons:
        return _BUCKET_STALE, "Stale"
    if "Hidden Gem" in reasons:
        return _BUCKET_HIDDEN_GEM, "Hidden Gem"
    if health_score < VULNERABLE_STAR_HEALTH:
        return _BUCKET_LOW_HEALTH, "Low Health"
    return _BUCKET_OK, "OK"


def rank_pages(pages: list[dict]) -> list[dict]:
    """Sort page dicts into the work-queue order and stamp priority_rank/bucket.

    Each input dict must have ``health_score`` (int) and ``review_flag``
    (a :class:`ReviewFlag`). Returns the same dicts, sorted, with
    ``bucket`` (label) and ``priority_rank`` (1-based) added. Stable: ties
    broken by ascending health (worst first), then url for determinism.
    """
    for p in pages:
        weight, label = classify_page_bucket(p["health_score"], p["review_flag"])
        p["_bucket_weight"] = weight
        p["bucket"] = label
    ordered = sorted(
        pages,
        key=lambda p: (p["_bucket_weight"], p["health_score"], p.get("url", "")),
    )
    for i, p in enumerate(ordered, start=1):
        p["priority_rank"] = i
        p.pop("_bucket_weight", None)
    return ordered
