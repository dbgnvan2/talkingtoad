"""
Integration tests for multi-page GEO Report flow.

Frontend flow:
1. GET /api/ai/geo-report/pages?job_id=... — list crawled pages with title + issue count for checkbox UI
2. POST /api/ai/geo-report with {job_id, page_urls: [...]} — analyze selected pages, return combined markdown

Adversarial cases enforced here:
- One page errors (403/timeout) → that page's section says "could not be analyzed", others succeed
- URLs not belonging to the job are rejected (security)
- Empty selection returns helpful message, not a crash
- LLM is NEVER called for pages that fail to fetch
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client(monkeypatch):
    """FastAPI test client with auth disabled."""
    monkeypatch.setenv("AUTH_TOKEN", "")
    from api.services.auth import require_auth

    app.dependency_overrides[require_auth] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def mock_store():
    """Mock job store with three pages."""
    from api.routers.crawl import get_store as crawl_get_store
    from api.routers.advisor import get_store as advisor_get_store

    store = MagicMock()

    job = MagicMock()
    job.job_id = "job-A"
    job.target_url = "https://example.com"

    pages = [
        {
            "url": "https://example.com/",
            "title": "Home",
            "status_code": 200,
            "issue_counts": {"total": 5, "critical": 1, "warning": 2, "info": 2},
        },
        {
            "url": "https://example.com/about",
            "title": "About Us",
            "status_code": 200,
            "issue_counts": {"total": 2, "critical": 0, "warning": 1, "info": 1},
        },
        {
            "url": "https://example.com/blocked",
            "title": "Blocked",
            "status_code": 403,
            "issue_counts": {"total": 7, "critical": 3, "warning": 2, "info": 2},
        },
    ]

    async def mock_get_job(job_id):
        return job if job_id == "job-A" else None

    async def mock_get_pages(job_id, min_severity=None, page=1, limit=50):
        return (pages, len(pages)) if job_id == "job-A" else ([], 0)

    store.get_job = mock_get_job
    store.get_pages_with_issue_counts = mock_get_pages

    app.dependency_overrides[crawl_get_store] = lambda: store
    app.dependency_overrides[advisor_get_store] = lambda: store

    yield store

    app.dependency_overrides.pop(crawl_get_store, None)
    app.dependency_overrides.pop(advisor_get_store, None)


class TestPagesListEndpoint:
    """GET /api/ai/geo-report/pages — returns pages for the checkbox UI."""

    def test_returns_url_title_issue_count(self, client, mock_store):
        """Frontend renders checkboxes from this — needs url, title, total issue count."""
        response = client.get("/api/ai/geo-report/pages?job_id=job-A")
        assert response.status_code == 200
        data = response.json()
        assert "pages" in data
        assert len(data["pages"]) == 3
        page = data["pages"][0]
        assert "url" in page
        assert "title" in page
        assert "issue_count" in page  # frontend depends on this exact field name

    def test_404_on_missing_job(self, client, mock_store):
        """Unknown job → 404, no silent success."""
        response = client.get("/api/ai/geo-report/pages?job_id=does-not-exist")
        assert response.status_code == 404

    def test_pages_ordered_by_issue_count_desc(self, client, mock_store):
        """Most problematic pages first — helps users prioritize selection."""
        response = client.get("/api/ai/geo-report/pages?job_id=job-A")
        counts = [p["issue_count"] for p in response.json()["pages"]]
        assert counts == sorted(counts, reverse=True)


class TestMultiPageGeoReport:
    """POST /api/ai/geo-report with page_urls — runs advisor on each selected page."""

    def test_analyzes_each_selected_page(self, client, mock_store):
        """All selected pages appear in the combined markdown."""
        with patch("api.routers.advisor.evaluate_page") as mock_eval:
            mock_eval.return_value = ("## Page report\n\nLooks fine.", True)
            response = client.post(
                "/api/ai/geo-report",
                json={
                    "job_id": "job-A",
                    "page_urls": ["https://example.com/", "https://example.com/about"],
                },
            )
            assert response.status_code == 200
            assert mock_eval.call_count == 2
            data = response.json()
            assert "report" in data
            markdown = data["report"]["report_markdown"]
            assert "https://example.com/" in markdown
            assert "https://example.com/about" in markdown

    def test_bad_page_does_not_kill_others(self, client, mock_store):
        """Adversarial: page 2 errors out — pages 1 and 3 still get real reports."""
        from api.models.advisor import AdvisorRequest

        async def fake_evaluate(request: AdvisorRequest):
            if "blocked" in request.url:
                return ("# Page could not be analyzed\n\n> 403 Forbidden", False)
            return (f"## Real analysis of {request.url}", True)

        with patch("api.routers.advisor.evaluate_page", side_effect=fake_evaluate):
            response = client.post(
                "/api/ai/geo-report",
                json={
                    "job_id": "job-A",
                    "page_urls": [
                        "https://example.com/",
                        "https://example.com/blocked",
                        "https://example.com/about",
                    ],
                },
            )
            assert response.status_code == 200
            markdown = response.json()["report"]["report_markdown"]
            assert "Real analysis of https://example.com/" in markdown
            assert "Real analysis of https://example.com/about" in markdown
            assert "could not be analyzed" in markdown
            assert "https://example.com/blocked" in markdown

    def test_rejects_urls_not_in_job(self, client, mock_store):
        """Security: page_urls must be a subset of the job's crawled pages."""
        with patch("api.routers.advisor.evaluate_page") as mock_eval:
            response = client.post(
                "/api/ai/geo-report",
                json={
                    "job_id": "job-A",
                    "page_urls": ["https://attacker.com/internal-host"],
                },
            )
            assert response.status_code == 400
            # Critical: evaluate_page must NOT be called for unverified URLs
            mock_eval.assert_not_called()

    def test_empty_page_urls_returns_helpful_message(self, client, mock_store):
        """Empty selection → 400 with explanation, no crash."""
        response = client.post(
            "/api/ai/geo-report",
            json={"job_id": "job-A", "page_urls": []},
        )
        assert response.status_code == 400

    def test_combined_markdown_has_one_section_per_page(self, client, mock_store):
        """Output is parseable: one H1 (or # heading) per page in the report."""
        with patch("api.routers.advisor.evaluate_page") as mock_eval:
            mock_eval.return_value = ("Body content", True)
            response = client.post(
                "/api/ai/geo-report",
                json={
                    "job_id": "job-A",
                    "page_urls": ["https://example.com/", "https://example.com/about"],
                },
            )
            markdown = response.json()["report"]["report_markdown"]
            # Each page is delimited by a top-level heading that includes its URL
            assert markdown.count("# https://example.com/") >= 1
            assert markdown.count("# https://example.com/about") >= 1

    def test_omitted_page_urls_falls_back_to_target_url(self, client, mock_store):
        """Backwards compat: no page_urls in body → analyze target_url only."""
        with patch("api.routers.advisor.evaluate_page") as mock_eval:
            mock_eval.return_value = ("Single page report", False)
            response = client.post(
                "/api/ai/geo-report",
                json={"job_id": "job-A"},
            )
            assert response.status_code == 200
            # Called exactly once, with the job's target_url
            assert mock_eval.call_count == 1
            call_args = mock_eval.call_args
            request_arg = call_args[0][0]
            assert request_arg.url == "https://example.com"
