"""P8.4 — a query the producer supplied must reach the page that needs one.

Striking distance read target queries from ONE place: `job.priority_seed`, the
CSV uploaded when the scan started. Meanwhile `/api/performance/ingest` accepted
`top_queries` on every bundle page and dropped them. Measured end to end:

    ingest -> 200   deferred=['top_queries']
    striking-distance rows=1
      target_query=None   other_queries=[]
      rewrite_brief="Rewrite the title and meta description of … to target its
                     main search query…"

The page is found. The query was supplied by the producer, acknowledged as
received, and discarded — and the brief then tells a nonprofit to target "its
main search query" without being able to name it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from api.models.job import CrawlJob, CrawlSettings
from api.models.page import CrawledPage

BASE = "https://e.com"
PAGE = f"{BASE}/about"
Q1, Q2 = "grief counselling vancouver", "bereavement support bc"


def _q(query, impressions, **kw):
    return {"query": query, "clicks": kw.get("clicks", 1),
            "impressions": impressions, "ctr": 0.01, "position": 8.0}


def _bundle(pages, period="2026-09"):
    return {"bundle_version": 1, "site_url": BASE, "period": period,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sources": ["gsc"], "pages": pages}


def _page(url, *, impressions=900, position=8.4, queries=None):
    gsc = {"clicks": 5, "impressions": impressions, "ctr": 0.005,
           "position": position}
    if queries is not None:
        gsc["top_queries"] = queries
    return {"url": url, "gsc": gsc}


async def _job(store, job_id="j", *, priority_seed=None):
    await store.create_job(CrawlJob(
        job_id=job_id, target_url=BASE, status="complete", pages_crawled=1,
        settings=CrawlSettings(), started_at=datetime.now(timezone.utc)))
    await store.save_pages([CrawledPage(
        job_id=job_id, url=PAGE, status_code=200, title="t",
        crawled_at=datetime.now(timezone.utc))])
    if priority_seed is not None:
        await store.update_job(job_id, priority_seed=priority_seed)


async def _ingest(api_client, headers, store, bundle, job_id="j"):
    with patch("api.routers.performance._get_store", return_value=store):
        return await api_client.post(f"/api/performance/ingest?job_id={job_id}",
                                     json=bundle, headers=headers)


async def _sd_row(api_client, headers, job_id="j"):
    r = await api_client.get(f"/api/crawl/{job_id}/striking-distance", headers=headers)
    assert r.status_code == 200, r.text
    rows = r.json()["pages"]
    assert rows, f"the page did not land in the striking-distance band: {r.json()['basis']}"
    return rows[0]


class TestAnIngestedQueryReachesThePage:
    async def test_an_ingested_query_reaches_striking_distance(
        self, api_client, auth_headers, test_store
    ):
        """3.1 — the measured `target_query=None`."""
        await _job(test_store)
        await _ingest(api_client, auth_headers, test_store,
                      _bundle([_page(PAGE, queries=[_q(Q1, 500), _q(Q2, 200)])]))
        row = await _sd_row(api_client, auth_headers)
        assert row["target_query"] == Q1, row
        assert row["other_queries"] == [Q2], row
        assert Q1 in row["rewrite_brief"], (
            "the brief still says 'its main search query' without naming it"
        )

    async def test_a_page_with_no_queries_anywhere_reports_none_not_empty_string(
        self, api_client, auth_headers, test_store
    ):
        """3.7 — `""` is a query; `None` is "we do not have one", and the brief
        reads differently for each. The P12 shape this repo keeps hitting."""
        await _job(test_store)
        await _ingest(api_client, auth_headers, test_store, _bundle([_page(PAGE)]))
        row = await _sd_row(api_client, auth_headers)
        assert row["target_query"] is None, row
        assert row["other_queries"] == []


class TestThePrecedenceIsChosen:
    async def test_the_priority_seed_still_supplies_queries_when_the_ledger_has_none(
        self, api_client, auth_headers, test_store
    ):
        """3.5 — what the obvious implementation breaks.

        Swapping the seed lookup for a ledger lookup satisfies 3.1 and silently
        removes target queries from every job that gets them the way that works
        today. This is the only path that works before this change.
        """
        await _job(test_store, priority_seed={"pages": [
            {"url": PAGE, "top_queries": ["seeded query", "second seeded"]}]})
        await _ingest(api_client, auth_headers, test_store, _bundle([_page(PAGE)]))
        row = await _sd_row(api_client, auth_headers)
        assert row["target_query"] == "seeded query", row

    async def test_the_ledger_wins_over_a_stale_seed(
        self, api_client, auth_headers, test_store
    ):
        """3.6 — precedence chosen, not inherited from lookup order.

        With both present they will disagree eventually. The ledger is
        per-period and moves with the data; the seed is frozen at scan start.
        Leaving this to whichever lookup runs first is the P8.2 mistake in a
        different file.
        """
        await _job(test_store, priority_seed={"pages": [
            {"url": PAGE, "top_queries": ["stale seeded query"]}]})
        await _ingest(api_client, auth_headers, test_store,
                      _bundle([_page(PAGE, queries=[_q(Q1, 500)])]))
        row = await _sd_row(api_client, auth_headers)
        assert row["target_query"] == Q1, (
            f"the frozen seed beat the current ledger: {row['target_query']!r}"
        )


class TestTheContractStopsLying:
    async def test_top_queries_is_no_longer_reported_as_deferred(
        self, api_client, auth_headers, test_store
    ):
        """3.2 — `deferred` tells a producer what was accepted but NOT stored.

        Once stored, saying otherwise makes the response lie in the other
        direction: a producer reading it would keep re-sending data it believes
        was lost.
        """
        await _job(test_store)
        r = await _ingest(api_client, auth_headers, test_store,
                          _bundle([_page(PAGE, queries=[_q(Q1, 500)])]))
        assert "top_queries" not in r.json()["deferred"], r.json()

    async def test_the_site_level_query_report_is_still_deferred(
        self, api_client, auth_headers, test_store
    ):
        """3.3 — the other direction. `ga4_site_search_terms` genuinely is not
        stored, and claiming it now is would be the same lie reversed."""
        await _job(test_store)
        bundle = _bundle([_page(PAGE, queries=[_q(Q1, 500)])])
        bundle["site"] = {"ga4_site_search_terms": [{"term": "counselling", "sessions": 4}]}
        r = await _ingest(api_client, auth_headers, test_store, bundle)
        assert "site" in r.json()["deferred"], r.json()


class TestFoldingFollowsTheSameRule:
    async def test_folded_urls_sum_impressions_per_query(
        self, api_client, auth_headers, test_store
    ):
        """3.4 — P6.3's arithmetic, not a second convention.

        Two URL variants folding onto one page are two slices of that page's
        traffic, so a query present in both ends with the SUM. The inputs are
        chosen so summing and taking-one-slice give a different ORDER, not just
        a different number — otherwise the assertion cannot tell them apart.
        """
        await _job(test_store)
        await _ingest(api_client, auth_headers, test_store, _bundle([
            # slice A: Q2 leads
            _page("http://www.e.com/about", impressions=500,
                  queries=[_q(Q2, 300), _q(Q1, 150)]),
            # slice B: Q1 leads, and Q1's total (150+400) beats Q2's (300+50)
            _page("https://e.com/about/", impressions=400,
                  queries=[_q(Q1, 400), _q(Q2, 50)]),
        ]))
        row = await _sd_row(api_client, auth_headers)
        assert row["target_query"] == Q1, (
            f"queries were taken from one slice instead of summed: {row}"
        )
        assert row["other_queries"] == [Q2]
