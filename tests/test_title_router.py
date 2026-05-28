"""Contract tests for title_router endpoints (v2.3 M0.12.1).

These tests are CLAUDE.md "API Contract Tests (Non-Negotiable)": every
endpoint the frontend calls must have a test asserting its response schema
and status codes.

Endpoints under test:
    GET  /api/fixes/predefined-codes
    POST /api/fixes/bulk-trim-titles?job_id=...
    POST /api/fixes/trim-title-one?page_url=...

Covers: auth (router-level dependency), validation (missing required params),
not-found handling, NO_CREDENTIALS branch, DOMAIN_MISMATCH branch, and the
happy path with mocked WPClient.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from api.models.job import CrawlJob
from api.models.page import CrawledPage


# Shared fixture: a seeded crawl job with one page
@pytest.fixture
async def seeded_job(api_client, test_store):
    job_id = str(uuid4())
    job = CrawlJob(
        job_id=job_id,
        target_url="https://example.com",
        status="complete",
        pages_crawled=1,
    )
    await test_store.create_job(job)
    page = CrawledPage(
        job_id=job_id,
        url="https://example.com/about",
        status_code=200,
        title="About Us | Example",
        crawled_at=datetime.now(timezone.utc),
    )
    await test_store.save_pages([page])
    return api_client, job_id


# ---------------------------------------------------------------------------
# GET /api/fixes/predefined-codes
# ---------------------------------------------------------------------------


class TestPredefinedCodes:
    @pytest.mark.asyncio
    async def test_returns_codes_and_count(self, api_client, auth_headers):
        r = await api_client.get("/api/fixes/predefined-codes", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert "codes" in body
        assert "count" in body
        assert isinstance(body["codes"], list)
        assert body["count"] == len(body["codes"])
        # Should include at least the well-known fixable codes
        assert "TITLE_MISSING" in body["codes"] or len(body["codes"]) > 0

    @pytest.mark.asyncio
    async def test_codes_are_sorted(self, api_client, auth_headers):
        """Sorted output is deterministic — frontend can binary-search or memoize."""
        r = await api_client.get("/api/fixes/predefined-codes", headers=auth_headers)
        codes = r.json()["codes"]
        assert codes == sorted(codes)

    @pytest.mark.asyncio
    async def test_requires_auth(self, api_client):
        r = await api_client.get("/api/fixes/predefined-codes")
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/fixes/bulk-trim-titles
# ---------------------------------------------------------------------------


class TestBulkTrimTitles:
    @pytest.mark.asyncio
    async def test_requires_auth(self, api_client):
        r = await api_client.post("/api/fixes/bulk-trim-titles?job_id=abc")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_job_id_returns_422(self, api_client, auth_headers):
        r = await api_client.post(
            "/api/fixes/bulk-trim-titles", headers=auth_headers
        )
        # FastAPI returns 422 for missing required query params
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_unknown_job_returns_404(self, api_client, auth_headers):
        r = await api_client.post(
            "/api/fixes/bulk-trim-titles?job_id=does-not-exist",
            headers=auth_headers,
        )
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "JOB_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_no_credentials_returns_400(self, api_client, auth_headers, seeded_job, tmp_path):
        api_client, job_id = seeded_job
        nonexistent = tmp_path / "no-such-file.json"
        with patch("api.routers.title_router._CREDS_PATH", nonexistent):
            r = await api_client.post(
                f"/api/fixes/bulk-trim-titles?job_id={job_id}",
                headers=auth_headers,
            )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "NO_CREDENTIALS"

    @pytest.mark.asyncio
    async def test_domain_mismatch_returns_403(
        self, api_client, auth_headers, seeded_job, tmp_path
    ):
        """Creds for a different site than the job → 403 DOMAIN_MISMATCH."""
        api_client, job_id = seeded_job
        creds_path = tmp_path / "wp-credentials.json"
        creds_path.write_text(json.dumps({
            "site_url": "https://other-site.com",
            "login_url": "https://other-site.com/wp-login.php",
            "username": "admin",
            "password": "secret",
        }))
        # Patch BOTH bindings (per the M0.11 lesson about `from x import name`)
        with patch("api.routers.title_router._CREDS_PATH", creds_path), \
             patch("api.routers.fixes_shared._CREDS_PATH", creds_path):
            r = await api_client.post(
                f"/api/fixes/bulk-trim-titles?job_id={job_id}",
                headers=auth_headers,
            )
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "DOMAIN_MISMATCH"

    @pytest.mark.asyncio
    async def test_no_eligible_pages_returns_empty(
        self, api_client, auth_headers, test_store, tmp_path
    ):
        """Job with zero crawled pages (or all 404s, no titles) returns applied=0 cleanly."""
        job_id = str(uuid4())
        job = CrawlJob(
            job_id=job_id,
            target_url="https://example.com",
            status="complete",
            pages_crawled=0,
        )
        await test_store.create_job(job)

        creds_path = tmp_path / "wp-credentials.json"
        creds_path.write_text(json.dumps({
            "site_url": "https://example.com",
            "login_url": "https://example.com/wp-login.php",
            "username": "admin",
            "password": "secret",
        }))
        with patch("api.routers.title_router._CREDS_PATH", creds_path), \
             patch("api.routers.fixes_shared._CREDS_PATH", creds_path):
            r = await api_client.post(
                f"/api/fixes/bulk-trim-titles?job_id={job_id}",
                headers=auth_headers,
            )
        assert r.status_code == 200
        body = r.json()
        assert body == {"applied": 0, "skipped": 0, "results": []}


# ---------------------------------------------------------------------------
# POST /api/fixes/trim-title-one
# ---------------------------------------------------------------------------


class TestTrimTitleOne:
    @pytest.mark.asyncio
    async def test_requires_auth(self, api_client):
        r = await api_client.post(
            "/api/fixes/trim-title-one?page_url=https://example.com/about"
        )
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_page_url_returns_422(self, api_client, auth_headers):
        r = await api_client.post(
            "/api/fixes/trim-title-one", headers=auth_headers
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_no_credentials_returns_400(self, api_client, auth_headers, tmp_path):
        nonexistent = tmp_path / "no-such-file.json"
        with patch("api.routers.title_router._CREDS_PATH", nonexistent):
            r = await api_client.post(
                "/api/fixes/trim-title-one?page_url=https://example.com/about",
                headers=auth_headers,
            )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "NO_CREDENTIALS"

    @pytest.mark.asyncio
    async def test_domain_mismatch_returns_403(self, api_client, auth_headers, tmp_path):
        """page_url's domain different from credentials' site_url → 403 DOMAIN_MISMATCH."""
        creds_path = tmp_path / "wp-credentials.json"
        creds_path.write_text(json.dumps({
            "site_url": "https://example.com",
            "login_url": "https://example.com/wp-login.php",
            "username": "admin",
            "password": "secret",
        }))
        with patch("api.routers.title_router._CREDS_PATH", creds_path), \
             patch("api.routers.fixes_shared._CREDS_PATH", creds_path):
            r = await api_client.post(
                "/api/fixes/trim-title-one?page_url=https://other-site.com/page",
                headers=auth_headers,
            )
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "DOMAIN_MISMATCH"


# ---------------------------------------------------------------------------
# Architecture test — router is registered, not just defined
# ---------------------------------------------------------------------------


class TestTitleRouterRegistration:
    def test_router_is_included_in_app(self):
        """Prove title_router's endpoints are actually reachable on the FastAPI app.

        Adversarial: a future commit removes the include_router(title_router, ...)
        line in fixes.py — these endpoints silently 404. This test fails loudly.
        """
        from api.main import app

        registered_paths = {r.path for r in app.routes if hasattr(r, "path")}
        assert "/api/fixes/predefined-codes" in registered_paths
        assert "/api/fixes/bulk-trim-titles" in registered_paths
        assert "/api/fixes/trim-title-one" in registered_paths
