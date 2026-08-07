"""PB2 (ingest) + PB6 (domain guard) API-contract & integration tests.

Contract table (must exist before any frontend consumes this endpoint):

| Endpoint | Frontend expects | Test |
|---|---|---|
| POST /api/performance/ingest | ingested, sources, period, unmatched_urls, stale, deferred | test_ingest_response_schema |

Spec: docs/functional-specification.md §4.8 (Performance Bundle ingestion)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app
from api.models.job import CrawlJob
from api.models.page import CrawledPage


@pytest.fixture
async def client_store(monkeypatch):
    """Async client wired to an in-memory store with auth disabled."""
    import api.main as main_mod
    from api.services.auth import require_auth
    from api.services.sqlite_store import SQLiteJobStore

    async with SQLiteJobStore(db_path=":memory:") as s:
        monkeypatch.setattr(main_mod, "_store", s)
        app.dependency_overrides[require_auth] = lambda: None
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c, s
        app.dependency_overrides.clear()


async def _seed_job(store, job_id="job1", target="https://example.org",
                    paths=("/", "/a", "/b")):
    await store.create_job(CrawlJob(job_id=job_id, target_url=target, status="complete"))
    pages = [
        CrawledPage(job_id=job_id, url=(target + p), status_code=200,
                    crawled_at=datetime.now(timezone.utc))
        for p in paths
    ]
    await store.save_pages(pages)
    return job_id


def _bundle(*, site="https://example.org", period="2026-07",
            generated_at="2026-08-01T00:00:00Z", pages=None, sources=None,
            site_obj=None, version=1):
    return {
        "bundle_version": version,
        "site_url": site,
        "generated_at": generated_at,
        "period": period,
        "sources": sources if sources is not None else ["gsc", "ga4"],
        "pages": pages or [],
        "site": site_obj,
    }


def _page(url, *, gsc=None, ga4=None):
    p = {"url": url}
    if gsc is not None:
        p["gsc"] = gsc
    if ga4 is not None:
        p["ga4"] = ga4
    return p


# ── PB2 contract + persistence ───────────────────────────────────────────────


async def test_ingest_response_schema(client_store):
    client, store = client_store
    await _seed_job(store)
    bundle = _bundle(pages=[
        _page("https://example.org/a",
              gsc={"clicks": 40, "impressions": 900, "ctr": 0.044, "position": 8.1,
                   "index_state": "indexed"},
              ga4={"sessions": 180, "engaged_sessions": 120, "engagement_rate": 0.67,
                   "conversions": 6, "source_breakdown": {"organic": 170, "ai_referral": 9}}),
    ])
    resp = await client.post("/api/performance/ingest", params={"job_id": "job1"}, json=bundle)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    for key in ("ingested", "sources", "period", "unmatched_urls", "stale", "deferred"):
        assert key in body, f"response missing {key}"
    assert body["ingested"] == 1
    assert body["period"] == "2026-07"
    assert body["sources"] == ["gsc", "ga4"]

    # side effect: row persisted with GA4 + index
    rec = (await store.get_performance_records(url="https://example.org/a"))[0]
    assert rec.gsc_clicks_mo == 40
    assert rec.ga4_sessions_mo == 180
    assert rec.ga4_ai_referral_sessions_mo == 9
    assert rec.index_state == "indexed"
    assert rec.source_generated_at == "2026-08-01T00:00:00Z"


async def test_ingest_ga4_only_page_keeps_gsc_null_not_zero(client_store):
    client, store = client_store
    await _seed_job(store)
    bundle = _bundle(sources=["ga4"], pages=[
        _page("https://example.org/a", ga4={"sessions": 50}),
    ])
    await client.post("/api/performance/ingest", params={"job_id": "job1"}, json=bundle)
    rec = (await store.get_performance_records(url="https://example.org/a"))[0]
    assert rec.ga4_sessions_mo == 50
    assert rec.ga4_conversions_mo is None  # absent GA4 field stays None


# ── PB6 domain guard ─────────────────────────────────────────────────────────


async def test_domain_mismatch_returns_403_and_writes_nothing(client_store):
    client, store = client_store
    await _seed_job(store, target="https://example.org")
    bundle = _bundle(site="https://evil.com", pages=[
        _page("https://evil.com/x", gsc={"clicks": 5}),
    ])
    resp = await client.post("/api/performance/ingest", params={"job_id": "job1"}, json=bundle)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "DOMAIN_MISMATCH"
    assert await store.get_performance_records() == []  # no rows written


async def test_job_not_found_returns_404(client_store):
    client, _ = client_store
    resp = await client.post("/api/performance/ingest", params={"job_id": "nope"},
                             json=_bundle(pages=[_page("https://example.org/a")]))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "JOB_NOT_FOUND"


async def test_unsupported_version_returns_400(client_store):
    client, store = client_store
    await _seed_job(store)
    resp = await client.post("/api/performance/ingest", params={"job_id": "job1"},
                             json=_bundle(version=2, pages=[_page("https://example.org/a")]))
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "UNSUPPORTED_BUNDLE_VERSION"


# ── unmatched-URL surfacing (P2/P3) + deferred reporting ─────────────────────


async def test_unmatched_urls_surfaced(client_store):
    client, store = client_store
    await _seed_job(store, paths=("/", "/a"))  # crawl knows / and /a
    bundle = _bundle(pages=[
        _page("https://example.org/a", gsc={"clicks": 3}),      # matched
        _page("https://example.org/ghost", gsc={"clicks": 99}),  # not crawled
    ])
    body = (await client.post("/api/performance/ingest",
                              params={"job_id": "job1"}, json=bundle)).json()
    assert body["unmatched_urls"] == ["https://example.org/ghost"]


async def test_deferred_reports_query_and_site_payloads(client_store):
    client, store = client_store
    await _seed_job(store)
    bundle = _bundle(
        pages=[_page("https://example.org/a",
                     gsc={"clicks": 3, "top_queries": [{"query": "counselling", "clicks": 3}]})],
        site_obj={"gtm_audit": {"consent_mode": True}},
    )
    body = (await client.post("/api/performance/ingest",
                              params={"job_id": "job1"}, json=bundle)).json()
    assert "top_queries" in body["deferred"]
    assert "site" in body["deferred"]


# ── PB2 dirty-state (P8) via the endpoint ────────────────────────────────────


async def test_reingest_updates_not_duplicates(client_store):
    client, store = client_store
    await _seed_job(store)
    b1 = _bundle(pages=[_page("https://example.org/a", gsc={"clicks": 10})])
    b2 = _bundle(pages=[_page("https://example.org/a", gsc={"clicks": 25})])
    await client.post("/api/performance/ingest", params={"job_id": "job1"}, json=b1)
    await client.post("/api/performance/ingest", params={"job_id": "job1"}, json=b2)
    recs = await store.get_performance_records(url="https://example.org/a")
    assert len(recs) == 1
    assert recs[0].gsc_clicks_mo == 25


async def test_ga4_only_reingest_preserves_prior_gsc_via_endpoint(client_store):
    """Read-merge: a GA4-only bundle must not zero the GSC metrics an earlier
    bundle wrote for the same (url, period)."""
    client, store = client_store
    await _seed_job(store)
    await client.post("/api/performance/ingest", params={"job_id": "job1"},
                      json=_bundle(pages=[_page("https://example.org/a",
                                                gsc={"clicks": 30, "impressions": 400})]))
    await client.post("/api/performance/ingest", params={"job_id": "job1"},
                      json=_bundle(sources=["ga4"],
                                   pages=[_page("https://example.org/a", ga4={"sessions": 70})]))
    rec = (await store.get_performance_records(url="https://example.org/a"))[0]
    assert rec.gsc_clicks_mo == 30, "GSC must survive a later GA4-only bundle"
    assert rec.gsc_impressions_mo == 400
    assert rec.ga4_sessions_mo == 70


async def test_trailing_slash_bundle_url_stored_under_crawled_key(client_store):
    """Regression (review #1/#5, P11): a bundle URL that differs from the crawled
    URL only by a trailing slash must persist under the CRAWLED page's key — the
    key the downstream consumer looks up by — not the raw bundle form."""
    client, store = client_store
    await _seed_job(store, paths=("/", "/a"))  # crawled "/a" has no trailing slash
    bundle = _bundle(pages=[
        _page("https://example.org/a/", gsc={"clicks": 7, "impressions": 200}),
    ])
    body = (await client.post("/api/performance/ingest",
                              params={"job_id": "job1"}, json=bundle)).json()
    assert body["ingested"] == 1
    assert body["unmatched_urls"] == []
    # The consumer keys on the crawled page URL ("/a", no slash) — the row must be there.
    recs = await store.get_performance_records(url="https://example.org/a")
    assert len(recs) == 1
    assert recs[0].gsc_clicks_mo == 7
    # And nothing was persisted under the raw trailing-slash bundle form.
    assert await store.get_performance_records(url="https://example.org/a/") == []


async def test_www_and_scheme_differences_still_join(client_store):
    """Regression (review F1, P11): a bundle whose property host is www./http-
    skewed from the crawl must still land on the crawled-page rows — the routine
    'crawl example.org, GSC property www.example.org' configuration."""
    client, store = client_store
    await _seed_job(store, target="https://example.org", paths=("/", "/a", "/b"))
    bundle = _bundle(site="https://www.example.org/", pages=[
        _page("https://www.example.org/a", gsc={"clicks": 4}),   # www skew
        _page("http://example.org/b", gsc={"clicks": 6}),        # scheme skew
    ])
    body = (await client.post("/api/performance/ingest",
                              params={"job_id": "job1"}, json=bundle)).json()
    assert body["ingested"] == 2
    assert body["unmatched_urls"] == []
    assert (await store.get_performance_records(url="https://example.org/a"))[0].gsc_clicks_mo == 4
    assert (await store.get_performance_records(url="https://example.org/b"))[0].gsc_clicks_mo == 6


async def test_duplicate_bundle_urls_merge_to_one_row(client_store):
    """Regression (review gap #3): two pages[] entries resolving to the same
    crawled page merge into one row; ingested counts distinct rows, and the
    GA4-only duplicate does not zero the first entry's GSC."""
    client, store = client_store
    await _seed_job(store, paths=("/", "/a"))
    bundle = _bundle(pages=[
        _page("https://example.org/a", gsc={"clicks": 12}),
        _page("https://example.org/a/", ga4={"sessions": 88}),  # same page, trailing slash
    ])
    body = (await client.post("/api/performance/ingest",
                              params={"job_id": "job1"}, json=bundle)).json()
    assert body["ingested"] == 1
    recs = await store.get_performance_records(url="https://example.org/a")
    assert len(recs) == 1
    assert recs[0].gsc_clicks_mo == 12
    assert recs[0].ga4_sessions_mo == 88


async def test_index_state_carried_forward_when_new_gsc_omits_it(client_store):
    """Regression (review gap #4): a later bundle whose gsc omits index_state
    keeps the prior index_state rather than nulling it."""
    client, store = client_store
    await _seed_job(store)
    await client.post("/api/performance/ingest", params={"job_id": "job1"},
                      json=_bundle(pages=[_page("https://example.org/a",
                                                gsc={"clicks": 1, "index_state": "indexed"})]))
    await client.post("/api/performance/ingest", params={"job_id": "job1"},
                      json=_bundle(pages=[_page("https://example.org/a", gsc={"clicks": 2})]))
    rec = (await store.get_performance_records(url="https://example.org/a"))[0]
    assert rec.gsc_clicks_mo == 2
    assert rec.index_state == "indexed"


async def test_malformed_bundle_url_is_skipped_not_fatal(client_store):
    """Regression (review #2, P2): a malformed URL in pages[] must not crash a
    request whose other rows commit — it lands in invalid_urls."""
    client, store = client_store
    await _seed_job(store, paths=("/", "/a"))
    bundle = _bundle(pages=[
        _page("not a url", gsc={"clicks": 1}),
        _page("https://example.org/a", gsc={"clicks": 9}),
    ])
    resp = await client.post("/api/performance/ingest", params={"job_id": "job1"}, json=bundle)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ingested"] == 1
    assert "not a url" in body["invalid_urls"]
    assert (await store.get_performance_records(url="https://example.org/a"))[0].gsc_clicks_mo == 9


async def test_invalid_site_url_returns_400(client_store):
    """Regression (review #4): a bare-host / scheme-less site_url is a clear 400,
    not a confusing 403 domain-mismatch."""
    client, store = client_store
    await _seed_job(store)
    resp = await client.post("/api/performance/ingest", params={"job_id": "job1"},
                             json=_bundle(site="example.org",
                                          pages=[_page("https://example.org/a")]))
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_SITE_URL"


async def test_carried_forward_row_reports_oldest_source_vintage(client_store):
    """Regression (review #3, PB8): a GA4-only bundle that carries prior GSC
    forward must stamp the row with the OLDER source's date, not optimistically
    the new bundle's."""
    client, store = client_store
    await _seed_job(store)
    await client.post("/api/performance/ingest", params={"job_id": "job1"},
                      json=_bundle(generated_at="2026-06-01T00:00:00Z",
                                   pages=[_page("https://example.org/a", gsc={"clicks": 30})]))
    await client.post("/api/performance/ingest", params={"job_id": "job1"},
                      json=_bundle(generated_at="2026-08-01T00:00:00Z", sources=["ga4"],
                                   pages=[_page("https://example.org/a", ga4={"sessions": 5})]))
    rec = (await store.get_performance_records(url="https://example.org/a"))[0]
    assert rec.gsc_clicks_mo == 30          # GSC preserved
    assert rec.ga4_sessions_mo == 5         # GA4 applied
    assert rec.source_generated_at == "2026-06-01T00:00:00Z"  # oldest vintage wins


async def test_mixed_tz_format_across_bundles_does_not_crash(client_store):
    """Regression (consolidated sweep): bundle #1 with a tz-naive generated_at then
    bundle #2 with a `...Z` generated_at (carried-forward page) must merge, not 500."""
    client, store = client_store
    await _seed_job(store)
    r1 = await client.post("/api/performance/ingest", params={"job_id": "job1"},
                           json=_bundle(generated_at="2026-07-01T00:00:00",  # naive
                                        pages=[_page("https://example.org/a", gsc={"clicks": 3})]))
    assert r1.status_code == 200
    r2 = await client.post("/api/performance/ingest", params={"job_id": "job1"},
                           json=_bundle(generated_at="2026-08-15T00:00:00Z", sources=["ga4"],  # aware
                                        pages=[_page("https://example.org/a", ga4={"sessions": 4})]))
    assert r2.status_code == 200, r2.text
    rec = (await store.get_performance_records(url="https://example.org/a"))[0]
    assert rec.gsc_clicks_mo == 3
    assert rec.ga4_sessions_mo == 4
    assert rec.source_generated_at == "2026-07-01T00:00:00"  # oldest vintage, no crash


async def test_stale_bundle_flagged(client_store):
    client, store = client_store
    await _seed_job(store)
    body = (await client.post(
        "/api/performance/ingest", params={"job_id": "job1"},
        json=_bundle(generated_at="2026-01-01T00:00:00Z",
                     pages=[_page("https://example.org/a", gsc={"clicks": 1})]),
    )).json()
    assert body["stale"] is True
