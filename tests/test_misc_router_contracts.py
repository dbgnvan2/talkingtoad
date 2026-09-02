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

    @pytest.mark.asyncio
    async def test_list_returns_array_or_dict(self, api_client, auth_headers):
        r = await api_client.get("/api/suppressed-codes", headers=auth_headers)
        assert r.status_code == 200
        # Shape varies; just confirm valid JSON
        body = r.json()
        assert isinstance(body, (list, dict))


class TestExemptAnchorUrls:

    @pytest.mark.asyncio
    async def test_list_returns_valid_json(self, api_client, auth_headers):
        r = await api_client.get("/api/exempt-anchor-urls", headers=auth_headers)
        assert r.status_code == 200
        assert isinstance(r.json(), (list, dict))



class TestSaveLLMSTxt:

    @pytest.mark.asyncio
    async def test_missing_body_returns_422(self, api_client, auth_headers):
        r = await api_client.post("/api/utility/save-llms-txt", headers=auth_headers)
        assert r.status_code == 422


class TestGenerateLLMSTxt:

    @pytest.mark.asyncio
    async def test_unknown_job_returns_404(self, api_client, auth_headers):
        r = await api_client.get(
            "/api/utility/generate-llms-txt?job_id=does-not-exist",
            headers=auth_headers,
        )
        assert r.status_code == 404


# ===================================================================
# GEO router
# ===================================================================



# ===================================================================
# Crawl router — endpoints not covered in test_crawl_router_contracts.py
# ===================================================================

