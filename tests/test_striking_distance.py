"""Striking-distance pages: in the band, above the floor, with the query the seed knows.

Spec:  docs/pending/2026-09-02_phase4-user-value.md#U4.1 (PB3)
Tests: this file
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from api.models.job import CrawlJob
from api.models.page import CrawledPage
from api.models.performance import PerformanceRecord
from api.services.striking_distance import _cfg, build_striking_distance, rewrite_brief

BASE = "https://example.com"


async def _job(store, *, seed=None, job_id="j1"):
    job = CrawlJob(job_id=job_id, target_url=BASE, status="complete", pages_crawled=4,
                   started_at=datetime.now(timezone.utc), priority_seed=seed)
    await store.create_job(job)
    if seed is not None:
        await store.update_job(job_id, priority_seed=seed)
    await store.save_pages([CrawledPage(job_id=job_id, url=f"{BASE}/{p}", status_code=200,
                                        crawled_at=datetime.now(timezone.utc))
                            for p in ("in-band", "too-high", "too-few", "no-ledger")])
    await store.save_performance_records([
        PerformanceRecord(url=f"{BASE}/in-band", period="2026-08", gsc_clicks_mo=12, gsc_impressions_mo=400,
                          gsc_ctr_mo=0.03, gsc_avg_position_mo=8.4),
        PerformanceRecord(url=f"{BASE}/too-high", period="2026-08", gsc_clicks_mo=90, gsc_impressions_mo=900,
                          gsc_ctr_mo=0.1, gsc_avg_position_mo=2.1),
        PerformanceRecord(url=f"{BASE}/too-few", period="2026-08", gsc_clicks_mo=1, gsc_impressions_mo=12,
                          gsc_ctr_mo=0.08, gsc_avg_position_mo=9.0),
    ])


def test_config_values_are_the_documented_ones():
    """P29 — docs/thresholds.md records these."""
    cfg = _cfg()
    assert (cfg["position_min"], cfg["position_max"], cfg["impressions_min"]) == (5, 15, 50)


async def test_only_in_band_pages_above_the_floor_are_returned(test_store):
    await _job(test_store)
    out = await build_striking_distance(test_store, "j1")
    assert [p["url"] for p in out["pages"]] == [f"{BASE}/in-band"]
    row = out["pages"][0]
    assert row["position"] == 8.4 and row["impressions"] == 400 and row["clicks"] == 12
    assert row["target_query"] is None, "the ledger carries no query; none must be invented"
    assert f"{BASE}/in-band" in row["rewrite_brief"] and "8.4" in row["rewrite_brief"]
    assert "health_score" in row


async def test_target_query_comes_from_the_seed(test_store):
    seed = {"pages": [{"url": f"{BASE}/in-band", "top_queries": ["grief counselling vancouver", "bereavement support"]}]}
    await _job(test_store, seed=seed)
    out = await build_striking_distance(test_store, "j1")
    row = out["pages"][0]
    assert row["target_query"] == "grief counselling vancouver"
    assert row["other_queries"] == ["bereavement support"]
    assert '"grief counselling vancouver"' in row["rewrite_brief"]
    assert out["basis"]["queries_from_seed"] is True


async def test_basis_explains_an_empty_list(test_store):
    """P31: no ledger at all must read as 'no data', not 'nothing to do'."""
    job = CrawlJob(job_id="j2", target_url="https://other.org", status="complete", pages_crawled=1,
                   started_at=datetime.now(timezone.utc))
    await test_store.create_job(job)
    await test_store.save_pages([CrawledPage(job_id="j2", url="https://other.org/p", status_code=200,
                                             crawled_at=datetime.now(timezone.utc))])
    out = await build_striking_distance(test_store, "j2")
    assert out["pages"] == []
    assert out["basis"] == {"pages_crawled": 1, "pages_with_ledger": 0,
                            "band": {"position_min": 5.0, "position_max": 15.0},
                            "impressions_min": 50, "queries_from_seed": False}


async def test_endpoint_contract(api_client, auth_headers, test_store):
    await _job(test_store)
    r = await api_client.get("/api/crawl/j1/striking-distance", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    for key in ("pages", "basis"):
        assert key in body
    for key in ("url", "position", "impressions", "clicks", "target_query", "rewrite_brief", "health_score", "period"):
        assert key in body["pages"][0], f"StrikingDistancePanel reads {key}"
    r = await api_client.get("/api/crawl/nope/striking-distance", headers=auth_headers)
    assert r.status_code == 404


def test_rewrite_brief_reads_as_one_instruction():
    b = rewrite_brief("https://x.org/p", "food bank hours", 11.0, 120)
    assert b.startswith("Rewrite the title and meta description of https://x.org/p")
    assert '"food bank hours"' in b and "position 11.0" in b and "120 monthly impressions" in b


async def test_health_score_honours_suppressed_codes_like_page_priority(test_store):
    """CLN5 parity: the two panels sit side by side and must agree by page."""
    from api.models.issue import Issue
    await _job(test_store)
    await test_store.save_issues([Issue(job_id="j1", page_url=f"{BASE}/in-band", category="heading", severity="warning",
                                        issue_code="H1_MISSING", description="", recommendation="", impact=6)])
    before = (await build_striking_distance(test_store, "j1"))["pages"][0]["health_score"]
    await test_store.add_suppressed_code("H1_MISSING")
    after = (await build_striking_distance(test_store, "j1"))["pages"][0]["health_score"]
    assert before == 94 and after == 100
    from api.services.page_priority import build_page_priority
    pp = next(r for r in await build_page_priority(test_store, "j1") if r["url"].endswith("in-band"))
    assert pp["health_score"] == after
