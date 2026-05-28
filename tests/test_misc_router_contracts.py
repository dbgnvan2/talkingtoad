"""Contract test backfill for utility, verified, ai routers (v2.5 M8).

Covers endpoints not exercised by the existing test files:

utility.py:
  - /api/suppressed-codes (GET, POST, DELETE)
  - /api/exempt-anchor-urls (GET, POST, DELETE)
  - /api/ignored-image-patterns (GET, POST, DELETE)
  - /api/utility/save-llms-txt

verified.py (/api/verified-links):
  - GET, POST, DELETE

ai.py:
  - /api/ai/page-advisor, /api/ai/site-advisor
  - /api/ai/image/analyze-geo, /api/ai/image/apply-geo-metadata

Auth, validation, response-shape coverage. Deep behaviour lives in the
service-layer test files.
"""

from __future__ import annotations

import pytest


# ===================================================================
# AI router auth
# ===================================================================


class TestAIRouterAuth:
    @pytest.mark.parametrize("method,path", [
        ("post", "/api/ai/analyze"),
        ("get",  "/api/ai/test"),
        ("post", "/api/ai/page-advisor"),
        ("post", "/api/ai/site-advisor"),
        ("post", "/api/ai/image/analyze-geo"),
        ("post", "/api/ai/image/apply-geo-metadata"),
    ])
    @pytest.mark.asyncio
    async def test_endpoint_requires_auth(self, api_client, method, path):
        if method == "post":
            r = await api_client.post(path)
        else:
            r = await api_client.get(path)
        assert r.status_code == 401


class TestAIRouterValidation:
    @pytest.mark.asyncio
    async def test_analyze_missing_body_rejected(self, api_client, auth_headers):
        r = await api_client.post("/api/ai/analyze", headers=auth_headers)
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_page_advisor_missing_body_rejected(self, api_client, auth_headers):
        r = await api_client.post("/api/ai/page-advisor", headers=auth_headers)
        assert r.status_code == 422


# ===================================================================
# Verified-links router
# ===================================================================


class TestVerifiedLinksAuth:
    @pytest.mark.parametrize("method,path", [
        ("get",    "/api/verified-links"),
        ("post",   "/api/verified-links"),
        ("delete", "/api/verified-links?url=https://example.com/x"),
    ])
    @pytest.mark.asyncio
    async def test_endpoint_requires_auth(self, api_client, method, path):
        if method == "post":
            r = await api_client.post(path)
        elif method == "delete":
            r = await api_client.delete(path)
        else:
            r = await api_client.get(path)
        assert r.status_code == 401


class TestVerifiedLinksCRUD:
    @pytest.mark.asyncio
    async def test_list_returns_array(self, api_client, auth_headers):
        r = await api_client.get("/api/verified-links", headers=auth_headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    @pytest.mark.asyncio
    async def test_post_empty_url_returns_400(self, api_client, auth_headers):
        r = await api_client.post(
            "/api/verified-links",
            json={"url": ""},
            headers=auth_headers,
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "INVALID_URL"

    @pytest.mark.asyncio
    async def test_post_whitespace_url_returns_400(self, api_client, auth_headers):
        """Adversarial: ' ' stripped becomes '' — must also reject."""
        r = await api_client.post(
            "/api/verified-links",
            json={"url": "   "},
            headers=auth_headers,
        )
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_add_then_list_then_delete_roundtrip(self, api_client, auth_headers):
        url = "https://example.com/verified-test-roundtrip"

        # Add
        r = await api_client.post(
            "/api/verified-links",
            json={"url": url},
            headers=auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["url"] == url
        assert "verified_at" in body

        # List should include it
        r = await api_client.get("/api/verified-links", headers=auth_headers)
        urls = {item.get("url") for item in r.json()}
        assert url in urls

        # Delete
        r = await api_client.delete(
            f"/api/verified-links?url={url}",
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["removed"] is True

        # Should no longer be listed
        r = await api_client.get("/api/verified-links", headers=auth_headers)
        urls = {item.get("url") for item in r.json()}
        assert url not in urls


# ===================================================================
# Utility router — config-CRUD endpoints
# ===================================================================


class TestSuppressedCodes:
    @pytest.mark.parametrize("method,path", [
        ("get",    "/api/suppressed-codes"),
        ("post",   "/api/suppressed-codes?code=TEST_CODE"),
        ("delete", "/api/suppressed-codes?code=TEST_CODE"),
    ])
    @pytest.mark.asyncio
    async def test_endpoint_requires_auth(self, api_client, method, path):
        if method == "post":
            r = await api_client.post(path)
        elif method == "delete":
            r = await api_client.delete(path)
        else:
            r = await api_client.get(path)
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_list_returns_array_or_dict(self, api_client, auth_headers):
        r = await api_client.get("/api/suppressed-codes", headers=auth_headers)
        assert r.status_code == 200
        # Shape varies; just confirm valid JSON
        body = r.json()
        assert isinstance(body, (list, dict))


class TestExemptAnchorUrls:
    @pytest.mark.parametrize("method", ["get", "post", "delete"])
    @pytest.mark.asyncio
    async def test_endpoint_requires_auth(self, api_client, method):
        path = "/api/exempt-anchor-urls"
        if method == "post":
            r = await api_client.post(f"{path}?url=https://example.com/x")
        elif method == "delete":
            r = await api_client.delete(f"{path}?url=https://example.com/x")
        else:
            r = await api_client.get(path)
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_list_returns_valid_json(self, api_client, auth_headers):
        r = await api_client.get("/api/exempt-anchor-urls", headers=auth_headers)
        assert r.status_code == 200
        assert isinstance(r.json(), (list, dict))


class TestIgnoredImagePatterns:
    @pytest.mark.parametrize("method", ["get", "post", "delete"])
    @pytest.mark.asyncio
    async def test_endpoint_requires_auth(self, api_client, method):
        path = "/api/ignored-image-patterns"
        if method == "post":
            r = await api_client.post(f"{path}?pattern=/icon.svg")
        elif method == "delete":
            r = await api_client.delete(f"{path}?pattern=/icon.svg")
        else:
            r = await api_client.get(path)
        assert r.status_code == 401


class TestSaveLLMSTxt:
    @pytest.mark.asyncio
    async def test_requires_auth(self, api_client):
        r = await api_client.post("/api/utility/save-llms-txt")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_body_returns_422(self, api_client, auth_headers):
        r = await api_client.post("/api/utility/save-llms-txt", headers=auth_headers)
        assert r.status_code == 422
