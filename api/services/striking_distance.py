"""Striking-distance pages — the highest-leverage inputs to the Content Rewriter.

Purpose: a page already ranking 5–15 for a query with real impressions is one
         rewrite away from page one; the Page Priority queue ranks by traffic
         and health and never singles these out. PB3 of the Performance Bundle
         plan (docs/pending/2026-08-06_performance-bundle-ingestion.md).
Spec:    docs/pending/2026-09-02_phase4-user-value.md#U4.1
Tests:   tests/test_striking_distance.py

Read-only; the user triggers the existing rewriter. The band and floor are
config (api/config/striking_distance.json), recorded in docs/thresholds.md.
"""

from __future__ import annotations

from typing import Any

from api.config import load_config
from api.services.job_store_base import compute_page_health
from api.services.page_priority import _ledger_by_key, ledger_key

_CFG_KEYS = ("position_min", "position_max", "impressions_min")


def _cfg() -> dict:
    return load_config("striking_distance", required_keys=_CFG_KEYS)


def rewrite_brief(url: str, query: str | None, position: float, impressions: int) -> str:
    """One sentence the operator can paste into the Content Rewriter."""
    target = f"the search query \"{query}\"" if query else "its main search query"
    return (f"Rewrite the title and meta description of {url} to target {target}. "
            f"It currently ranks at position {position:.1f} with {impressions} monthly impressions; "
            f"the goal is to move it onto page one.")


async def build_striking_distance(store: Any, job_id: str) -> dict:
    """Pages in the band, sorted by impressions, with the basis they were chosen over."""
    cfg = _cfg()
    lo, hi, floor = float(cfg["position_min"]), float(cfg["position_max"]), int(cfg["impressions_min"])
    job = await store.get_job(job_id)
    pages = await store.get_pages(job_id)
    issues = await store.get_all_issues(job_id)
    ledger = await _ledger_by_key(store, pages)
    info_detail = job.settings.info_detail if job is not None else "all"

    # Target queries: the LEDGER first (per-period, moves with the data), then
    # the scan-time priority seed as a fallback (frozen at start). Both are kept
    # because the seed is the only path that worked before P8.4 and jobs still
    # use it; the precedence is chosen rather than left to lookup order.
    seed_queries: dict[str, list[str]] = {}
    seed = (job.priority_seed or {}) if job is not None else {}
    for row in seed.get("pages", []) or []:
        if row.get("url") and row.get("top_queries"):
            seed_queries[ledger_key(row["url"])] = list(row["top_queries"])

    _gs = getattr(store, "get_suppressed_codes", None)
    suppressed = set(await _gs()) if _gs else set()
    rows_by_url: dict[str, list[tuple[str, int, str]]] = {}
    for issue in issues:
        if issue.page_url and issue.issue_code not in suppressed:  # CLN5 parity with /page-priority
            rows_by_url.setdefault(issue.page_url.rstrip("/"), []).append(
                (issue.issue_code, issue.impact or 0, issue.category or ""))

    out: list[dict] = []
    with_ledger = 0
    for page in pages:
        records = ledger.get(ledger_key(page.url), [])
        if not records:
            continue
        with_ledger += 1
        latest = sorted(records, key=lambda r: r.period)[-1]
        pos, imps = float(latest.gsc_avg_position_mo or 0), int(latest.gsc_impressions_mo or 0)
        if not (lo <= pos <= hi) or imps < floor:
            continue
        ledger_queries = [
            q["query"] for q in (latest.gsc_top_queries or []) if q.get("query")
        ]
        queries = ledger_queries or seed_queries.get(ledger_key(page.url), [])
        query = queries[0] if queries else None
        out.append({
            "url": page.url,
            "position": round(pos, 1),
            "impressions": imps,
            "clicks": int(latest.gsc_clicks_mo or 0),
            "ctr": latest.gsc_ctr_mo,
            "period": latest.period,
            "health_score": compute_page_health(rows_by_url.get(page.url.rstrip("/"), []), info_detail=info_detail),
            "target_query": query,
            "other_queries": queries[1:4],
            "rewrite_brief": rewrite_brief(page.url, query, pos, imps),
        })
    out.sort(key=lambda r: (-r["impressions"], r["position"]))
    return {
        "job_id": job_id,
        "pages": out,
        # P31: an empty list must say WHY it is empty.
        "basis": {
            "pages_crawled": len(pages),
            "pages_with_ledger": with_ledger,
            "band": {"position_min": lo, "position_max": hi},
            "impressions_min": floor,
            "queries_from_seed": bool(seed_queries),
        },
    }
