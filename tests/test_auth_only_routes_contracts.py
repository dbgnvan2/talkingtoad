"""Behavioural contracts for the four routes whose only test used to be the 401 pair.

Spec:  docs/pending/2026-09-02_phase3-happy-path.md#R3.4
Tests: this file — closes `_AUTH_ONLY_COVERAGE` in tests/test_auth_matrix.py.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from api.models.issue import Issue
from api.models.job import CrawlJob
from api.models.page import CrawledPage

BASE = "https://example.com"


async def _job(store, job_id="j1", *, started_at=None, with_issue=True):
    job = CrawlJob(job_id=job_id, target_url=BASE, status="complete", pages_crawled=1,
                   started_at=started_at or datetime.now(timezone.utc))
    await store.create_job(job)
    await store.save_pages([CrawledPage(job_id=job_id, url=f"{BASE}/p", status_code=200,
                                        crawled_at=datetime.now(timezone.utc))])
    if with_issue:
        await store.save_issues([Issue(job_id=job_id, page_url=f"{BASE}/p", category="heading",
                                       severity="warning", issue_code="H1_MISSING",
                                       description="x", recommendation="y", impact=6)])
    return job


class TestRecent:
    async def test_shape_and_order(self, api_client, auth_headers, test_store):
        old = datetime.now(timezone.utc) - timedelta(days=1)
        await _job(test_store, "old", started_at=old)
        await _job(test_store, "new")
        r = await api_client.get("/api/crawl/recent", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert [j["job_id"] for j in body] == ["new", "old"], "newest first"
        for key in ("job_id", "target_url", "status", "pages_crawled", "started_at", "completed_at"):
            assert key in body[0], f"Home.jsx reads {key}"

    async def test_limit_is_capped_at_20(self, api_client, auth_headers, test_store):
        for n in range(25):
            await _job(test_store, f"j{n}", with_issue=False)
        r = await api_client.get("/api/crawl/recent?limit=100", headers=auth_headers)
        assert len(r.json()) == 20


class TestFixFocusRegenerate:
    async def test_unknown_job_is_404(self, api_client, auth_headers):
        r = await api_client.post("/api/crawl/nope/fix-focus/regenerate", headers=auth_headers)
        assert r.status_code == 404 and r.json()["error"]["code"] == "JOB_NOT_FOUND"

    async def test_regenerate_returns_the_snapshot_the_panel_reads(self, api_client, auth_headers, test_store):
        await _job(test_store)
        r = await api_client.post("/api/crawl/j1/fix-focus/regenerate", headers=auth_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        # FixFocusPanel.jsx reads data.seo and data.geo.
        assert "seo" in body and "geo" in body, body.keys()


class TestAnalyzeImageWithAI:
    async def test_unknown_image_returns_the_documented_error_without_an_ai_call(self, api_client, auth_headers, test_store):
        await _job(test_store)
        with patch("api.services.ai_analyzer.analyze_image_with_ai", new_callable=AsyncMock) as ai:
            r = await api_client.post("/api/crawl/j1/images/analyze-ai?image_url=https://example.com/none.jpg",
                                      headers=auth_headers)
        assert r.status_code == 200
        assert "error" in r.json() and "not found" in r.json()["error"].lower()
        ai.assert_not_called()


class TestAiImagesPdf:
    async def test_unknown_job_is_404(self, api_client, auth_headers):
        r = await api_client.get("/api/crawl/nope/export/ai-images-pdf", headers=auth_headers)
        assert r.status_code == 404

    async def test_job_with_no_images_still_renders_a_pdf(self, api_client, auth_headers, test_store):
        await _job(test_store)
        r = await api_client.get("/api/crawl/j1/export/ai-images-pdf", headers=auth_headers)
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith("application/pdf")
        assert r.content[:4] == b"%PDF"
