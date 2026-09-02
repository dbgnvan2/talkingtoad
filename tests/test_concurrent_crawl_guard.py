"""One crawl per domain at a time — both doorways, one guard.

Spec:  docs/pending/2026-09-02_phase3-happy-path.md#R3.3
Tests: this file
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from api.models.job import CrawlJob

BASE = "https://example.com"


async def _job(store, status, url=BASE, job_id="j1"):
    job = CrawlJob(job_id=job_id, target_url=url, status=status, pages_crawled=1,
                   started_at=datetime.now(timezone.utc))
    await store.create_job(job)
    return job


class TestStart:
    async def test_second_start_for_a_running_domain_is_409(self, api_client, auth_headers, test_store):
        await _job(test_store, "running")
        with patch("api.routers.crawl._run_crawl_background", new_callable=AsyncMock):
            r = await api_client.post("/api/crawl/start", headers=auth_headers, json={"target_url": BASE})
        assert r.status_code == 409, r.text
        body = r.json()["error"]
        assert body["code"] == "CRAWL_IN_PROGRESS_FOR_DOMAIN" and "j1" in body["message"]

    async def test_www_and_bare_host_are_one_domain(self, api_client, auth_headers, test_store):
        await _job(test_store, "queued", url="https://www.example.com/")
        with patch("api.routers.crawl._run_crawl_background", new_callable=AsyncMock):
            r = await api_client.post("/api/crawl/start", headers=auth_headers, json={"target_url": "https://example.com"})
        assert r.status_code == 409

    async def test_a_finished_job_never_blocks(self, api_client, auth_headers, test_store):
        for n, status in enumerate(("complete", "failed", "cancelled")):
            await _job(test_store, status, job_id=f"done{n}")
        with patch("api.routers.crawl._run_crawl_background", new_callable=AsyncMock):
            r = await api_client.post("/api/crawl/start", headers=auth_headers, json={"target_url": BASE})
        assert r.status_code == 202, r.text

    async def test_another_domain_is_not_blocked(self, api_client, auth_headers, test_store):
        await _job(test_store, "running", url="https://other.org")
        with patch("api.routers.crawl._run_crawl_background", new_callable=AsyncMock):
            r = await api_client.post("/api/crawl/start", headers=auth_headers, json={"target_url": BASE})
        assert r.status_code == 202, r.text


class TestRescan:
    async def test_rescan_is_guarded_by_the_same_rule(self, api_client, auth_headers, test_store):
        """The source job is complete (so the rescan's own 409 does not fire),
        but ANOTHER job of the same domain is running."""
        await _job(test_store, "complete", job_id="old")
        await _job(test_store, "running", job_id="live", url="https://example.com/other")
        with patch("api.routers.crawl._run_crawl_background", new_callable=AsyncMock):
            r = await api_client.post("/api/crawl/old/rescan", headers=auth_headers)
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "CRAWL_IN_PROGRESS_FOR_DOMAIN"


class TestStoreQuery:
    async def test_active_jobs_for_domain_matches_host_only(self, test_store):
        await _job(test_store, "running", url="https://www.example.com/a", job_id="a")
        await _job(test_store, "queued", url="https://example.com/b", job_id="b")
        await _job(test_store, "complete", url="https://example.com/c", job_id="c")
        await _job(test_store, "running", url="https://notexample.com/", job_id="d")
        ids = {j.job_id for j in await test_store.active_jobs_for_domain("example.com")}
        assert ids == {"a", "b"}
