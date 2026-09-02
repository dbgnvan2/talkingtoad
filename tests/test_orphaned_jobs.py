"""A crawl orphaned by a restart never blocks its domain, and cancel really cancels.

Spec:  docs/pending/2026-09-02_phase3-happy-path.md#R3.3 (sweep finding 2)
Tests: this file
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from api.models.job import CrawlJob

BASE = "https://example.com"


async def _job(store, status, job_id="j1"):
    await store.create_job(CrawlJob(job_id=job_id, target_url=BASE, status=status, pages_crawled=1,
                                    started_at=datetime.now(timezone.utc)))


async def test_startup_reaper_fails_queued_and_running_jobs_and_says_why(test_store):
    await _job(test_store, "running", "r")
    await _job(test_store, "queued", "q")
    await _job(test_store, "complete", "c")
    n = await test_store.fail_orphaned_jobs("The server restarted while this scan was running.")
    assert n == 2
    r = await test_store.get_job("r")
    assert r.status == "failed" and "restarted" in (r.error_message or "") and r.completed_at
    assert (await test_store.get_job("c")).status == "complete"
    assert await test_store.active_jobs_for_domain("example.com") == []


async def test_cancel_after_a_restart_writes_the_cancellation(api_client, auth_headers, test_store):
    """No engine, no event — the old handler returned 'cancelled' and wrote nothing."""
    await _job(test_store, "running")
    r = await api_client.post("/api/crawl/j1/cancel", headers=auth_headers)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    job = await test_store.get_job("j1")
    assert job.status == "cancelled", "the store must reflect what the response claimed"
    # ...and the domain is free again.
    with patch("api.routers.crawl._run_crawl_background", new_callable=AsyncMock):
        r = await api_client.post("/api/crawl/start", headers=auth_headers, json={"target_url": BASE})
    assert r.status_code == 202, r.text


async def test_cancel_with_a_live_engine_signals_it_and_leaves_the_write_to_the_engine(api_client, auth_headers, test_store):
    import asyncio
    from api.routers import crawl as crawl_router
    await _job(test_store, "running")
    ev = asyncio.Event()
    crawl_router._cancel_events["j1"] = ev
    try:
        r = await api_client.post("/api/crawl/j1/cancel", headers=auth_headers)
        assert r.status_code == 200 and ev.is_set()
        assert (await test_store.get_job("j1")).status == "running", "the engine writes the final status"
    finally:
        crawl_router._cancel_events.pop("j1", None)
