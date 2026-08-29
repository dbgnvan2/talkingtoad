"""Page Priority work queue — one assembly, every surface.

Purpose: rank a job's crawled pages by the Authority Matrix and traffic (§6.9),
         from a single function that the API route, the PDF and the Excel export
         all call, so the ranking cannot exist for one surface and not another.
Spec:    docs/functional-specification.md#69-page-priority-work-queue
         docs/pending/2026-08-29_E3-performance-data-in-report.md#E3.1
Tests:   tests/test_page_priority.py, tests/test_performance_report.py

Why this module exists (E3.1, P25). The ranking, the Authority Matrix buckets
and the PW traffic ordering all shipped and were tested — at the orchestrator.
They were reachable only from `GET /api/crawl/{job_id}/page-priority` and the
GUI panel. The PDF the client actually receives ordered its "Top 10 Pages to Fix
First" by raw issue count, so on livingsystems.ca it listed ten podcast episode
pages while the ledger held a page with 15,216 impressions at 0.36% CTR. A test
at the orchestrator proves the orchestrator works; it says nothing about the
callers above it. Extracting the body here makes "which surfaces rank pages" a
single, greppable, testable fact.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from typing import Any

from api.services.job_store_base import compute_citability_grade, compute_page_health
from api.services.refresh_trigger import evaluate_refresh, rank_pages

# E3.5 (rule 8, P6) — performance data older than this is presented with its age
# stated, never as current.
PERF_STALE_DAYS = int(os.getenv("TT_PERF_STALE_DAYS", "60"))


async def build_page_priority(
    store: Any,
    job_id: str,
    *,
    today: date | None = None,
) -> list[dict]:
    """Return the job's crawled pages in work-queue order.

    Each row: ``{url, health_score, citability_grade, gsc, review_flag, bucket,
    priority_rank}``. ``gsc`` is ``None`` when the Performance Ledger holds no
    record for the page; ``review_flag`` is the live :class:`ReviewFlag` object
    (callers that serialise to JSON convert it — see ``serialise_review_flags``).

    Works with OR without ledger data: with none, every traffic key is ``(0, 0)``
    and the order collapses to the health-only ordering (§6.9).
    """
    pages = await store.get_pages(job_id)
    issues = await store.get_all_issues(job_id)

    # CLN5: drop user-suppressed codes before grading so per-page health AND the
    # citability column reconcile with site health (both previously used raw
    # rows). SQLite-only suppression; no-ops on Redis, matching Redis get_summary.
    _gs = getattr(store, "get_suppressed_codes", None)
    suppressed = set(await _gs()) if _gs else set()
    rows_by_url: dict[str, list[tuple[str, int, str]]] = {}
    for issue in issues:
        if issue.page_url and issue.issue_code not in suppressed:
            key = issue.page_url.rstrip("/")
            rows_by_url.setdefault(key, []).append(
                (issue.issue_code, issue.impact or 0, issue.category or "")
            )

    today = today or datetime.now(timezone.utc).date()
    rows: list[dict] = []
    for page in pages:
        key = page.url.rstrip("/")
        page_rows = rows_by_url.get(key, [])
        # Per-page health via the canonical capped+suppressed model (R5.0) — NOT
        # a raw ``100 − Σ impact`` sum (which ignored the category cap and cluster
        # suppression and diverged from compute_impact_health).
        health_score = compute_page_health(page_rows)
        # E5: per-page GEO/citability grade (rollup of ai_readiness issues).
        citability_grade = compute_citability_grade(page_rows)
        records = await store.get_performance_records(url=page.url)
        flag = evaluate_refresh(records, health_score, today=today)
        latest = sorted(records, key=lambda r: r.period)[-1] if records else None
        rows.append({
            "url": page.url,
            "health_score": health_score,
            "citability_grade": citability_grade,
            "gsc": None if latest is None else {
                "clicks": latest.gsc_clicks_mo,
                "impressions": latest.gsc_impressions_mo,
                "ctr": latest.gsc_ctr_mo,
                "position": latest.gsc_avg_position_mo,
                # PW: conversions drive within-bucket rank (tiebreak) + surfaced in
                # the panel. None stays None (unknown ≠ zero); rank coalesces.
                "conversions": latest.ga4_conversions_mo,
            },
            "review_flag": flag,
        })

    return rank_pages(rows)


def serialise_review_flags(ranked: list[dict]) -> list[dict]:
    """Convert each row's ``ReviewFlag`` to a JSON-safe dict, in place."""
    for r in ranked:
        f = r.get("review_flag")
        if f is not None and not isinstance(f, dict):
            r["review_flag"] = {"flagged": f.flagged, "reasons": f.reasons}
    return ranked


# ---------------------------------------------------------------------------
# Site-level performance rollup (E3.2)
# ---------------------------------------------------------------------------


def _ctr(clicks: int, impressions: int) -> float:
    return (clicks / impressions) if impressions else 0.0


