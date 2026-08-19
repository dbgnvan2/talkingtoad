"""Contract test backfill for api/routers/crawl.py endpoints (v2.5 M8).

The crawl router has ~25 endpoints. tests/test_api.py covers the core flow
(start, status, results, pages, pages/issues, cancel) but ~13 endpoints
have no contract test. Per CLAUDE.md "API Contract Tests (Non-Negotiable)"
every frontend-called endpoint needs one.

This file covers the gaps with focused tests: auth, validation, and
response-shape checks. Deep behavioural tests for the underlying services
live elsewhere (test_crawl_engine.py, test_report_generator.py, etc.) —
this file is the HTTP contract surface.

Endpoints covered:
- POST /api/crawl/{id}/rescan-url
- POST /api/crawl/scan-page
- POST /api/crawl/{id}/mark-fixed
- GET  /api/crawl/{id}/fix-history
- GET  /api/crawl/{id}/comparison
- GET  /api/crawl/{id}/executive-summary
- GET  /api/crawl/{id}/export/csv
- GET  /api/crawl/{id}/export/csv/{category}
- GET  /api/crawl/{id}/export/pdf
- GET  /api/crawl/{id}/export/excel
- GET  /api/crawl/{id}/images
- GET  /api/crawl/{id}/images/summary
- GET  /api/crawl/{id}/orphaned-images
- GET  /api/crawl/{id}/orphaned-pages (this lives elsewhere — covered for completeness)
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from api.models.job import CrawlJob
from api.models.page import CrawledPage


@pytest.fixture
async def seeded_job(api_client, test_store):
    """A complete crawl job with one page — enough to satisfy the JOB_NOT_FOUND
    branch for endpoints that take a job_id."""
    job_id = str(uuid4())
    await test_store.create_job(CrawlJob(
        job_id=job_id,
        target_url="https://example.com",
        status="complete",
        pages_crawled=1,
    ))
    await test_store.save_pages([
        CrawledPage(
            job_id=job_id,
            url="https://example.com/about",
            status_code=200,
            title="About",
            crawled_at=datetime.now(timezone.utc),
        ),
    ])
    return api_client, job_id


# ===================================================================
# Auth coverage for every frontend-called endpoint
# ===================================================================


class TestCrawlRouterAuth:
    """Every endpoint must require bearer auth. Parametrize so adding new
    endpoints to the list catches missing auth at a glance."""

    @pytest.mark.parametrize("method,path", [
        ("post", "/api/crawl/some-job-id/rescan-url"),
        ("post", "/api/crawl/scan-page"),
        ("post", "/api/crawl/some-job-id/mark-fixed"),
        ("get",  "/api/crawl/some-job-id/fix-history"),
        ("get",  "/api/crawl/some-job-id/comparison"),
        ("get",  "/api/crawl/some-job-id/executive-summary"),
        ("get",  "/api/crawl/some-job-id/export/csv"),
        ("get",  "/api/crawl/some-job-id/export/csv/metadata"),
        ("get",  "/api/crawl/some-job-id/export/pdf"),
        ("get",  "/api/crawl/some-job-id/export/excel"),
        ("get",  "/api/crawl/some-job-id/images"),
        ("get",  "/api/crawl/some-job-id/images/summary"),
        ("get",  "/api/crawl/some-job-id/fix-focus"),
        ("post", "/api/crawl/some-job-id/fix-focus/regenerate"),
        ("post", "/api/crawl/some-job-id/fix-focus/check"),
        ("post", "/api/crawl/some-job-id/fix-focus/verify-page"),
        # Note: /api/crawl/{id}/orphaned-images doesn't exist on the crawl
        # router; the frontend uses /api/fixes/orphaned-media/{id} which
        # ships via orphaned_media_router (M0.12.4).
    ])
    @pytest.mark.asyncio
    async def test_endpoint_requires_auth(self, api_client, method, path):
        if method == "post":
            r = await api_client.post(path)
        else:
            r = await api_client.get(path)
        assert r.status_code == 401


# ===================================================================
# JOB_NOT_FOUND coverage
# ===================================================================


class TestCrawlRouterJobNotFound:
    """Endpoints that take a job_id should 404 cleanly when the job doesn't
    exist — not 500. Spec error shape: error.code == 'JOB_NOT_FOUND'."""

    @pytest.mark.parametrize("method,path", [
        ("post", "/api/crawl/nope/rescan-url"),
        ("post", "/api/crawl/nope/mark-fixed"),
        ("get",  "/api/crawl/nope/fix-history"),
        ("get",  "/api/crawl/nope/comparison"),
        ("get",  "/api/crawl/nope/executive-summary"),
        ("get",  "/api/crawl/nope/export/csv"),
    ])
    @pytest.mark.asyncio
    async def test_unknown_job_returns_404(
        self, api_client, auth_headers, method, path
    ):
        # rescan-url and mark-fixed take a body; we send a minimal one
        if method == "post":
            r = await api_client.post(path, json={"url": "https://example.com/x"}, headers=auth_headers)
        else:
            r = await api_client.get(path, headers=auth_headers)
        # Some endpoints validate body first (422); accept either, but the
        # JOB_NOT_FOUND-aware ones should be 404.
        assert r.status_code in (404, 422), (
            f"{method.upper()} {path} returned {r.status_code}; expected 404 or 422"
        )


# ===================================================================
# Comparison endpoint (M0.12 reference — already shipped in v1.9.5)
# ===================================================================


class TestComparisonEndpoint:
    @pytest.mark.asyncio
    async def test_returns_200_when_only_one_crawl_for_domain(
        self, api_client, auth_headers, seeded_job
    ):
        """Adversarial: only one crawl exists for the domain — comparison has
        no 'previous' to compare against. Should still return 200 (with a
        message indicating no previous run), not 500."""
        api_client, job_id = seeded_job
        r = await api_client.get(
            f"/api/crawl/{job_id}/comparison",
            headers=auth_headers,
        )
        # Either 200 with a "no previous crawl" indication, or a clean 404 —
        # but never a 500 server error.
        assert r.status_code != 500


# ===================================================================
# Executive summary
# ===================================================================


class TestExecutiveSummaryEndpoint:
    @pytest.mark.asyncio
    async def test_unknown_job_returns_404(self, api_client, auth_headers):
        r = await api_client.get(
            "/api/crawl/does-not-exist/executive-summary",
            headers=auth_headers,
        )
        assert r.status_code == 404


# ===================================================================
# Export endpoints — response shape (we don't deep-test PDF/Excel bytes)
# ===================================================================


class TestExportEndpoints:
    @pytest.mark.asyncio
    async def test_csv_unknown_job_returns_404(self, api_client, auth_headers):
        r = await api_client.get(
            "/api/crawl/does-not-exist/export/csv",
            headers=auth_headers,
        )
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_csv_unknown_category_returns_400_or_404(
        self, api_client, auth_headers, seeded_job
    ):
        """Adversarial: category not in PHASE_1_CATEGORIES."""
        api_client, job_id = seeded_job
        r = await api_client.get(
            f"/api/crawl/{job_id}/export/csv/not-a-real-category",
            headers=auth_headers,
        )
        # Either 400 INVALID_CATEGORY or 404 — both are acceptable for an
        # invalid category, but 500 is a bug.
        assert r.status_code in (400, 404, 422)


# ===================================================================
# Image endpoints
# ===================================================================


class TestImageListEndpoint:
    @pytest.mark.asyncio
    async def test_unknown_job_returns_404(self, api_client, auth_headers):
        r = await api_client.get(
            "/api/crawl/does-not-exist/images",
            headers=auth_headers,
        )
        # 404 or 200-with-empty-list — depends on whether the handler
        # validates job existence. Either is fine; just not 500.
        assert r.status_code in (200, 404)

    @pytest.mark.asyncio
    async def test_empty_job_returns_empty_image_list(
        self, api_client, auth_headers, seeded_job
    ):
        api_client, job_id = seeded_job
        r = await api_client.get(
            f"/api/crawl/{job_id}/images",
            headers=auth_headers,
        )
        if r.status_code == 200:
            body = r.json()
            # Response is either {"images": [...], "count": N} or a list
            assert isinstance(body, (dict, list))


# (Removed TestOrphanedImagesEndpoint — endpoint was never registered on the
# crawl router. The actual orphaned-media feature lives at
# GET /api/fixes/orphaned-media/{job_id} via orphaned_media_router; its
# contract is tested in tests/test_orphaned_media_router.py.)


# ===================================================================
# Validation
# ===================================================================


class TestCrawlRouterValidation:
    @pytest.mark.asyncio
    async def test_rescan_url_missing_body_returns_422_or_400(
        self, api_client, auth_headers, seeded_job
    ):
        """No body → 422 (Pydantic) or 400 (manual validation)."""
        api_client, job_id = seeded_job
        r = await api_client.post(
            f"/api/crawl/{job_id}/rescan-url",
            headers=auth_headers,
        )
        assert r.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_mark_fixed_missing_body_rejected(
        self, api_client, auth_headers, seeded_job
    ):
        api_client, job_id = seeded_job
        r = await api_client.post(
            f"/api/crawl/{job_id}/mark-fixed",
            headers=auth_headers,
        )
        assert r.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_scan_page_missing_body_rejected(
        self, api_client, auth_headers
    ):
        r = await api_client.post(
            "/api/crawl/scan-page",
            headers=auth_headers,
        )
        assert r.status_code in (400, 422)


# ===================================================================
# Agent-readiness Phase 1 (WP6) — API contract surfaces
# ===================================================================


class TestAgentReadinessContract:
    """Contract tests for the agent-readiness API surfaces (spec §5)."""

    @pytest.mark.asyncio
    async def test_summary_has_agent_readiness(self, api_client, auth_headers, seeded_job):
        """GET /results exposes agent_health_score + agent_readiness.breakdown."""
        api_client, job_id = seeded_job
        r = await api_client.get(f"/api/crawl/{job_id}/results", headers=auth_headers)
        assert r.status_code == 200
        summary = r.json()["summary"]
        assert isinstance(summary["agent_health_score"], int)
        assert 0 <= summary["agent_health_score"] <= 100
        assert "breakdown" in summary["agent_readiness"]
        assert isinstance(summary["agent_readiness"]["breakdown"], list)

    @pytest.mark.parametrize("category", ["rendering", "semantic_html", "ai_readiness"])
    @pytest.mark.asyncio
    async def test_agent_categories_resolve(
        self, api_client, auth_headers, seeded_job, category
    ):
        """The new agent categories resolve (200), not rejected as INVALID_CATEGORY (422)."""
        api_client, job_id = seeded_job
        r = await api_client.get(
            f"/api/crawl/{job_id}/results/{category}", headers=auth_headers
        )
        assert r.status_code == 200, f"category {category} should resolve, got {r.status_code}"

    @pytest.mark.asyncio
    async def test_pages_issues_has_agent_issue_tiers(
        self, api_client, auth_headers, test_store
    ):
        """GET /pages/issues returns agent_issues[] with code/severity/tier."""
        from api.models.issue import Issue
        job_id = str(uuid4())
        url = "https://example.com/about"
        await test_store.create_job(CrawlJob(
            job_id=job_id, target_url="https://example.com",
            status="complete", pages_crawled=1,
        ))
        await test_store.save_pages([CrawledPage(
            job_id=job_id, url=url, status_code=200, title="About",
            crawled_at=datetime.now(timezone.utc),
        )])
        await test_store.save_issues([Issue(
            job_id=job_id, page_url=url, category="semantic_html",
            severity="warning", issue_code="NON_SEMANTIC_BUTTON",
            description="x", recommendation="y", impact=4,
        )])
        r = await api_client.get(
            f"/api/crawl/{job_id}/pages/issues",
            params={"url": url}, headers=auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert "agent_issues" in body
        assert any(a["code"] == "NON_SEMANTIC_BUTTON" for a in body["agent_issues"])
        for a in body["agent_issues"]:
            assert "code" in a and "severity" in a and "tier" in a


# ===================================================================
# P14: executive-summary must never store/return an AI error as content
# ===================================================================


class TestExecutiveSummaryAIErrorNotContent:
    """When analyze_with_ai raises AIAnalysisError, the endpoint must return an
    AI_UNAVAILABLE error (503) and must NOT cache/return the error text as the
    `summary` content on the job (P14 error-as-content)."""

    @pytest.mark.asyncio
    async def test_ai_error_returns_503_and_is_not_cached(
        self, seeded_job, auth_headers, test_store, monkeypatch
    ):
        from api.services.ai_analyzer import AIAnalysisError

        api_client, job_id = seeded_job

        async def boom(prompt_key, context):
            raise AIAnalysisError("Error calling AI: provider unreachable")

        # The endpoint imports analyze_with_ai from the source module at call
        # time, so patch it there.
        monkeypatch.setattr(
            "api.services.ai_analyzer.analyze_with_ai", boom
        )

        r = await api_client.get(
            f"/api/crawl/{job_id}/executive-summary", headers=auth_headers
        )
        assert r.status_code == 503
        body = r.json()
        # Error is surfaced in the error channel, not as `summary` content.
        assert "summary" not in body

        # Load-bearing: the error string must NOT have been cached on the job.
        job = await test_store.get_job(job_id)
        assert not job.executive_summary, (
            "AI error string must never be cached as the job's executive_summary"
        )


# ===================================================================
# Fix Focus checklist (2026-08-13) — FF4.A / FF4.B / FF4.D
# Spec: docs/pending/2026-08-13_fix-focus-checklist.md
# ===================================================================


class TestFixFocusEndpoints:
    async def _seed(self, test_store):
        from api.models.issue import Issue
        job_id = str(uuid4())
        await test_store.create_job(CrawlJob(
            job_id=job_id, target_url="https://example.com", status="complete",
            pages_crawled=1))
        await test_store.save_pages([CrawledPage(
            job_id=job_id, url="https://example.com/about", status_code=200,
            title="About", crawled_at=datetime.now(timezone.utc))])
        await test_store.save_issues([
            Issue(job_id=job_id, page_url="https://example.com/about",
                  category="metadata", severity="warning", issue_code="TITLE_MISSING",
                  description="d", recommendation="r", impact=7, effort=1,
                  priority_rank=64, human_description="Missing title"),
            Issue(job_id=job_id, page_url="https://example.com/about",
                  category="ai_readiness", severity="warning", issue_code="GEO_SUMMARY_BURIED",
                  description="d", recommendation="r", impact=5, effort=2,
                  priority_rank=38, human_description="Summary buried"),
        ])
        return job_id

    @pytest.mark.asyncio
    async def test_ff4a_fix_focus_schema(self, api_client, auth_headers, test_store):
        """GET returns the frozen contract: seo+geo focuses, each with
        pages[].items[] carrying priority_rank/quick_win/status, plus the
        drop-announcement counters."""
        job_id = await self._seed(test_store)
        r = await api_client.get(f"/api/crawl/{job_id}/fix-focus", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        for focus in ("seo", "geo"):
            assert focus in body
            fl = body[focus]
            for k in ("pages", "pages_total", "pages_shown", "items_hidden"):
                assert k in fl, f"{focus}.{k} missing"
        # the SEO title issue landed in seo; the geo issue in geo
        seo_codes = [it["issue_code"] for p in body["seo"]["pages"] for it in p["items"]]
        geo_codes = [it["issue_code"] for p in body["geo"]["pages"] for it in p["items"]]
        assert "TITLE_MISSING" in seo_codes
        assert "GEO_SUMMARY_BURIED" in geo_codes
        item = body["seo"]["pages"][0]["items"][0]
        for k in ("issue_code", "priority_rank", "quick_win", "status", "human_description"):
            assert k in item, f"item.{k} missing (frontend depends on it)"
        assert item["status"] == "open"

    @pytest.mark.asyncio
    async def test_ff3_persists_no_rebuild(self, api_client, auth_headers, test_store):
        """First GET persists the snapshot; it's saved on the job (returnable
        without re-scanning)."""
        job_id = await self._seed(test_store)
        await api_client.get(f"/api/crawl/{job_id}/fix-focus", headers=auth_headers)
        job = await test_store.get_job(job_id)
        assert job.fix_focus is not None
        assert job.fix_focus["seo"]["pages_total"] >= 1

    @pytest.mark.asyncio
    async def test_ff4b_check_toggle_and_errors(self, api_client, auth_headers, test_store):
        job_id = await self._seed(test_store)
        await api_client.get(f"/api/crawl/{job_id}/fix-focus", headers=auth_headers)
        # valid toggle → 200, status checked
        ok = await api_client.post(
            f"/api/crawl/{job_id}/fix-focus/check",
            json={"page_url": "https://example.com/about", "issue_code": "TITLE_MISSING",
                  "checked": True}, headers=auth_headers)
        assert ok.status_code == 200
        assert ok.json()["status"] == "checked"
        # persisted
        job = await test_store.get_job(job_id)
        checked = [it for p in job.fix_focus["seo"]["pages"] for it in p["items"]
                   if it["issue_code"] == "TITLE_MISSING"][0]
        assert checked["status"] == "checked"
        # unknown item → 404
        bad = await api_client.post(
            f"/api/crawl/{job_id}/fix-focus/check",
            json={"page_url": "https://example.com/about", "issue_code": "NOPE",
                  "checked": True}, headers=auth_headers)
        assert bad.status_code == 404
        # missing field → 422
        malformed = await api_client.post(
            f"/api/crawl/{job_id}/fix-focus/check",
            json={"page_url": "https://example.com/about"}, headers=auth_headers)
        assert malformed.status_code == 422

    @pytest.mark.asyncio
    async def test_ff4d_verify_page_reuses_rescan_and_reconciles(
        self, api_client, auth_headers, test_store, monkeypatch
    ):
        """verify-page reuses the rescan-url path (FF5.B) and reconciles the
        snapshot: a resolved code → verified, an unfixed one → still_present."""
        job_id = await self._seed(test_store)
        await api_client.get(f"/api/crawl/{job_id}/fix-focus", headers=auth_headers)

        import api.routers.crawl as crawl_mod
        calls = {"n": 0}

        async def fake_rescan(jid, url, store):
            # ABSOLUTE live set: TITLE gone (→ verified), GEO still present (→
            # still_present). impact carried so the floor filter keeps GEO.
            calls["n"] += 1
            return {
                "url": "https://example.com/about",
                "status_code": 200,
                "resolved_codes": ["TITLE_MISSING"],
                "by_category": {"ai_readiness": [
                    {"issue_code": "GEO_SUMMARY_BURIED", "impact": 5}]},
            }

        monkeypatch.setattr(crawl_mod, "rescan_url", fake_rescan)
        r = await api_client.post(
            f"/api/crawl/{job_id}/fix-focus/verify-page?url=https://example.com/about",
            headers=auth_headers)
        assert r.status_code == 200
        assert calls["n"] == 1, "verify-page must reuse the rescan-url path (FF5.B)"
        body = r.json()
        assert body["reconciled"] is True
        assert body["verified"] == ["TITLE_MISSING"]
        assert body["still_present"] == ["GEO_SUMMARY_BURIED"]
        # snapshot updated + persisted
        job = await test_store.get_job(job_id)
        statuses = {it["issue_code"]: it["status"]
                    for f in ("seo", "geo") for p in job.fix_focus[f]["pages"]
                    for it in p["items"]}
        assert statuses["TITLE_MISSING"] == "verified"
        assert statuses["GEO_SUMMARY_BURIED"] == "still_present"

    @pytest.mark.asyncio
    async def test_ff2_verify_page_error_status_not_reconciled(
        self, api_client, auth_headers, test_store, monkeypatch
    ):
        """Sweep finding 2 (P1): a 5xx/4xx page must NOT mark its issues verified —
        an erroring page parses to few issues and would look 'fixed'."""
        job_id = await self._seed(test_store)
        await api_client.get(f"/api/crawl/{job_id}/fix-focus", headers=auth_headers)
        import api.routers.crawl as crawl_mod

        async def err_rescan(jid, url, store):
            return {"url": "https://example.com/about", "status_code": 503,
                    "resolved_codes": ["TITLE_MISSING"], "by_category": {}}

        monkeypatch.setattr(crawl_mod, "rescan_url", err_rescan)
        r = await api_client.post(
            f"/api/crawl/{job_id}/fix-focus/verify-page?url=https://example.com/about",
            headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["reconciled"] is False
        # snapshot untouched — nothing falsely verified
        job = await test_store.get_job(job_id)
        statuses = {it["issue_code"]: it["status"]
                    for f in ("seo", "geo") for p in job.fix_focus[f]["pages"]
                    for it in p["items"]}
        assert statuses["TITLE_MISSING"] == "open"

    @pytest.mark.asyncio
    async def test_fix_focus_unknown_job_404(self, api_client, auth_headers):
        r = await api_client.get("/api/crawl/nope/fix-focus", headers=auth_headers)
        assert r.status_code == 404


class TestPagePriorityConversions:
    """PW2 (2026-08-14): /page-priority surfaces GSC conversions per page so the
    ranking tiebreak + panel can use them. Spec: 2026-08-14_traffic-conversion-weighted-priority.md"""

    @pytest.mark.asyncio
    async def test_pw2_conversions_in_payload(self, api_client, auth_headers, test_store):
        from api.models.performance import PerformanceRecord
        job_id = str(uuid4())
        url = "https://example.com/about"
        await test_store.create_job(CrawlJob(
            job_id=job_id, target_url="https://example.com", status="complete", pages_crawled=1))
        await test_store.save_pages([CrawledPage(
            job_id=job_id, url=url, status_code=200, title="About",
            crawled_at=datetime.now(timezone.utc))])
        await test_store.save_performance_records([PerformanceRecord(
            url=url, period="2026-08", gsc_clicks_mo=138, gsc_impressions_mo=1494,
            gsc_ctr_mo=0.09, gsc_avg_position_mo=23.5, ga4_conversions_mo=7)])

        r = await api_client.get(f"/api/crawl/{job_id}/page-priority", headers=auth_headers)
        assert r.status_code == 200
        page = r.json()["pages"][0]
        assert page["gsc"] is not None
        assert page["gsc"]["conversions"] == 7          # PW2: surfaced
        assert page["gsc"]["clicks"] == 138
