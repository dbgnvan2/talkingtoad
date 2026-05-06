"""
Integration tests for POST /api/ai/rewrite-url endpoint.

Contract: Endpoint accepts URL + prompt, fetches page, rewrites it, returns result.

Spec: /Users/davemini2/.claude/plans/moonlit-beaming-thacker.md
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient

from api.main import app
from api.models.advisor import RewriterResult


@pytest.fixture
def client(monkeypatch):
    """FastAPI test client with auth disabled."""
    monkeypatch.setenv("AUTH_TOKEN", "")
    from api.services.auth import require_auth
    app.dependency_overrides[require_auth] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestRewriteUrlEndpoint:
    """Test POST /api/ai/rewrite-url endpoint."""

    def test_endpoint_exists(self, client):
        """Verify endpoint is registered and accepts POST requests."""
        # This will fail with 422 due to missing body, but proves endpoint exists
        response = client.post("/api/ai/rewrite-url", json={})
        # Should be validation error (422) not 404
        assert response.status_code in [422, 400], f"Expected validation error, got {response.status_code}"

    def test_endpoint_requires_url_and_prompt(self, client):
        """Endpoint must have both url and prompt fields."""
        # Missing url
        response = client.post("/api/ai/rewrite-url", json={"prompt": "test"})
        assert response.status_code == 422

        # Missing prompt
        response = client.post("/api/ai/rewrite-url", json={"url": "http://example.com"})
        assert response.status_code == 422

        # Both present should at least not fail on validation
        response = client.post(
            "/api/ai/rewrite-url",
            json={"url": "http://example.com", "prompt": "test prompt"}
        )
        # Will fail on fetch, but not on validation
        assert response.status_code != 422

    def test_rewrite_url_response_schema(self, client):
        """Response must have rewrite and stopped_by_limit fields."""
        with patch("api.services.advisor._fetch_page") as mock_fetch:
            with patch("api.routers.advisor.rewrite_page") as mock_rewrite:
                mock_fetch.return_value = "<h1>Test</h1><p>Content</p>"
                mock_rewrite = AsyncMock(return_value=RewriterResult(
                    rewrite="Rewritten content here",
                    stopped_by_limit=False
                ))

                with patch("api.routers.advisor.rewrite_page", mock_rewrite):
                    response = client.post(
                        "/api/ai/rewrite-url",
                        json={"url": "http://example.com/page", "prompt": "Rewrite this"}
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert "rewrite" in data, "Response missing 'rewrite' field"
                    assert "stopped_by_limit" in data, "Response missing 'stopped_by_limit' field"
                    assert isinstance(data["rewrite"], str)
                    assert isinstance(data["stopped_by_limit"], bool)

    def test_rewrite_url_fetches_page(self, client):
        """Endpoint must fetch the provided URL."""
        with patch("api.services.advisor._fetch_page") as mock_fetch:
            with patch("api.routers.advisor.rewrite_page") as mock_rewrite:
                mock_fetch.return_value = "<h1>Original</h1>"
                mock_rewrite = AsyncMock(return_value=RewriterResult(
                    rewrite="Rewritten",
                    stopped_by_limit=False
                ))

                with patch("api.routers.advisor.rewrite_page", mock_rewrite):
                    client.post(
                        "/api/ai/rewrite-url",
                        json={"url": "http://example.com/test", "prompt": "prompt"}
                    )

                    # Verify _fetch_page was called with the URL
                    mock_fetch.assert_called_once_with("http://example.com/test")

    def test_rewrite_url_passes_prompt_to_rewriter(self, client):
        """Endpoint must pass the prompt to the rewriter."""
        with patch("api.services.advisor._fetch_page") as mock_fetch:
            with patch("api.routers.advisor.rewrite_page") as mock_rewrite:
                mock_fetch.return_value = "<p>Content</p>"
                mock_rewrite = AsyncMock(return_value=RewriterResult(
                    rewrite="Done",
                    stopped_by_limit=False
                ))

                test_prompt = "Rewrite for GEO optimization"
                with patch("api.routers.advisor.rewrite_page", mock_rewrite):
                    client.post(
                        "/api/ai/rewrite-url",
                        json={"url": "http://example.com", "prompt": test_prompt}
                    )

                    # Verify rewrite_page was called with correct prompt
                    call_args = mock_rewrite.call_args
                    assert call_args is not None
                    rewriter_request = call_args[0][0]
                    assert rewriter_request.prompt == test_prompt

    def test_rewrite_url_handles_fetch_error(self, client):
        """Endpoint must return 500 if page fetch fails."""
        with patch("api.services.advisor._fetch_page") as mock_fetch:
            mock_fetch.side_effect = RuntimeError("URL not reachable")

            response = client.post(
                "/api/ai/rewrite-url",
                json={"url": "http://example.com", "prompt": "test"}
            )

            assert response.status_code == 500
            response_json = response.json()
            # The response should contain an error message somewhere
            # It may have "detail" (string or dict), "error" (dict), or "message"
            error_found = False

            if "detail" in response_json:
                detail = response_json["detail"]
                if isinstance(detail, dict) and "message" in detail:
                    error_found = "Rewriting failed" in detail["message"]
                elif isinstance(detail, str):
                    error_found = "Rewriting failed" in detail
            elif "error" in response_json:
                error = response_json["error"]
                if isinstance(error, dict) and "message" in error:
                    error_found = "Rewriting failed" in error["message"]
                elif isinstance(error, str):
                    error_found = "Rewriting failed" in error
            elif "message" in response_json:
                error_found = "Rewriting failed" in response_json["message"]

            assert error_found, f"Expected error message in response, got: {response_json}"

    def test_rewrite_url_handles_rewriter_error(self, client):
        """Endpoint must return 500 if rewriter fails."""
        with patch("api.services.advisor._fetch_page") as mock_fetch:
            with patch("api.routers.advisor.rewrite_page") as mock_rewrite:
                mock_fetch.return_value = "<p>Content</p>"
                mock_rewrite = AsyncMock(side_effect=RuntimeError("LLM API error"))

                with patch("api.routers.advisor.rewrite_page", mock_rewrite):
                    response = client.post(
                        "/api/ai/rewrite-url",
                        json={"url": "http://example.com", "prompt": "test"}
                    )

                    assert response.status_code == 500

    def test_rewrite_url_token_limit_flag(self, client):
        """Endpoint must return stopped_by_limit flag from rewriter."""
        with patch("api.services.advisor._fetch_page") as mock_fetch:
            with patch("api.routers.advisor.rewrite_page") as mock_rewrite:
                mock_fetch.return_value = "<p>Very long content</p>"
                mock_rewrite = AsyncMock(return_value=RewriterResult(
                    rewrite="Truncated...",
                    stopped_by_limit=True
                ))

                with patch("api.routers.advisor.rewrite_page", mock_rewrite):
                    response = client.post(
                        "/api/ai/rewrite-url",
                        json={"url": "http://example.com", "prompt": "test"}
                    )

                    data = response.json()
                    assert data["stopped_by_limit"] is True


class TestRewriteUrlFrontendContract:
    """Test assumptions the frontend makes about /api/ai/rewrite-url."""

    def test_frontend_assumes_rewrite_field_in_response(self, client):
        """Frontend assumes response has 'rewrite' field containing rewritten text."""
        with patch("api.services.advisor._fetch_page") as mock_fetch:
            with patch("api.routers.advisor.rewrite_page") as mock_rewrite:
                mock_fetch.return_value = "<p>Original</p>"
                expected_rewrite = "This is the rewritten content"
                mock_rewrite = AsyncMock(return_value=RewriterResult(
                    rewrite=expected_rewrite,
                    stopped_by_limit=False
                ))

                with patch("api.routers.advisor.rewrite_page", mock_rewrite):
                    response = client.post(
                        "/api/ai/rewrite-url",
                        json={"url": "http://example.com", "prompt": "test"}
                    )

                    data = response.json()
                    assert data["rewrite"] == expected_rewrite

    def test_frontend_assumes_stopped_by_limit_is_boolean(self, client):
        """Frontend assumes stopped_by_limit is a boolean, not string or int."""
        with patch("api.services.advisor._fetch_page") as mock_fetch:
            with patch("api.services.rewriter.rewrite_page") as mock_rewrite:
                mock_fetch.return_value = "<p>Content</p>"
                mock_rewrite.return_value = RewriterResult(
                    rewrite="Result",
                    stopped_by_limit=False
                )

                response = client.post(
                    "/api/ai/rewrite-url",
                    json={"url": "http://example.com", "prompt": "test"}
                )

                data = response.json()
                assert isinstance(data["stopped_by_limit"], bool), (
                    f"stopped_by_limit must be boolean, got {type(data['stopped_by_limit'])}"
                )