def _parse_stamp(value: object) -> datetime | None:
    """Parse an ISO timestamp to an aware datetime, or None. Never raises."""
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _period_end(period: str) -> datetime | None:
    """Last instant of a ``YYYY-MM`` reporting period, or None if unparseable.

    Used as the freshness reference when the producer supplied no
    ``source_generated_at``: data for May is May-old no matter when it landed.
    """
    try:
        year, month = (int(p) for p in str(period).split("-")[:2])
        start = datetime(year, month, 1, tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None
    next_month = (
        datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        if month == 12
        else datetime(year, month + 1, 1, tzinfo=timezone.utc)
    )
    return next_month - timedelta(seconds=1) if next_month > start else start


async def build_performance_summary(
    store: Any,
    job_id: str,
    *,
    now: datetime | None = None,
    top_n: int = 15,
) -> dict | None:
    """Site-level GSC/GA4 rollup joined to per-page health, or ``None``.

    Returns ``None`` when the Performance Ledger holds nothing for this job's
    pages — the caller must then OMIT the section AND record the omission
    (E7.4), never render zeros that read as "no traffic".

    Purpose: the join between what the crawl sees and what the site earns. That
             join is the whole reason to put performance data in a crawl report;
             neither half is worth much on its own.
    Spec:    docs/pending/2026-08-29_E3-performance-data-in-report.md#E3.2
    Tests:   tests/test_performance_report.py
    """
    ranked = await build_page_priority(store, job_id)
    health_by_url = {r["url"]: r["health_score"] for r in ranked}

    rows: list[dict] = []
    periods: set[str] = set()
    newest_recorded: datetime | None = None

    for r in ranked:
        records = await store.get_performance_records(url=r["url"])
        if not records:
            continue
        latest = sorted(records, key=lambda x: x.period)[-1]
        periods.add(latest.period)
        # Freshness is a property of the DATA, not of when it was imported.
        # `recorded_at` is stamped `now` by the store on every write, so a
        # three-month-old bundle re-imported today would read as fresh (P6).
        # Prefer the producer's own `source_generated_at`; otherwise fall back to
        # the reporting period below.
        stamp = getattr(latest, "source_generated_at", None)
        if stamp:
            parsed = _parse_stamp(stamp)
            if parsed and (newest_recorded is None or parsed > newest_recorded):
                newest_recorded = parsed
        rows.append({
            "url": r["url"],
            "clicks": latest.gsc_clicks_mo or 0,
            "impressions": latest.gsc_impressions_mo or 0,
            "ctr": latest.gsc_ctr_mo or 0.0,
            "position": latest.gsc_avg_position_mo or 0.0,
            "sessions": getattr(latest, "ga4_sessions_mo", None),
            "conversions": getattr(latest, "ga4_conversions_mo", None),
            "ai_referral_sessions": getattr(latest, "ga4_ai_referral_sessions_mo", None),
            "health_score": health_by_url.get(r["url"]),
            "period": latest.period,
        })

    if not rows:
        return None

    total_clicks = sum(r["clicks"] for r in rows)
    total_impressions = sum(r["impressions"] for r in rows)
    site_ctr = _ctr(total_clicks, total_impressions)

    by_impressions = sorted(rows, key=lambda r: -r["impressions"])

    # High-impression / low-CTR: above the median impressions AND below the site
    # average CTR. Both halves matter — an "underperformer" with 12 impressions
    # is noise, and a low CTR on a page nobody sees is not a finding.
    impressions_sorted = sorted(r["impressions"] for r in rows)
    mid = len(impressions_sorted) // 2
    median_impressions = (
        impressions_sorted[mid]
        if len(impressions_sorted) % 2
        else (impressions_sorted[mid - 1] + impressions_sorted[mid]) / 2
    ) if impressions_sorted else 0
    low_ctr = [
        r for r in by_impressions
        if r["impressions"] >= median_impressions
        and r["impressions"] > 0
        and r["ctr"] < site_ctr
    ]

    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    if newest_recorded is None and periods:
        # Fall back to the end of the newest reporting month. A ledger whose most
        # recent period is 2026-05 describes May, however recently it was loaded.
        newest_recorded = _period_end(max(periods))
    age_days = (
        (reference - newest_recorded).days if newest_recorded is not None else None
    )

    return {
        "periods": sorted(periods),
        "pages_with_data": len(rows),
        "total_clicks": total_clicks,
        "total_impressions": total_impressions,
        "site_ctr": site_ctr,
        "total_sessions": sum(r["sessions"] or 0 for r in rows),
        "total_conversions": sum(r["conversions"] or 0 for r in rows),
        "total_ai_referral_sessions": sum(r["ai_referral_sessions"] or 0 for r in rows),
        "top_by_impressions": by_impressions[:top_n],
        "low_ctr_high_impression": low_ctr[:top_n],
        "data_age_days": age_days,
        "is_stale": bool(age_days is not None and age_days > PERF_STALE_DAYS),
        "source": "Google Search Console + GA4 (Performance Bundle)",
    }
