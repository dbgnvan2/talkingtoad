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
from api.services.perf_join import build_crawled_key_map, match_key
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


class BundleSite(BaseModel):
    ga4_site_search_terms: list[dict] | None = None
    gtm_audit: dict | None = None


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

    # Keyed by storage_key so two bundle pages that resolve to the same crawled
    # page merge into one row (last-writer-wins over the accumulated base) rather
    # than emitting a duplicate — `ingested` then counts distinct rows.
    pending: dict[str, PerformanceRecord] = {}
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

        # Base to merge onto: an already-accumulated row for this key (in-batch
        # duplicate) else the stored prior row (fetched only when a field must be
        # carried forward).
        base = pending.get(storage_key)
        if base is None and (p.gsc is None or p.ga4 is None):
            base = await _existing(storage_key)

        gsc = p.gsc
        ga4 = p.ga4
        # Freshness (PB8, honest): if any field is carried forward from an older
        # base row, the row is only as fresh as that oldest source.
        gen = bundle.generated_at
        if base is not None and base.source_generated_at:
            gen = earlier(bundle.generated_at, base.source_generated_at)

        pending[storage_key] = PerformanceRecord(
            url=storage_key,
            period=bundle.period,
            # GSC — from bundle if present, else carry base forward (else 0).
            gsc_clicks_mo=gsc.clicks if gsc else (base.gsc_clicks_mo if base else 0),
            gsc_impressions_mo=gsc.impressions if gsc else (base.gsc_impressions_mo if base else 0),
            gsc_ctr_mo=gsc.ctr if gsc else (base.gsc_ctr_mo if base else 0.0),
            gsc_avg_position_mo=gsc.position if gsc else (base.gsc_avg_position_mo if base else 0.0),
            index_state=(gsc.index_state if gsc else None) or (base.index_state if base else None),
            # GA4 — from bundle if present, else carry base forward (else None).
            ga4_sessions_mo=ga4.sessions if ga4 else (base.ga4_sessions_mo if base else None),
            ga4_engaged_sessions_mo=ga4.engaged_sessions if ga4 else (base.ga4_engaged_sessions_mo if base else None),
            ga4_engagement_rate_mo=ga4.engagement_rate if ga4 else (base.ga4_engagement_rate_mo if base else None),
            ga4_conversions_mo=ga4.conversions if ga4 else (base.ga4_conversions_mo if base else None),
            ga4_ai_referral_sessions_mo=_ai_referral(ga4) if ga4 else (base.ga4_ai_referral_sessions_mo if base else None),
            source_generated_at=gen,
        )

    records = list(pending.values())
    await store.save_performance_records(records)

    deferred: list[str] = []
    if any(p.gsc and p.gsc.top_queries for p in bundle.pages):
        deferred.append("top_queries")
    if bundle.site and (bundle.site.gtm_audit or bundle.site.ga4_site_search_terms):
        deferred.append("site")

    return IngestResult(
        ingested=len(records),
        sources=bundle.sources,
        period=bundle.period,
        unmatched_urls=sorted(set(unmatched)),
        invalid_urls=sorted(set(invalid)),
        stale=is_stale(bundle.generated_at),
        deferred=deferred,
    )
