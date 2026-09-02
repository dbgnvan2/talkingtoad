"""Re-check all pages in place — every stored page through the one hardened rescan path.

Spec:  docs/pending/2026-09-02_phase4-user-value.md#U4.3
Tests: this file
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from api.models.job import CrawlJob, CrawlSettings
from api.models.page import CrawledPage
from api.routers import crawl as crawl_router

BASE = "https://example.com"


@pytest.fixture(autouse=True)
def _clear_progress():
    crawl_router._recheck_progress.clear()
    yield
    crawl_router._recheck_progress.clear()


async def _job(store, status="complete", n_pages=3, delay_ms=200, job_id="j1"):  # delay_ms >= 200 (CrawlSettings floor)
    job = CrawlJob(job_id=job_id, target_url=BASE, status=status, pages_crawled=n_pages,
                   settings=CrawlSettings(crawl_delay_ms=delay_ms),
                   started_at=datetime.now(timezone.utc))
    await store.create_job(job)
    await store.save_pages([CrawledPage(job_id=job_id, url=f"{BASE}/p{i}", status_code=200,
                                        crawled_at=datetime.now(timezone.utc)) for i in range(n_pages)])
    return job


class TestStartAndStatus:
    async def test_unknown_job_is_404(self, api_client, auth_headers):
        assert (await api_client.post("/api/crawl/nope/recheck-all", headers=auth_headers)).status_code == 404
        assert (await api_client.get("/api/crawl/nope/recheck-all/status", headers=auth_headers)).status_code == 404

    async def test_running_job_is_409(self, api_client, auth_headers, test_store):
        await _job(test_store, status="running")
        r = await api_client.post("/api/crawl/j1/recheck-all", headers=auth_headers)
        assert r.status_code == 409 and r.json()["error"]["code"] == "CRAWL_IN_PROGRESS"

    async def test_status_before_any_run_is_not_running(self, api_client, auth_headers, test_store):
        await _job(test_store)
        body = (await api_client.get("/api/crawl/j1/recheck-all/status", headers=auth_headers)).json()
        assert body == {"job_id": "j1", "running": False, "done": 0, "total": 0, "resolved": 0,
                        "added": 0, "unreadable": 0, "started_at": None, "finished_at": None}

    async def test_start_returns_202_and_the_loop_visits_every_page_with_the_delay(
            self, api_client, auth_headers, test_store):
        await _job(test_store, n_pages=3, delay_ms=250)
        visited: list[str] = []
        sleeps: list[float] = []

        async def fake_rescan(job_id, url, store):
            visited.append(url)
            return {"url": url, "status_code": 200, "resolved": 1, "added": 0}

        async def fake_sleep(s):
            sleeps.append(s)

        with patch.object(crawl_router, "rescan_url", side_effect=fake_rescan), \
                patch.object(crawl_router.asyncio, "sleep", side_effect=fake_sleep):
            r = await api_client.post("/api/crawl/j1/recheck-all", headers=auth_headers)
            assert r.status_code == 202, r.text
            assert r.json() == {"job_id": "j1", "total": 3, "status": "started"}
        # Background tasks run before the test client returns the response.
        assert visited == [f"{BASE}/p0", f"{BASE}/p1", f"{BASE}/p2"]
        assert sleeps == [0.25, 0.25], "the job's politeness delay applies BETWEEN pages, not after the last"
        body = (await api_client.get("/api/crawl/j1/recheck-all/status", headers=auth_headers)).json()
        assert body["running"] is False and body["done"] == 3 and body["total"] == 3
        assert body["resolved"] == 3 and body["unreadable"] == 0 and body["finished_at"]

    async def test_unreadable_pages_are_counted_not_resolved(self, api_client, auth_headers, test_store):
        await _job(test_store, n_pages=2)

        async def fake_rescan(job_id, url, store):
            if url.endswith("p1"):
                return {"url": url, "status_code": 403, "page_unreadable": True, "resolved": 0, "added": 0}
            return {"url": url, "status_code": 200, "resolved": 2, "added": 1}

        with patch.object(crawl_router, "rescan_url", side_effect=fake_rescan), \
                patch.object(crawl_router.asyncio, "sleep", new=AsyncMock()):
            await api_client.post("/api/crawl/j1/recheck-all", headers=auth_headers)
        body = (await api_client.get("/api/crawl/j1/recheck-all/status", headers=auth_headers)).json()
        assert (body["resolved"], body["added"], body["unreadable"], body["done"]) == (2, 1, 1, 2)

    async def test_a_second_start_while_running_is_409(self, api_client, auth_headers, test_store):
        await _job(test_store, n_pages=1)
        crawl_router._recheck_progress["j1"] = {"running": True, "done": 0, "total": 5, "resolved": 0,
                                               "added": 0, "unreadable": 0, "started_at": "x", "finished_at": None}
        r = await api_client.post("/api/crawl/j1/recheck-all", headers=auth_headers)
        assert r.status_code == 409 and r.json()["error"]["code"] == "RECHECK_IN_PROGRESS"
        assert "0 of 5" in r.json()["error"]["message"]

    async def test_one_failing_page_does_not_end_the_run(self, api_client, auth_headers, test_store):
        await _job(test_store, n_pages=2)
        calls = []

        async def fake_rescan(job_id, url, store):
            calls.append(url)
            if url.endswith("p0"):
                raise RuntimeError("boom")
            return {"url": url, "status_code": 200, "resolved": 0, "added": 0}

        with patch.object(crawl_router, "rescan_url", side_effect=fake_rescan), \
                patch.object(crawl_router.asyncio, "sleep", new=AsyncMock()):
            await api_client.post("/api/crawl/j1/recheck-all", headers=auth_headers)
        assert len(calls) == 2
        body = (await api_client.get("/api/crawl/j1/recheck-all/status", headers=auth_headers)).json()
        assert body["done"] == 2 and body["unreadable"] == 1 and body["running"] is False


class TestPolitenessBothWays:
    async def test_recheck_refuses_while_a_crawl_of_the_host_runs(self, api_client, auth_headers, test_store):
        await _job(test_store, job_id="done")
        await _job(test_store, status="running", job_id="live", n_pages=1)
        r = await api_client.post("/api/crawl/done/recheck-all", headers=auth_headers)
        assert r.status_code == 409 and r.json()["error"]["code"] == "CRAWL_IN_PROGRESS_FOR_DOMAIN"

    async def test_start_refuses_while_a_recheck_of_the_host_runs(self, api_client, auth_headers, test_store):
        await _job(test_store, job_id="done")
        crawl_router._recheck_progress["done"] = {"running": True, "done": 1, "total": 3, "resolved": 0, "added": 0,
                                                 "unreadable": 0, "started_at": "x", "finished_at": None,
                                                 "host": "example.com"}
        with patch("api.routers.crawl._run_crawl_background", new_callable=AsyncMock):
            r = await api_client.post("/api/crawl/start", headers=auth_headers, json={"target_url": BASE})
        assert r.status_code == 409 and r.json()["error"]["code"] == "RECHECK_IN_PROGRESS"

    async def test_status_never_leaks_the_host_key(self, api_client, auth_headers, test_store):
        await _job(test_store, job_id="j1")
        crawl_router._recheck_progress["j1"] = {"running": False, "done": 1, "total": 1, "resolved": 0, "added": 0,
                                               "unreadable": 0, "started_at": "x", "finished_at": "y", "host": "example.com"}
        body = (await api_client.get("/api/crawl/j1/recheck-all/status", headers=auth_headers)).json()
        assert "host" not in body
