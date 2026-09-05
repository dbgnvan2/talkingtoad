"""Performance Bundle ingestion (2026-08-06 spec, Phase 1: PB1/PB2/PB6/PB8).

Accepts a source-agnostic ``PerformanceBundle`` (produced by the sibling
reporting app that owns GSC/GA4/GTM OAuth) and merges its per-URL GSC + GA4 +
index-state metrics into the existing Performance Ledger — the same ledger the
Page Priority queue and refresh flags already consume. TalkingToad never calls a
Google API here (architecture decision PB-A, Option A).

Phase 1 persists per-URL metrics. Query-level (`top_queries`) and site-level
(`gtm_audit`, `ga4_site_search_terms`) payloads are accepted but not yet
persisted — they feed the Phase 2/3 derived reports. The ingest response reports
them under ``deferred`` so nothing is silently dropped (P2).

Spec: docs/functional-specification.md §4.8 (Performance Bundle ingestion)
Tests: tests/test_performance_ingest.py, tests/test_performance_model.py
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.crawler.normaliser import is_same_domain
from api.models.performance import PerformanceRecord
from api.services.auth import require_auth
from api.services.error_responses import _err
from api.services.perf_join import (
    build_crawled_key_map,
    fold_performance_rows,
    match_key,
)
from api.services.performance_freshness import earlier, is_stale

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/performance", dependencies=[Depends(require_auth)])


def _get_store():
    from api.main import _store
    return _store


# ── PerformanceBundle v1 contract ───────────────────────────────────────────
class BundleQuery(BaseModel):
    query: str
    clicks: int = 0
    impressions: int = 0
    ctr: float = 0.0
    position: float = 0.0


class BundleGSC(BaseModel):
    clicks: int = 0
    impressions: int = 0
    ctr: float = 0.0
    position: float = 0.0
    top_queries: list[BundleQuery] = []
    index_state: str | None = None


class BundleGA4(BaseModel):
    sessions: int | None = None
    engaged_sessions: int | None = None
    engagement_rate: float | None = None
    conversions: int | None = None
    # e.g. {"organic": 180, "ai_referral": 9}
    source_breakdown: dict[str, int] | None = None


class BundlePage(BaseModel):
    url: str
    gsc: BundleGSC | None = None
    ga4: BundleGA4 | None = None


class BundleLinkingSite(BaseModel):
    domain: str
    linking_pages: int = 0
    target_pages: int = 0


class BundleLinkedPage(BaseModel):
    url: str
    incoming_links: int = 0
    linking_sites: int = 0


class BundleLinks(BaseModel):
    """D1 — Search Console's own Links report.

    First-party, free, and already inside the OAuth scope the producer holds. The
    alternative was renting a third-party backlink index: a recurring cost, a
    per-customer key, and therefore the parked multi-tenant work. Declined.
    Spec: docs/pending/2026-08-29_D1-off-site-authority.md
    """
    generated_at: str | None = None
    total_external_links: int | None = None
    referring_domains: int | None = None
    top_linking_sites: list[BundleLinkingSite] = []
    top_linked_pages: list[BundleLinkedPage] = []
    top_linking_text: list[dict] = []


class BundleSite(BaseModel):
    ga4_site_search_terms: list[dict] | None = None
    gtm_audit: dict | None = None
    links: BundleLinks | None = None


class PerformanceBundle(BaseModel):
    bundle_version: int
    site_url: str
    generated_at: str
    period: str  # "YYYY-MM"
    date_range: dict | None = None
    sources: list[str] = []
    pages: list[BundlePage] = []
    site: BundleSite | None = None


class IngestResult(BaseModel):
    ingested: int             # rows persisted (bundle URLs that matched a crawled page)
    sources: list[str]
    period: str
    unmatched_urls: list[str]  # bundle URLs with no crawled page — held out, not stored
    invalid_urls: list[str] = []  # bundle URLs that could not be parsed (skipped, not fatal)
    # P6.3 — storage key -> the bundle URLs that collapsed onto it. A fold is not
    # an error (it is the normal shape of a www/https duplicate) but it changes a
    # number the reader sees, so it is stated. Only keys with more than one URL.
    folded_urls: dict[str, list[str]] = {}
    stale: bool | None = None
    deferred: list[str] = []


def _ai_referral(ga4: BundleGA4 | None) -> int | None:
    if ga4 is None or not ga4.source_breakdown:
        return None
    return ga4.source_breakdown.get("ai_referral")


@router.post("/ingest", response_model=IngestResult)
async def ingest_bundle(bundle: PerformanceBundle, job_id: str):
    """Ingest a PerformanceBundle into the ledger for ``job_id`` (PB2)."""
    if bundle.bundle_version != 1:
        return _err("UNSUPPORTED_BUNDLE_VERSION",
                    f"bundle_version {bundle.bundle_version} is not supported (expected 1).", 400)

    # PB6 — reject a malformed site_url with a clear 400 first, so bare-host or
    # `sc-domain:` forms (netloc == "") don't masquerade as a domain mismatch.
    if not urlparse(bundle.site_url).netloc:
        return _err("INVALID_SITE_URL",
                    f"bundle.site_url '{bundle.site_url}' must be a full origin URL "
                    f"(scheme + host), e.g. 'https://example.org/'.", 400)

    store = _get_store()
    job = await store.get_job(job_id)
    if not job:
        return _err("JOB_NOT_FOUND", f"No crawl job with id {job_id}.", 404)

    # PB6 — domain guard. The bundle may only write rows for the job's own site.
    if not is_same_domain(bundle.site_url, job.target_url):
        return _err(
            "DOMAIN_MISMATCH",
            f"Bundle site_url '{bundle.site_url}' is a different domain from the crawl "
            f"job's target '{job.target_url}'. No performance rows were written.",
            403,
        )

    # ── ONE join key (P11 + P2) ─────────────────────────────────────────────
    # Storage, the matched/unmatched diff, AND the downstream consumer
    # (crawl.py page-priority lookup) must all resolve to the SAME string, or a
    # row persisted under one form is invisible to a reader using another. The
    # consumer looks rows up by the crawled page's exact url, so that is the
    # canonical STORAGE key; matching uses `_match_key` (www/scheme/slash-tolerant)
    # so a bundle URL still resolves to the right crawled page. Bundle URLs that
    # match no crawled page are held out (surfaced in unmatched_urls) rather than
    # persisted under an orphan key the consumer would never read.
    crawled_by_key = build_crawled_key_map(await store.get_pages(job_id))

    # Read-merge for correct dirty-state behaviour (P8): a bundle is authoritative
    # ONLY for the fields it carries. A GA4-only bundle must not overwrite GSC
    # metrics from an earlier bundle with zeros, and vice-versa. GA4/index are
    # additionally COALESCE-merged in the store layer so the legacy /api/gsc/ingest
    # (GSC-only) path can't wipe GA4 either.
    existing_cache: dict[str, PerformanceRecord | None] = {}

    async def _existing(key_url: str) -> PerformanceRecord | None:
        if key_url not in existing_cache:
            recs = await store.get_performance_records(url=key_url)
            existing_cache[key_url] = next((r for r in recs if r.period == bundle.period), None)
        return existing_cache[key_url]

    # P6.3 — two bundle pages resolving to one crawled page used to merge
    # last-writer-wins, so 100 clicks + 50 clicks stored as 50 on a page that
    # earned 150. They are collected here and FOLDED below (counts summed, rates
    # recomputed), which is also what /api/gsc/ingest does — one arithmetic, one
    # implementation.
    #
    # The read-merge (P8: a bundle is authoritative only for the fields it
    # carries) now happens AFTER the fold, not before. Before it, a GA4 value
    # carried forward onto two folding pages would be summed twice — the carry
    # is one fact about the page, not one per source URL.
    resolved: list[tuple[str, str, PerformanceRecord]] = []
    sections_seen: dict[str, set[str]] = {}
    unmatched: list[str] = []
    invalid: list[str] = []
    for p in bundle.pages:
        # Match up front (before any save) so a malformed URL is skipped honestly,
        # never crashing a request whose other rows are committed (P2).
        try:
            key = match_key(p.url)
        except ValueError:
            invalid.append(p.url)
            continue
        storage_key = crawled_by_key.get(key)
        if storage_key is None:
            unmatched.append(p.url)
            continue

        gsc = p.gsc
        ga4 = p.ga4
        seen = sections_seen.setdefault(storage_key, set())
        if gsc is not None:
            seen.add("gsc")
        if ga4 is not None:
            seen.add("ga4")

        resolved.append((storage_key, p.url, PerformanceRecord(
            url=storage_key,
            period=bundle.period,
            # Bundle values only — the carry-forward happens after the fold.
            gsc_clicks_mo=gsc.clicks if gsc else 0,
            gsc_impressions_mo=gsc.impressions if gsc else 0,
            gsc_ctr_mo=gsc.ctr if gsc else 0.0,
            gsc_avg_position_mo=gsc.position if gsc else 0.0,
            index_state=gsc.index_state if gsc else None,
            ga4_sessions_mo=ga4.sessions if ga4 else None,
            ga4_engaged_sessions_mo=ga4.engaged_sessions if ga4 else None,
            ga4_engagement_rate_mo=ga4.engagement_rate if ga4 else None,
            ga4_conversions_mo=ga4.conversions if ga4 else None,
            ga4_ai_referral_sessions_mo=_ai_referral(ga4) if ga4 else None,
            source_generated_at=bundle.generated_at,
            # P8.4 — only the query and its impressions: clicks/ctr/position per
            # query have no consumer, and a column of unread data is what P6.2
            # deleted. Ordered by impressions, which is what picks the target.
            gsc_top_queries=[
                {"query": q.query, "impressions": q.impressions}
                for q in sorted(gsc.top_queries, key=lambda q: -(q.impressions or 0))
            ] if (gsc and gsc.top_queries) else None,
        )))

    records, folded = fold_performance_rows(resolved)

    # Read-merge, once per folded row (P8): a bundle is authoritative ONLY for
    # the sections it carries, so a GA4-only bundle must not overwrite GSC
    # metrics from an earlier one with zeros, and vice versa.
    for rec in records:
        seen = sections_seen.get(rec.url, set())
        if "gsc" in seen and "ga4" in seen:
            continue
        base = await _existing(rec.url)
        if base is None:
            continue
        if "gsc" not in seen:
            rec.gsc_clicks_mo = base.gsc_clicks_mo
            rec.gsc_impressions_mo = base.gsc_impressions_mo
            rec.gsc_ctr_mo = base.gsc_ctr_mo
            rec.gsc_avg_position_mo = base.gsc_avg_position_mo
            rec.index_state = rec.index_state or base.index_state
        if "ga4" not in seen:
            rec.ga4_sessions_mo = base.ga4_sessions_mo
            rec.ga4_engaged_sessions_mo = base.ga4_engaged_sessions_mo
            rec.ga4_engagement_rate_mo = base.ga4_engagement_rate_mo
            rec.ga4_conversions_mo = base.ga4_conversions_mo
            rec.ga4_ai_referral_sessions_mo = base.ga4_ai_referral_sessions_mo
        # Freshness (PB8, honest): a row carrying a field forward from an older
        # base is only as fresh as that oldest source.
        if base.source_generated_at:
            rec.source_generated_at = earlier(bundle.generated_at, base.source_generated_at)

    await store.save_performance_records(records)

    # P8.4 — `deferred` names what was accepted but NOT stored. Per-URL
    # top_queries are stored now, so claiming otherwise would make the response
    # lie in the other direction: a producer reading it would keep re-sending
    # data it believes was lost. The SITE-level query report below genuinely is
    # still not stored.
    deferred: list[str] = []
    if bundle.site and (bundle.site.gtm_audit or bundle.site.ga4_site_search_terms):
        deferred.append("site")

    # D1 — the Links section is site-level, so it is stored on the job rather
    # than in the per-URL ledger. Absent section = no change, never an error:
    # every producer predating this contract must keep working.
    if bundle.site and bundle.site.links is not None:
        try:
            await store.update_job(job_id, offsite_links=bundle.site.links.model_dump())
        except Exception:  # noqa: BLE001
            logger.warning("offsite_links_persist_failed", extra={"job_id": job_id})

    return IngestResult(
        ingested=len(records),
        sources=bundle.sources,
        period=bundle.period,
        unmatched_urls=sorted(set(unmatched)),
        invalid_urls=sorted(set(invalid)),
        folded_urls=folded,
        stale=is_stale(bundle.generated_at),
        deferred=deferred,
    )
