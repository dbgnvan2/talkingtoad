"""P6.3 — two source URLs folding onto one crawled page must produce that page's
real totals, on both ingest paths, with the fold named in the response.

Measured before the fix. One crawled page (`https://e.com/about`), three GSC
rows: two URL variants that fold onto it (100 clicks and 50) and one URL no crawl
contains.

    POST /api/gsc/ingest -> {'ingested': 3, 'period': '2026-09'}
      ledger[/about]         = [(50, 500)]
      ledger[/never-crawled] = [(9, 90)]

    POST /api/performance/ingest -> {'ingested': 1,
                                     'unmatched_urls': ['https://e.com/never-crawled']}
      ledger[/about]         = [(50, 500)]

Two defects of different shapes:

* The GSC path stores an unmatched row under a key the page-priority consumer
  never reads, and counts it in `ingested`, so "the property is a different
  domain from the crawl" and "the join worked" look identical (P2). Its sibling
  holds those out and names them — and its comment states the exact reasoning
  the GSC path violates (P16).
* BOTH paths lose the folded row: `(50, 500)` where the page earned 150 and
  1500. 100 clicks and 1000 impressions, gone, with nothing in either response
  saying two URLs collapsed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from api.models.job import CrawlJob, CrawlSettings
from api.models.page import CrawledPage
from api.models.performance import PerformanceRecord

BASE = "https://e.com"
PAGE = f"{BASE}/about"


def _rec(url, **kw) -> PerformanceRecord:
    return PerformanceRecord(url=url, period="2026-09", **kw)


async def _job_with_one_page(store, job_id="j"):
    await store.create_job(CrawlJob(
        job_id=job_id, target_url=BASE, status="complete", pages_crawled=1,
        settings=CrawlSettings(), started_at=datetime.now(timezone.utc)))
    await store.save_pages([CrawledPage(
        job_id=job_id, url=PAGE, status_code=200, title="t",
        crawled_at=datetime.now(timezone.utc))])


# ---------------------------------------------------------------------------
# 4.3 – 4.6, 4.8, 4.9 — the fold arithmetic, at the unit
# ---------------------------------------------------------------------------


class TestTheFoldArithmetic:
    def test_folded_urls_sum_their_clicks_and_impressions(self):
        """4.3 — asserts the real total, not merely 'not 50'.

        First-wins is the plausible wrong fix: it changes the number, fixes
        nothing, and satisfies any assertion written as an inequality.
        """
        from api.services.perf_join import fold_performance_rows

        records, folded = fold_performance_rows([
            (PAGE, "http://www.e.com/about",
             _rec(PAGE, gsc_clicks_mo=100, gsc_impressions_mo=1000)),
            (PAGE, "https://e.com/about/",
             _rec(PAGE, gsc_clicks_mo=50, gsc_impressions_mo=500)),
        ])
        assert len(records) == 1
        assert records[0].gsc_clicks_mo == 150
        assert records[0].gsc_impressions_mo == 1500
        assert folded == {PAGE: ["http://www.e.com/about", "https://e.com/about/"]}

    def test_folded_ctr_is_recomputed_not_averaged(self):
        """4.4 — the inputs are chosen so the two arithmetics DIFFER.

        My own probe used 100/1000 and 50/500, which both have CTR 0.1 — an
        averaged CTR is also 0.1, so a fixture built from those rows cannot tell
        a mean from a recomputation. These deliberately differ: mean(0.10, 0.02)
        = 0.06, while 150 clicks over 3500 impressions is 0.0428…
        """
        from api.services.perf_join import fold_performance_rows

        records, _ = fold_performance_rows([
            (PAGE, "a", _rec(PAGE, gsc_clicks_mo=100, gsc_impressions_mo=1000,
                             gsc_ctr_mo=0.10)),
            (PAGE, "b", _rec(PAGE, gsc_clicks_mo=50, gsc_impressions_mo=2500,
                             gsc_ctr_mo=0.02)),
        ])
        assert records[0].gsc_ctr_mo == pytest.approx(150 / 3500)
        assert records[0].gsc_ctr_mo != pytest.approx(0.06), "the CTRs were averaged"

    def test_folded_position_is_impression_weighted(self):
        """4.5 — a plain mean says a page ranking 5th for its main query and 90th
        for one stray impression averages 47.5."""
        from api.services.perf_join import fold_performance_rows

        records, _ = fold_performance_rows([
            (PAGE, "a", _rec(PAGE, gsc_impressions_mo=999, gsc_avg_position_mo=5.0)),
            (PAGE, "b", _rec(PAGE, gsc_impressions_mo=1, gsc_avg_position_mo=90.0)),
        ])
        expected = (5.0 * 999 + 90.0 * 1) / 1000
        assert records[0].gsc_avg_position_mo == pytest.approx(expected)
        assert records[0].gsc_avg_position_mo < 6.0, "the positions were meaned"

    def test_a_rate_with_no_denominator_is_none_not_zero(self):
        """4.6 — for the field whose model can express it.

        `ga4_engagement_rate_mo` is `float | None`. `gsc_ctr_mo` is a bare
        `float` with default 0.0 and every consumer does arithmetic on it, so
        widening it is a contract change and is deferred (TODO P6.3b); the GSC
        half of this rule is pinned by the test below instead.
        """
        from api.services.perf_join import fold_performance_rows

        records, _ = fold_performance_rows([
            (PAGE, "a", _rec(PAGE, ga4_sessions_mo=0, ga4_engaged_sessions_mo=0)),
            (PAGE, "b", _rec(PAGE, ga4_sessions_mo=0, ga4_engaged_sessions_mo=0)),
        ])
        assert records[0].ga4_engagement_rate_mo is None, (
            "a rate with no sessions was written as 0.0, which reads as measured"
        )

    def test_gsc_ctr_with_no_impressions_stays_zero_deliberately(self):
        """4.6b — the deferral, pinned so it is a decision and not a slip."""
        from api.services.perf_join import fold_performance_rows

        records, _ = fold_performance_rows([
            (PAGE, "a", _rec(PAGE, gsc_clicks_mo=0, gsc_impressions_mo=0)),
            (PAGE, "b", _rec(PAGE, gsc_clicks_mo=0, gsc_impressions_mo=0)),
        ])
        assert records[0].gsc_ctr_mo == 0.0
        assert records[0].gsc_avg_position_mo == 0.0

    def test_a_single_url_is_not_reported_as_folded(self):
        """4.8 — a fold of one is not a fold. Reporting every row would make the
        disclosure noise, and noise is how the next one gets skipped."""
        from api.services.perf_join import fold_performance_rows

        records, folded = fold_performance_rows([
            (PAGE, "a", _rec(PAGE, gsc_clicks_mo=7)),
            (f"{BASE}/x", "b", _rec(f"{BASE}/x", gsc_clicks_mo=3)),
        ])
        assert len(records) == 2
        assert folded == {}

    def test_a_field_no_source_carried_stays_none_not_zero(self):
        """4.9b — found by mutation, not by review.

        4.9 mixes a real value with a None (1 and None), and `sum(v or 0)` gives
        1 there too — so the None-skipping in `_sum` could be replaced with
        zero-coercion and every test stayed green. The case that separates them
        is a field NO source carried: `_sum` keeps None ("unmeasured"),
        zero-coercion writes 0 ("measured, and it was zero"). Same P12 family as
        `info_excluded: 0` and `categories_unscored: []`.
        """
        from api.services.perf_join import fold_performance_rows

        records, _ = fold_performance_rows([
            (PAGE, "a", _rec(PAGE, gsc_clicks_mo=10, ga4_conversions_mo=None)),
            (PAGE, "b", _rec(PAGE, gsc_clicks_mo=5, ga4_conversions_mo=None)),
        ])
        assert records[0].ga4_conversions_mo is None, (
            "a field no source carried was written as 0 — which reads as "
            "'measured, and it was zero'"
        )
        assert records[0].gsc_clicks_mo == 15, "the sum still works"

    def test_ga4_counts_fold_without_disturbing_gsc(self):
        """4.9 — the fold reaches only the fields it should.

        The bundle path read-merges fields a source did not carry (P8). Summing
        GSC counts must not overwrite a GA4 value carried forward, and vice
        versa.
        """
        from api.services.perf_join import fold_performance_rows

        records, _ = fold_performance_rows([
            (PAGE, "a", _rec(PAGE, gsc_clicks_mo=10, ga4_sessions_mo=4,
                             ga4_conversions_mo=1)),
            (PAGE, "b", _rec(PAGE, gsc_clicks_mo=5, ga4_sessions_mo=6,
                             ga4_conversions_mo=None)),
        ])
        assert records[0].gsc_clicks_mo == 15
        assert records[0].ga4_sessions_mo == 10
        assert records[0].ga4_conversions_mo == 1, (
            "a None from one source erased a real value from the other"
        )


# ---------------------------------------------------------------------------
# 4.1 / 4.2 / 4.7 — the two endpoints
# ---------------------------------------------------------------------------


def _gsc_rows():
    return [
        {"url": "http://www.e.com/about", "clicks": 100, "impressions": 1000,
         "ctr": 0.10, "position": 5.0},
        {"url": "https://e.com/about/", "clicks": 50, "impressions": 500,
         "ctr": 0.10, "position": 6.0},
        {"url": f"{BASE}/never-crawled", "clicks": 9, "impressions": 90,
         "ctr": 0.10, "position": 9.0},
    ]


async def _gsc_ingest(api_client, auth_headers, store, rows=None):
    with patch("api.routers.gsc._require_gsc_configured"), \
         patch("api.routers.gsc._load_creds", return_value='{"token":"x"}'), \
         patch("google.oauth2.credentials.Credentials.from_authorized_user_info",
               return_value=object()), \
         patch("api.routers.gsc.fetch_page_performance",
               AsyncMock(return_value=rows if rows is not None else _gsc_rows())), \
         patch("api.routers.gsc._get_store", return_value=store):
        return await api_client.post(
            f"/api/gsc/ingest?site_url={BASE}&job_id=j", headers=auth_headers)


class TestTheGscPathAdoptsItsSiblingsContract:
    async def test_gsc_ingest_holds_out_urls_that_match_no_crawled_page(
        self, api_client, auth_headers, test_store
    ):
        """4.1 — an unmatched row was persisted under a key page-priority never
        reads. Its sibling's comment says why that is wrong; this pins it."""
        await _job_with_one_page(test_store)
        r = await _gsc_ingest(api_client, auth_headers, test_store)
        assert r.status_code == 200, r.text
        assert r.json()["unmatched_urls"] == [f"{BASE}/never-crawled"]
        assert await test_store.get_performance_records(url=f"{BASE}/never-crawled") == [], (
            "the unmatched row was still written to the ledger"
        )

    async def test_gsc_ingest_reports_matched_of_received(
        self, api_client, auth_headers, test_store
    ):
        """4.2 — `ingested: 3` could not be told apart from a perfect join."""
        await _job_with_one_page(test_store)
        body = (await _gsc_ingest(api_client, auth_headers, test_store)).json()
        assert body["received"] == 3
        assert body["matched"] == 2, "two source URLs resolved to the crawled page"
        assert body["ingested"] == 1, "one ledger row was written"

    async def test_gsc_ingest_stores_the_pages_real_totals(
        self, api_client, auth_headers, test_store
    ):
        """4.3b — the same arithmetic, through the endpoint."""
        await _job_with_one_page(test_store)
        await _gsc_ingest(api_client, auth_headers, test_store)
        recs = await test_store.get_performance_records(url=PAGE)
        assert [(r.gsc_clicks_mo, r.gsc_impressions_mo) for r in recs] == [(150, 1500)]

    async def test_both_ingest_paths_report_folded_urls(
        self, api_client, auth_headers, test_store
    ):
        """4.7 — the P16 guard, and the reason this is one change.

        The unmatched capability lived on one of two sibling paths for months.
        The way that happens again is fixing the fold only on the path named in
        the ticket.
        """
        await _job_with_one_page(test_store)
        gsc = (await _gsc_ingest(api_client, auth_headers, test_store)).json()
        assert gsc["folded_urls"] == {
            PAGE: ["http://www.e.com/about", "https://e.com/about/"]}

        await _job_with_one_page(test_store, job_id="j2")
        bundle = {
            "bundle_version": 1, "site_url": BASE, "period": "2026-09",
            "generated_at": datetime.now(timezone.utc).isoformat(), "sources": ["gsc"],
            "pages": [
                {"url": "http://www.e.com/about",
                 "gsc": {"clicks": 100, "impressions": 1000, "ctr": 0.1, "position": 5.0}},
                {"url": "https://e.com/about/",
                 "gsc": {"clicks": 50, "impressions": 500, "ctr": 0.1, "position": 6.0}},
            ],
        }
        with patch("api.routers.performance._get_store", return_value=test_store):
            r = await api_client.post("/api/performance/ingest?job_id=j2", json=bundle,
                                      headers=auth_headers)
        assert r.status_code == 200, r.text
        assert r.json()["folded_urls"] == {
            PAGE: ["http://www.e.com/about", "https://e.com/about/"]}
        recs = await test_store.get_performance_records(url=PAGE)
        assert [(x.gsc_clicks_mo, x.gsc_impressions_mo) for x in recs] == [(150, 1500)], (
            "the bundle path still last-wins the fold"
        )
