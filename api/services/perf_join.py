"""Shared URL join key for the performance ledger (CLN4).

`match_key` folds the differences that routinely separate a crawl seed from the
GSC/GA4 property it is joined against: beyond what `normalise_url` does (lowercase
host, drop fragment, strip tracking params, strip trailing slash) it ALSO folds a
leading `www.` and the http/https scheme — because a crawl seeded at
`https://example.org` is commonly joined against a `https://www.example.org/` or
`http://…` GSC property.

Used ONLY for MATCHING a performance-source URL (a GSC row or a bundle page) to a
crawled page. Ledger rows are always STORED under the crawled page's exact `url`,
which is the key the page-priority consumer (`crawl.py`) reads by — so storage
key, match, and lookup all agree.

Spec: docs/pending/2026-08-08_debt-cleanup-batch.md#CLN4
"""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse

from api.crawler.normaliser import _strip_www, normalise_url
from api.models.performance import PerformanceRecord


def match_key(url: str) -> str:
    """www/scheme/trailing-slash-tolerant join key. Raises ``ValueError`` (from
    `normalise_url`) on a scheme/host-less URL."""
    p = urlparse(normalise_url(url))
    return urlunparse(("", _strip_www(p.netloc), p.path, "", p.query, ""))


def build_crawled_key_map(pages) -> dict[str, str]:
    """Map ``match_key(crawled url) -> the crawled page's exact url`` for joining
    a performance source onto the key the ledger consumer reads by. URLs that
    cannot be normalised are skipped."""
    out: dict[str, str] = {}
    for pg in pages:
        try:
            out[match_key(pg.url)] = pg.url
        except ValueError:
            continue
    return out


# ── Folding two source URLs onto one crawled page (P6.3) ────────────────────
# `match_key` deliberately folds www/scheme/trailing-slash, so a GSC domain
# property routinely resolves several source URLs onto one crawled page. Both
# ingest paths then wrote them as separate records under the same storage key,
# and the ledger's ON CONFLICT overwrites the GSC columns — so the page's clicks
# became whichever row was written last. Measured: 100 clicks + 50 clicks stored
# as 50, on a page that earned 150.
#
# The arithmetic is per FIELD KIND, not one rule. Two URL variants of one page
# are two slices of that page's traffic, so counts add; a rate over the summed
# parts is not the mean of the rates; and an average position is only meaningful
# weighted by the impressions it averages over.

# Counts: additive across the folded rows.
_SUM_FIELDS = (
    "gsc_clicks_mo", "gsc_impressions_mo",
    "ga4_sessions_mo", "ga4_engaged_sessions_mo",
    "ga4_conversions_mo", "ga4_ai_referral_sessions_mo",
)


def _sum(values: list) -> int | None:
    """Sum, treating None as "this source said nothing" rather than as zero.

    All-None stays None: a field no source carried is unmeasured, and the
    bundle path's read-merge (P8) must still be able to carry a prior value
    forward for it.
    """
    present = [v for v in values if v is not None]
    return sum(present) if present else None


def fold_performance_rows(
    rows: list[tuple[str, str, PerformanceRecord]],
) -> tuple[list[PerformanceRecord], dict[str, list[str]]]:
    """Collapse ``(storage_key, source_url, record)`` triples to one record per key.

    Returns ``(records, folded_urls)``. ``folded_urls`` names only the keys that
    more than one source URL resolved to — a fold of one is not a fold, and
    reporting every row would make the disclosure noise.
    """
    by_key: dict[str, list[tuple[str, PerformanceRecord]]] = {}
    for storage_key, source_url, record in rows:
        by_key.setdefault(storage_key, []).append((source_url, record))

    out: list[PerformanceRecord] = []
    folded: dict[str, list[str]] = {}
    for key, entries in by_key.items():
        if len(entries) > 1:
            folded[key] = sorted(u for u, _r in entries)
        recs = [r for _u, r in entries]
        if len(recs) == 1:
            out.append(recs[0])
            continue

        merged = recs[0].model_copy(deep=True)
        for field in _SUM_FIELDS:
            total = _sum([getattr(r, field) for r in recs])
            if total is not None:
                setattr(merged, field, total)

        # Rates are recomputed from the summed parts, never averaged: averaging
        # weights a 10-impression row equally with a 10,000-impression one.
        impressions = merged.gsc_impressions_mo or 0
        if impressions:
            merged.gsc_ctr_mo = merged.gsc_clicks_mo / impressions
            # Impression-weighted, over the rows that HAVE impressions: an
            # unweighted mean says a page ranking 5th for its main query and
            # 90th for one stray impression averages 47.5.
            merged.gsc_avg_position_mo = sum(
                (r.gsc_avg_position_mo or 0) * (r.gsc_impressions_mo or 0) for r in recs
            ) / impressions
        # else: leave the model's 0.0. `gsc_ctr_mo`/`gsc_avg_position_mo` are
        # bare floats with every consumer doing arithmetic on them, so widening
        # them to express "unmeasured" is a contract change — TODO P6.3b.

        # P8.4 — queries fold by the same rule as every other count: two URL
        # variants of one page are two slices of that page's traffic, so a query
        # present in both ends with the SUM of its impressions, and the list is
        # re-sorted. Taking one slice's list would silently pick a different
        # target query depending on which URL the producer listed first.
        totals: dict[str, int] = {}
        for r in recs:
            for q in (r.gsc_top_queries or ()):
                name = (q or {}).get("query")
                if name:
                    totals[name] = totals.get(name, 0) + int(q.get("impressions") or 0)
        merged.gsc_top_queries = [
            {"query": name, "impressions": imps}
            for name, imps in sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
        ] or None

        sessions = merged.ga4_sessions_mo
        if sessions:
            merged.ga4_engagement_rate_mo = (merged.ga4_engaged_sessions_mo or 0) / sessions
        elif any(r.ga4_engagement_rate_mo is not None for r in recs):
            # Nullable in the model, so it can say "no denominator" honestly.
            merged.ga4_engagement_rate_mo = None
        out.append(merged)

    return out, folded
