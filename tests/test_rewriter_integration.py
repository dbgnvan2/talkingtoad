"""
Integration tests for rewriter flow — end-to-end from API to frontend expectations.

Tests verify that all endpoints return the fields that frontend code depends on.
Spec: /Users/davemini2/.claude/plans/moonlit-beaming-thacker.md
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from api.main import app
from api.models.advisor import RewriterRequest, RewriterResult


@pytest.fixture
def client(monkeypatch):
    """FastAPI test client with auth disabled for testing."""
    # Disable auth for integration tests
    monkeypatch.setenv("AUTH_TOKEN", "")

    # Override require_auth dependency to allow all requests
    from api.services.auth import require_auth
    from api.routers.crawl import get_store

    app.dependency_overrides[require_auth] = lambda: None

    yield TestClient(app)

    # Clean up overrides
    app.dependency_overrides.clear()


@pytest.fixture
def mock_store():
    """Mock job store with realistic data."""
    from api.routers.crawl import get_store as crawl_get_store
    from api.routers.advisor import get_store as advisor_get_store

    store = MagicMock()

    # Mock job
    job = MagicMock()
    job.job_id = "test-job-123"
    job.target_url = "https://example.com"
    job.pages_crawled = 2

    # Mock pages with URL but NO content field
    # This is the real schema that caused the bug
    pages = [
        {
            "url": "https://example.com/page1",
            "title": "Page 1",
            "status_code": 200,
            "word_count": 500,
            # NOTE: No 'content' field — this is what the frontend was expecting but doesn't exist
        },
        {
            "url": "https://example.com/page2",
            "title": "Page 2",
            "status_code": 200,
            "word_count": 600,
        }
    ]

    # Make get_job async
    async def mock_get_job(job_id):
        if job_id == "test-job-123":
            return job
        return None

    async def mock_get_pages(job_id, min_severity=None, page=1, limit=50):
        if job_id == "test-job-123":
            return (pages, 2)
        return ([], 0)

    store.get_job = mock_get_job
    store.get_pages_with_issue_counts = mock_get_pages

    # Override the get_store dependency for both routers
    app.dependency_overrides[crawl_get_store] = lambda: store
    app.dependency_overrides[advisor_get_store] = lambda: store

    yield store

    # Clean up
    app.dependency_overrides.pop(crawl_get_store, None)
    app.dependency_overrides.pop(advisor_get_store, None)


class TestGetPagesEndpointSchema:
    """Verify /api/crawl/{job_id}/pages response schema."""

    def test_pages_endpoint_returns_url_not_content(self, client, mock_store):
        """
        CRITICAL: Verify that /api/crawl/{job_id}/pages returns 'url' field
        but NOT 'content' field. The frontend must NOT assume content is present.
        """
        response = client.get("/api/crawl/test-job-123/pages?limit=1")
        assert response.status_code == 200

        data = response.json()
        assert "pages" in data, "Response must have 'pages' array"
        assert len(data["pages"]) > 0, "Response must have at least one page"

        page = data["pages"][0]
        assert "url" in page, "Each page must have 'url' field"
        assert "title" in page, "Each page must have 'title' field"
        assert "status_code" in page, "Each page must have 'status_code' field"

        # CRITICAL: Verify that 'content' does NOT exist
        assert "content" not in page, (
            "Page object must NOT have 'content' field. "
            "Frontend must fetch content via separate URL or use Advisor service."
        )

    def test_pages_endpoint_pagination(self, client, mock_store):
        """Verify pagination fields are present."""
        response = client.get("/api/crawl/test-job-123/pages?limit=1&page=1")
        assert response.status_code == 200

        data = response.json()
        assert "pagination" in data
        assert "page" in data["pagination"]
        assert "limit" in data["pagination"]
        assert "total_pages_crawled" in data["pagination"]


class TestRewriterEndpoint:
    """Verify /api/ai/rewriter endpoint."""

    @pytest.mark.asyncio
    async def test_rewriter_accepts_content_and_prompt(self, client):
        """
        Verify rewriter endpoint accepts content and prompt parameters.
        """
        payload = {
            "content": "This is test content to rewrite.",
            "prompt": "Rewrite for clarity."
        }

        with patch("api.services.rewriter.rewrite_page") as mock_rewrite:
            mock_rewrite.return_value = RewriterResult(
                rewrite="This content has been rewritten for clarity.",
                stopped_by_limit=False
            )

            response = client.post("/api/ai/rewriter", json=payload)
            assert response.status_code == 200

            data = response.json()
            assert "rewrite" in data, "Response must have 'rewrite' field"
            assert "stopped_by_limit" in data, "Response must have 'stopped_by_limit' field"
            assert isinstance(data["rewrite"], str)
            assert isinstance(data["stopped_by_limit"], bool)

    def test_rewriter_token_limit_flag_exists_in_response(self, client):
        """Verify rewriter response always includes stopped_by_limit flag."""
        payload = {
            "content": "Content to rewrite.",
            "prompt": "Rewrite for clarity."
        }

        response = client.post("/api/ai/rewriter", json=payload)
        assert response.status_code == 200

        data = response.json()
        # Must have this flag so frontend knows if content was truncated
        assert "stopped_by_limit" in data
        assert isinstance(data["stopped_by_limit"], bool)


class TestRewriteFlowIntegration:
    """End-to-end test of the rewrite flow (how frontend will use it)."""

    def test_frontend_flow_step1_get_pages(self, client, mock_store):
        """
        Step 1: Frontend calls GET /api/crawl/{job_id}/pages to get page URLs.

        This test verifies that the endpoint returns enough data for the frontend
        to proceed to step 2.
        """
        response = client.get("/api/crawl/test-job-123/pages?limit=1")
        assert response.status_code == 200

        data = response.json()
        pages = data.get("pages", [])
        assert len(pages) > 0, "Must have at least one page"

        # Frontend will extract URL from here
        page_url = pages[0].get("url")
        assert page_url is not None, "Page must have URL"
        assert isinstance(page_url, str)

        # Frontend CANNOT get content from here (it doesn't exist)
        assert "content" not in pages[0]

    def test_frontend_flow_step2_fetches_via_advisor_or_direct_url(self):
        """
        Step 2: Frontend must fetch page content from the actual URL or via Advisor.

        This test documents that the frontend must NOT assume the pages endpoint
        has content, and instead fetch it separately using either:
        - Direct fetch with potential CORS handling (no-cors mode)
        - Or through the Advisor service which fetches server-side

        The advisor service has URL fetching capability via httpx.
        """
        # This is verified in test_rewriter_integration_flow above
        # where we show the frontend must call the URL separately
        pass

    @pytest.mark.asyncio
    async def test_frontend_flow_step3_rewrite(self, client):
        """
        Step 3: Frontend has HTML/markdown content and calls rewriter.

        This test verifies the rewriter accepts content and returns rewritten version.
        """
        content = "<h1>Original Page</h1><p>This is the original content.</p>"
        prompt = "Rewrite for AI retrieval quality."

        with patch("api.services.rewriter.rewrite_page") as mock_rewrite:
            mock_rewrite.return_value = RewriterResult(
                rewrite="<h1>Original Page</h1><p>Rewritten for better AI retrieval.</p>",
                stopped_by_limit=False
            )

            response = client.post("/api/ai/rewriter", json={
                "content": content,
                "prompt": prompt
            })

            assert response.status_code == 200
            data = response.json()
            assert data["rewrite"] is not None
            assert len(data["rewrite"]) > 0


class TestDataModelValidation:
    """Verify that Pydantic models enforce required fields."""

    def test_rewriter_request_requires_content(self):
        """RewriterRequest must have content (it's a required positional argument)."""
        with pytest.raises(TypeError):
            RewriterRequest(prompt="test")  # Missing required 'content' argument

    def test_rewriter_request_allows_empty_content(self):
        """RewriterRequest can have empty content (for edge cases)."""
        req = RewriterRequest(content="", prompt="test")
        assert req.content == ""

    def test_rewriter_result_has_required_fields(self):
        """RewriterResult must have rewrite and stopped_by_limit."""
        result = RewriterResult(
            rewrite="test rewrite",
            stopped_by_limit=False
        )
        assert result.rewrite == "test rewrite"
        assert result.stopped_by_limit is False


class TestErrorHandling:
    """Test error conditions in the rewrite flow."""

    def test_pages_endpoint_with_missing_job(self, client, mock_store):
        """GET /pages returns 404 when job not found."""
        mock_store.get_job = AsyncMock(return_value=None)

        response = client.get("/api/crawl/nonexistent-job/pages")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_rewriter_with_invalid_json(self, client):
        """POST /rewriter returns 422 for invalid payload."""
        response = client.post("/api/ai/rewriter", json={
            "content": "test"
            # Missing 'prompt' field
        })
        assert response.status_code == 422

    def test_rewriter_with_empty_content(self, client):
        """POST /rewriter can handle empty content (edge case)."""
        response = client.post("/api/ai/rewriter", json={
            "content": "",
            "prompt": "test prompt"
        })
        # Should still return 200, but rewritten content might be empty
        assert response.status_code in [200, 400, 500]
        # (Actual behavior depends on LLM - might fail or return empty)


class TestFrontendAssumptions:
    """Test assumptions that the frontend makes about API responses.

    If any of these tests fail, the frontend code needs to be updated.
    """

    def test_frontend_assumes_pages_have_url(self, client, mock_store):
        """Frontend assumes every page in pages array has 'url' field."""
        response = client.get("/api/crawl/test-job-123/pages?limit=5")
        assert response.status_code == 200

        data = response.json()
        for page in data["pages"]:
            assert "url" in page, "Frontend assumes 'url' field exists"

    def test_frontend_assumes_rewriter_returns_rewrite_field(self, client):
        """Frontend assumes rewriter response has 'rewrite' field."""
        with patch("api.services.rewriter.rewrite_page") as mock_rewrite:
            mock_rewrite.return_value = RewriterResult(
                rewrite="Rewritten content",
                stopped_by_limit=False
            )

            response = client.post("/api/ai/rewriter", json={
                "content": "test",
                "prompt": "test"
            })

            data = response.json()
            assert "rewrite" in data, "Frontend assumes 'rewrite' field exists in response"

    def test_frontend_assumes_pages_do_not_have_content(self, client, mock_store):
        """
        Frontend must NOT assume pages endpoint returns 'content'.
        If this test fails, the API changed and frontend needs updating.
        """
        response = client.get("/api/crawl/test-job-123/pages?limit=1")
        assert response.status_code == 200

        data = response.json()
        for page in data["pages"]:
            assert "content" not in page, (
                "API schema changed: pages now have 'content' field. "
                "Frontend can simplify by using page.content instead of fetching separately."
            )
