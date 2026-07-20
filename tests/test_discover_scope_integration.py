"""
API contract tests for the partial-scan endpoints.

The discovery logic is unit-tested in test_content_discovery.py; here we assert
the endpoint contract (routing, auth, validation, response passthrough) and the
/start content_scope plumbing. Discovery/resolution are patched so no real HTTP
is made.

Spec:  docs/functional-specification.md (Scan content-type scoping)
"""

from unittest.mock import AsyncMock, patch

import pytest


_REST_PAYLOAD = {
    "is_wordpress": True,
    "discovery_tier": "rest",
    "types": [
        {"key": "page", "label": "Pages", "rest_base": "pages", "count": 14},
        {"key": "post", "label": "Posts", "rest_base": "posts", "count": 212},
        {"key": "event", "label": "Events", "rest_base": "events", "count": 30},
    ],
    "categories": [{"id": 7, "name": "Programs", "count": 41}],
    "category_scope_supported": True,
    "notes": "",
}
_SITEMAP_PAYLOAD = {
    "is_wordpress": True,
    "discovery_tier": "sitemap",
    "types": [
        {"key": "page", "label": "Pages", "rest_base": None, "count": 8},
        {"key": "post", "label": "Posts", "rest_base": None, "count": 40},
    ],
    "categories": [],
    "category_scope_supported": False,
    "notes": "Content types were read from the site's sitemap.",
}
_NONE_PAYLOAD = {
    "is_wordpress": False,
    "discovery_tier": "none",
    "types": [],
    "categories": [],
    "category_scope_supported": False,
    "notes": "This site doesn't expose a WordPress REST API or a typed sitemap.",
}


class TestDiscoverScopeEndpoint:
    async def test_discover_scope_rest(self, api_client, auth_headers):
        with patch("api.routers.crawl.discover_scope", new=AsyncMock(return_value=_REST_PAYLOAD)):
            r = await api_client.post(
                "/api/crawl/discover-scope",
                json={"target_url": "example.com"},
                headers=auth_headers,
            )
        assert r.status_code == 200
        data = r.json()
        assert data["is_wordpress"] is True
        assert data["discovery_tier"] == "rest"
        assert {t["key"] for t in data["types"]} == {"page", "post", "event"}
        assert all("count" in t for t in data["types"])
        assert data["category_scope_supported"] is True
        assert data["categories"][0]["name"] == "Programs"

    async def test_discover_scope_sitemap(self, api_client, auth_headers):
        with patch("api.routers.crawl.discover_scope", new=AsyncMock(return_value=_SITEMAP_PAYLOAD)):
            r = await api_client.post(
                "/api/crawl/discover-scope",
                json={"target_url": "example.com"},
                headers=auth_headers,
            )
        assert r.status_code == 200
        data = r.json()
        assert data["discovery_tier"] == "sitemap"
        assert data["category_scope_supported"] is False

    async def test_discover_scope_none(self, api_client, auth_headers):
        with patch("api.routers.crawl.discover_scope", new=AsyncMock(return_value=_NONE_PAYLOAD)):
            r = await api_client.post(
                "/api/crawl/discover-scope",
                json={"target_url": "example.com"},
                headers=auth_headers,
            )
        assert r.status_code == 200
        data = r.json()
        assert data["discovery_tier"] == "none"
        assert data["types"] == []
        assert data["notes"]

    async def test_discover_scope_requires_auth(self, api_client):
        r = await api_client.post("/api/crawl/discover-scope", json={"target_url": "example.com"})
        assert r.status_code == 401

    async def test_discover_scope_invalid_url(self, api_client, auth_headers):
        r = await api_client.post(
            "/api/crawl/discover-scope",
            json={"target_url": "not-a-url"},
            headers=auth_headers,
        )
        assert r.status_code == 422


class TestStartWithContentScope:
    async def test_start_accepts_content_scope(self, api_client, auth_headers, test_store):
        """A partial scan resolves the selection to an allowlist and persists the
        content_scope on the job."""
        resolved = {"https://example.com/about", "https://example.com/contact"}
        with patch("api.routers.crawl._run_crawl_background", new_callable=AsyncMock), \
             patch("api.routers.crawl.resolve_scope_urls",
                   new=AsyncMock(return_value=(resolved, []))):
            r = await api_client.post(
                "/api/crawl/start",
                json={
                    "target_url": "example.com",
                    "settings": {"content_scope": {"mode": "types", "type_keys": ["page"], "category_ids": []}},
                },
                headers=auth_headers,
            )
        assert r.status_code == 202
        job = await test_store.get_job(r.json()["job_id"])
        assert job.settings.content_scope.mode == "types"
        assert job.settings.content_scope.type_keys == ["page"]

    async def test_start_empty_selection_rejected(self, api_client, auth_headers):
        r = await api_client.post(
            "/api/crawl/start",
            json={
                "target_url": "example.com",
                "settings": {"content_scope": {"mode": "types", "type_keys": [], "category_ids": []}},
            },
            headers=auth_headers,
        )
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "INVALID_SCOPE"

    async def test_start_unresolvable_scope_rejected(self, api_client, auth_headers):
        with patch("api.routers.crawl.resolve_scope_urls", new=AsyncMock(return_value=(set(), []))):
            r = await api_client.post(
                "/api/crawl/start",
                json={
                    "target_url": "example.com",
                    "settings": {"content_scope": {"mode": "types", "type_keys": ["page"], "category_ids": []}},
                },
                headers=auth_headers,
            )
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "SCOPE_EMPTY"

    async def test_start_full_mode_unaffected(self, api_client, auth_headers):
        """No content_scope → default full crawl; resolve_scope_urls is never called."""
        with patch("api.routers.crawl._run_crawl_background", new_callable=AsyncMock), \
             patch("api.routers.crawl.resolve_scope_urls", new_callable=AsyncMock) as mock_resolve:
            r = await api_client.post(
                "/api/crawl/start",
                json={"target_url": "example.com"},
                headers=auth_headers,
            )
        assert r.status_code == 202
        mock_resolve.assert_not_called()
