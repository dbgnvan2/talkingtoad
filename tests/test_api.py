"""
API endpoint integration tests (spec §6).

Uses an in-memory SQLite store injected via dependency override.
The crawl engine is mocked so no real HTTP requests are made.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from api.crawler.engine import CrawlResult
from api.models.issue import Issue
from api.models.job import CrawlJob
from api.models.page import CrawledPage


# ── Helpers ────────────────────────────────────────────────────────────────

def _job(
    job_id: str | None = None,
    status: str = "complete",
    pages_crawled: int = 5,
) -> CrawlJob:
    return CrawlJob(
        job_id=job_id or str(uuid4()),
        target_url="https://example.com",
        status=status,
        pages_crawled=pages_crawled,
    )


def _issue(
    job_id: str,
    *,
    category: str = "metadata",
    severity: str = "warning",
    page_url: str = "https://example.com/page",
    impact: int = 0,
) -> Issue:
    priority_rank = (impact * 10) - 2 if impact > 0 else 0
    return Issue(
        job_id=job_id,
        page_url=page_url,
        category=category,
        severity=severity,
        issue_code="TITLE_TOO_SHORT",
        description="Title under 30 characters",
        recommendation="Expand the title.",
        impact=impact,
        priority_rank=priority_rank,
    )


def _page(job_id: str, url: str = "https://example.com/page") -> CrawledPage:
    return CrawledPage(
        job_id=job_id,
        url=url,
        status_code=200,
        crawled_at=datetime.now(timezone.utc),
    )


async def _seed(store, job: CrawlJob, issues: list[Issue] | None = None, pages: list[CrawledPage] | None = None):
    await store.create_job(job)
    if issues:
        await store.save_issues(issues)
    if pages:
        await store.save_pages(pages)


# ── Utility endpoints ──────────────────────────────────────────────────────

class TestHealthEndpoint:
    async def test_health_returns_ok(self, api_client, auth_headers):
        r = await api_client.get("/api/health", headers=auth_headers)
        assert r.status_code == 200
        assert r.json() == {"status": "ok", "version": "1.8"}

    async def test_health_no_auth_required(self, api_client):
        # /api/health is on the utility router which has no auth dependency
        r = await api_client.get("/api/health")
        assert r.status_code == 200


# ── Auth middleware ────────────────────────────────────────────────────────

class TestAuthMiddleware:
    async def test_missing_token_returns_401(self, api_client):
        r = await api_client.post("/api/crawl/start", json={"target_url": "https://example.com"})
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "UNAUTHORIZED"

    async def test_wrong_token_returns_401(self, api_client):
        r = await api_client.post(
            "/api/crawl/start",
            json={"target_url": "https://example.com"},
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert r.status_code == 401

    async def test_correct_token_accepted(self, api_client, auth_headers):
        with patch("api.routers.crawl._run_crawl_background", new_callable=AsyncMock):
            r = await api_client.post(
                "/api/crawl/start",
                json={"target_url": "https://example.com"},
                headers=auth_headers,
            )
        assert r.status_code == 202


# ── POST /api/crawl/start ──────────────────────────────────────────────────

class TestStartCrawl:
    async def test_start_returns_job_id_and_poll_url(self, api_client, auth_headers):
        with patch("api.routers.crawl._run_crawl_background", new_callable=AsyncMock):
            r = await api_client.post(
                "/api/crawl/start",
                json={"target_url": "https://example.com"},
                headers=auth_headers,
            )
        assert r.status_code == 202
        data = r.json()
        assert "job_id" in data
        assert data["status"] == "queued"
        assert data["poll_url"].startswith("/api/crawl/")

    async def test_start_invalid_url_returns_422(self, api_client, auth_headers):
        r = await api_client.post(
            "/api/crawl/start",
            json={"target_url": "not-a-url"},
            headers=auth_headers,
        )
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "INVALID_URL"

    async def test_start_missing_url_returns_422(self, api_client, auth_headers):
        r = await api_client.post(
            "/api/crawl/start",
            json={},
            headers=auth_headers,
        )
        assert r.status_code == 422

    async def test_start_creates_job_in_store(self, api_client, auth_headers):
        with patch("api.routers.crawl._run_crawl_background", new_callable=AsyncMock):
            r = await api_client.post(
                "/api/crawl/start",
                json={"target_url": "https://example.com"},
                headers=auth_headers,
            )
        assert r.json()["job_id"] is not None

    async def test_start_custom_settings_accepted(self, api_client, auth_headers):
        with patch("api.routers.crawl._run_crawl_background", new_callable=AsyncMock):
            r = await api_client.post(
                "/api/crawl/start",
                json={
                    "target_url": "https://example.com",
                    "settings": {"max_pages": 100, "crawl_delay_ms": 300},
                },
                headers=auth_headers,
            )
        assert r.status_code == 202


# ── GET /api/crawl/{job_id}/status ─────────────────────────────────────────

class TestJobStatus:
    async def test_status_returns_job_fields(self, api_client, auth_headers, test_store):
        job = _job(status="running", pages_crawled=3)
        await _seed(test_store, job)

        r = await api_client.get(f"/api/crawl/{job.job_id}/status", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "running"
        assert data["pages_crawled"] == 3

    async def test_status_unknown_job_returns_404(self, api_client, auth_headers):
        r = await api_client.get("/api/crawl/no-such-job/status", headers=auth_headers)
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "JOB_NOT_FOUND"


# ── POST /api/crawl/{job_id}/cancel ───────────────────────────────────────

class TestCancelJob:
    async def test_cancel_complete_job_returns_409(self, api_client, auth_headers, test_store):
        job = _job(status="complete")
        await _seed(test_store, job)

        r = await api_client.post(f"/api/crawl/{job.job_id}/cancel", headers=auth_headers)
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "JOB_ALREADY_COMPLETE"

    async def test_cancel_unknown_job_returns_404(self, api_client, auth_headers):
        r = await api_client.post("/api/crawl/no-such-id/cancel", headers=auth_headers)
        assert r.status_code == 404

    async def test_cancel_queued_job_sets_cancelled(self, api_client, auth_headers, test_store):
        job = _job(status="queued")
        await _seed(test_store, job)

        r = await api_client.post(f"/api/crawl/{job.job_id}/cancel", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["status"] == "cancelled"
        updated = await test_store.get_job(job.job_id)
        assert updated.status == "cancelled"


# ── GET /api/crawl/{job_id}/results ───────────────────────────────────────

class TestGetResults:
    async def test_results_returns_summary_and_issues(self, api_client, auth_headers, test_store):
        job = _job()
        issues = [
            _issue(job.job_id, severity="critical"),
            _issue(job.job_id, severity="warning"),
        ]
        await _seed(test_store, job, issues=issues)

        r = await api_client.get(f"/api/crawl/{job.job_id}/results", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["summary"]["total_issues"] == 2
        assert data["summary"]["by_severity"]["critical"] == 1
        assert len(data["issues"]) == 2

    async def test_results_unknown_job_returns_404(self, api_client, auth_headers):
        r = await api_client.get("/api/crawl/no-such-id/results", headers=auth_headers)
        assert r.status_code == 404

    async def test_results_pagination_correct(self, api_client, auth_headers, test_store):
        job = _job()
        issues = [_issue(job.job_id) for _ in range(7)]
        await _seed(test_store, job, issues=issues)

        r = await api_client.get(
            f"/api/crawl/{job.job_id}/results", params={"page": 1, "limit": 3}, headers=auth_headers
        )
        data = r.json()
        assert data["pagination"]["total_issues"] == 7
        assert data["pagination"]["total_pages"] == 3
        assert len(data["issues"]) == 3

    async def test_results_severity_filter(self, api_client, auth_headers, test_store):
        job = _job()
        issues = [
            _issue(job.job_id, severity="critical"),
            _issue(job.job_id, severity="info"),
        ]
        await _seed(test_store, job, issues=issues)

        r = await api_client.get(
            f"/api/crawl/{job.job_id}/results", params={"severity": "critical"}, headers=auth_headers
        )
        data = r.json()
        assert data["pagination"]["total_issues"] == 1
        assert data["issues"][0]["severity"] == "critical"


# ── GET /api/crawl/{job_id}/results/{category} ────────────────────────────

class TestGetResultsByCategory:
    async def test_valid_category_filtered(self, api_client, auth_headers, test_store):
        job = _job()
        issues = [
            _issue(job.job_id, category="metadata"),
            _issue(job.job_id, category="heading"),
        ]
        await _seed(test_store, job, issues=issues)

        r = await api_client.get(
            f"/api/crawl/{job.job_id}/results/metadata", headers=auth_headers
        )
        assert r.status_code == 200
        data = r.json()
        assert all(i["category"] == "metadata" for i in data["issues"])

    async def test_invalid_category_returns_422(self, api_client, auth_headers, test_store):
        job = _job()
        await _seed(test_store, job)

        r = await api_client.get(
            f"/api/crawl/{job.job_id}/results/not_a_category", headers=auth_headers
        )
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "INVALID_CATEGORY"

    async def test_unknown_job_returns_404(self, api_client, auth_headers):
        r = await api_client.get("/api/crawl/no-such/results/metadata", headers=auth_headers)
        assert r.status_code == 404


# ── GET /api/crawl/{job_id}/pages ─────────────────────────────────────────

class TestGetPages:
    async def test_pages_returns_list_with_issue_counts(self, api_client, auth_headers, test_store):
        job = _job()
        pages = [_page(job.job_id, url="https://example.com/about")]
        issues = [_issue(job.job_id, severity="critical")]
        issues[0].page_url = "https://example.com/about"
        await _seed(test_store, job, issues=issues, pages=pages)

        r = await api_client.get(f"/api/crawl/{job.job_id}/pages", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert len(data["pages"]) == 1
        assert data["pages"][0]["issue_counts"]["critical"] == 1

    async def test_pages_unknown_job_returns_404(self, api_client, auth_headers):
        r = await api_client.get("/api/crawl/no-such/pages", headers=auth_headers)
        assert r.status_code == 404

    async def test_pages_min_severity_filter(self, api_client, auth_headers, test_store):
        job = _job()
        pages = [
            _page(job.job_id, url="https://example.com/a"),
            _page(job.job_id, url="https://example.com/b"),
        ]
        issues = [
            Issue(job_id=job.job_id, page_url="https://example.com/a",
                  category="metadata", severity="critical", issue_code="X",
                  description="d", recommendation="r"),
            Issue(job_id=job.job_id, page_url="https://example.com/b",
                  category="metadata", severity="info", issue_code="Y",
                  description="d", recommendation="r"),
        ]
        await _seed(test_store, job, issues=issues, pages=pages)

        r = await api_client.get(
            f"/api/crawl/{job.job_id}/pages",
            params={"min_severity": "critical"},
            headers=auth_headers,
        )
        data = r.json()
        assert data["pagination"]["total_pages"] == 1
        assert data["pages"][0]["url"] == "https://example.com/a"


# ── GET /api/crawl/{job_id}/pages/issues ──────────────────────────────────

class TestGetPageIssues:
    async def test_page_issues_grouped_by_category(self, api_client, auth_headers, test_store):
        job = _job()
        page = _page(job.job_id)
        issues = [
            _issue(job.job_id, category="metadata"),
            _issue(job.job_id, category="heading"),
        ]
        await _seed(test_store, job, issues=issues, pages=[page])

        r = await api_client.get(
            f"/api/crawl/{job.job_id}/pages/issues",
            params={"url": page.url},
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total_issues"] == 2
        assert "metadata" in data["by_category"]
        assert "heading" in data["by_category"]

    async def test_page_issues_unknown_page_returns_404(self, api_client, auth_headers, test_store):
        job = _job()
        await _seed(test_store, job)

        r = await api_client.get(
            f"/api/crawl/{job.job_id}/pages/issues",
            params={"url": "https://example.com/not-crawled"},
            headers=auth_headers,
        )
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "PAGE_NOT_FOUND"

    async def test_page_issues_unknown_job_returns_404(self, api_client, auth_headers):
        r = await api_client.get(
            "/api/crawl/no-such/pages/issues",
            params={"url": "https://example.com/"},
            headers=auth_headers,
        )
        assert r.status_code == 404


# ── CSV export ─────────────────────────────────────────────────────────────

class TestCsvExport:
    async def test_full_csv_contains_correct_columns(self, api_client, auth_headers, test_store):
        job = _job()
        await _seed(test_store, job, issues=[_issue(job.job_id)])

        r = await api_client.get(f"/api/crawl/{job.job_id}/export/csv", headers=auth_headers)
        assert r.status_code == 200
        assert "text/csv" in r.headers["content-type"]
        lines = r.text.strip().splitlines()
        header = lines[0]
        assert "url" in header
        assert "issue_code" in header
        assert "severity" in header
        assert "recommendation" in header

    async def test_full_csv_contains_data_rows(self, api_client, auth_headers, test_store):
        job = _job()
        await _seed(test_store, job, issues=[_issue(job.job_id), _issue(job.job_id)])

        r = await api_client.get(f"/api/crawl/{job.job_id}/export/csv", headers=auth_headers)
        lines = r.text.strip().splitlines()
        assert len(lines) == 3  # header + 2 data rows

    async def test_category_csv_filtered(self, api_client, auth_headers, test_store):
        job = _job()
        issues = [
            _issue(job.job_id, category="metadata"),
            _issue(job.job_id, category="heading"),
        ]
        await _seed(test_store, job, issues=issues)

        r = await api_client.get(
            f"/api/crawl/{job.job_id}/export/csv/metadata", headers=auth_headers
        )
        assert r.status_code == 200
        lines = r.text.strip().splitlines()
        assert len(lines) == 2  # header + 1 metadata issue

    async def test_csv_invalid_category_returns_422(self, api_client, auth_headers, test_store):
        job = _job()
        await _seed(test_store, job)

        r = await api_client.get(
            f"/api/crawl/{job.job_id}/export/csv/bad_cat", headers=auth_headers
        )
        assert r.status_code == 422

    async def test_csv_unknown_job_returns_404(self, api_client, auth_headers):
        r = await api_client.get("/api/crawl/no-such/export/csv", headers=auth_headers)
        assert r.status_code == 404


# ── Utility: robots and sitemap ────────────────────────────────────────────

class TestUtilityEndpoints:
    async def test_robots_endpoint_mocked(self, api_client, auth_headers):
        import respx
        import httpx

        with respx.mock:
            respx.get("https://example.com/robots.txt").mock(
                return_value=httpx.Response(200, text="User-agent: *\nDisallow:\n")
            )
            r = await api_client.get("/api/robots", params={"url": "https://example.com"}, headers=auth_headers)

        assert r.status_code == 200
        data = r.json()
        assert "sitemap_urls" in data

    async def test_sitemap_endpoint_mocked(self, api_client, auth_headers):
        import respx
        import httpx

        xml = ('<?xml version="1.0"?>'
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
               '<url><loc>https://example.com/about</loc></url>'
               '</urlset>')
        with respx.mock:
            respx.get("https://example.com/sitemap.xml").mock(
                return_value=httpx.Response(200, text=xml)
            )
            r = await api_client.get("/api/sitemap", params={"url": "https://example.com"}, headers=auth_headers)

        assert r.status_code == 200
        data = r.json()
        assert data["found"] is True
        assert "https://example.com/about" in data["urls"]


# ── Health score (v1.5 §4.1) ─────────────────────────────────────────────────
#
# v1.5 formula:
#   Page health  = max(0, 100 − Σ(impact of all issues on the page))
#   Site health  = average of all page health scores
# Pages with no issues contribute 100 to the average.

class TestHealthScore:
    async def test_health_score_present_in_summary(self, api_client, auth_headers, test_store):
        """Summary response must include a health_score field."""
        job = _job()
        await _seed(test_store, job)
        r = await api_client.get(f"/api/crawl/{job.job_id}/results", headers=auth_headers)
        assert r.status_code == 200
        assert "health_score" in r.json()["summary"]

    async def test_health_score_perfect_when_no_issues(self, api_client, auth_headers, test_store):
        """No issues and no crawled pages → health score 100 (empty-crawl fallback)."""
        job = _job()
        await _seed(test_store, job)
        r = await api_client.get(f"/api/crawl/{job.job_id}/results", headers=auth_headers)
        assert r.json()["summary"]["health_score"] == 100

    async def test_health_score_perfect_with_pages_and_no_issues(self, api_client, auth_headers, test_store):
        """Crawled pages with no issues → every page scores 100 → site health 100."""
        job = _job(pages_crawled=3)
        pages = [_page(job.job_id, url=f"https://example.com/p{i}") for i in range(3)]
        await _seed(test_store, job, pages=pages)
        r = await api_client.get(f"/api/crawl/{job.job_id}/results", headers=auth_headers)
        assert r.json()["summary"]["health_score"] == 100

    async def test_health_score_uses_impact_values(self, api_client, auth_headers, test_store):
        """v1.5: page health = 100 − sum(impact); site health = average across pages.

        Setup: 5 pages. Page1 has 2 issues with impact=10 each → page health=80.
        Pages 2-5 have no issues → page health=100.
        Site health = (80 + 100 + 100 + 100 + 100) / 5 = 96.
        """
        job = _job(pages_crawled=5)
        pages = [_page(job.job_id, url=f"https://example.com/p{i}") for i in range(5)]
        issues = [
            _issue(job.job_id, page_url="https://example.com/p0", impact=10),
            _issue(job.job_id, page_url="https://example.com/p0", impact=10),
        ]
        await _seed(test_store, job, issues=issues, pages=pages)
        r = await api_client.get(f"/api/crawl/{job.job_id}/results", headers=auth_headers)
        assert r.json()["summary"]["health_score"] == 96

    async def test_health_score_floors_at_zero_per_page(self, api_client, auth_headers, test_store):
        """A page with cumulative impact > 100 still scores 0 (not negative)."""
        job = _job(pages_crawled=2)
        pages = [
            _page(job.job_id, url="https://example.com/bad"),
            _page(job.job_id, url="https://example.com/good"),
        ]
        # 15 issues each with impact=10 → total impact=150 → page health = max(0, 100-150) = 0
        issues = [
            _issue(job.job_id, page_url="https://example.com/bad", impact=10)
            for _ in range(15)
        ]
        await _seed(test_store, job, issues=issues, pages=pages)
        r = await api_client.get(f"/api/crawl/{job.job_id}/results", headers=auth_headers)
        score = r.json()["summary"]["health_score"]
        # site health = (0 + 100) / 2 = 50
        assert score == 50
        assert score >= 0

    async def test_health_score_improves_as_issues_resolved(self, api_client, auth_headers, test_store):
        """Fewer issues on a page → higher site health score."""
        # Setup A: 1 page with impact 50 among 2 pages → site health = (50+100)/2 = 75
        job_a = _job(pages_crawled=2)
        pages_a = [
            _page(job_a.job_id, url="https://example.com/p1"),
            _page(job_a.job_id, url="https://example.com/p2"),
        ]
        issues_a = [_issue(job_a.job_id, page_url="https://example.com/p1", impact=50)]
        await _seed(test_store, job_a, issues=issues_a, pages=pages_a)
        r_a = await api_client.get(f"/api/crawl/{job_a.job_id}/results", headers=auth_headers)
        score_a = r_a.json()["summary"]["health_score"]

        # Setup B: same but impact 20 → site health = (80+100)/2 = 90
        job_b = _job(pages_crawled=2)
        pages_b = [
            _page(job_b.job_id, url="https://example.com/p1"),
            _page(job_b.job_id, url="https://example.com/p2"),
        ]
        issues_b = [_issue(job_b.job_id, page_url="https://example.com/p1", impact=20)]
        await _seed(test_store, job_b, issues=issues_b, pages=pages_b)
        r_b = await api_client.get(f"/api/crawl/{job_b.job_id}/results", headers=auth_headers)
        score_b = r_b.json()["summary"]["health_score"]

        assert score_a == 75
        assert score_b == 90
        assert score_b > score_a


# ── Analysis toggles (v1.3 §3.1) ────────────────────────────────────────────

class TestAnalysisToggles:
    async def test_enabled_analyses_setting_accepted(self, api_client, auth_headers):
        """POST /start accepts enabled_analyses without error."""
        with patch("api.routers.crawl._run_crawl_background", new_callable=AsyncMock):
            r = await api_client.post(
                "/api/crawl/start",
                json={
                    "target_url": "https://example.com",
                    "settings": {"enabled_analyses": ["link_integrity", "seo_essentials"]},
                },
                headers=auth_headers,
            )
        assert r.status_code == 202

    async def test_enabled_analyses_none_sends_all(self, api_client, auth_headers):
        """Omitting enabled_analyses defaults to all analyses enabled."""
        with patch("api.routers.crawl._run_crawl_background", new_callable=AsyncMock):
            r = await api_client.post(
                "/api/crawl/start",
                json={"target_url": "https://example.com", "settings": {}},
                headers=auth_headers,
            )
        assert r.status_code == 202


# ── Security and URL Structure categories (fixed in bugfix session) ───────────

class TestSecurityAndUrlStructureCategories:
    async def test_security_category_accepted(self, api_client, auth_headers, test_store):
        job = _job()
        await _seed(test_store, job)
        r = await api_client.get(f"/api/crawl/{job.job_id}/results/security", headers=auth_headers)
        assert r.status_code == 200

    async def test_url_structure_category_accepted(self, api_client, auth_headers, test_store):
        job = _job()
        await _seed(test_store, job)
        r = await api_client.get(
            f"/api/crawl/{job.job_id}/results/url_structure", headers=auth_headers
        )
        assert r.status_code == 200
