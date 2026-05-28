"""Contract tests for image_router endpoints (v2.3 M0.12.3).

Covers all 8 endpoints. Deep WP-workflow tests live with the service layer
(tests/test_image_optimization.py, tests/test_wp_fixer.py); this file focuses
on the HTTP contract: routes registered, auth required, validation correct,
NO_CREDENTIALS / DOMAIN_MISMATCH branches reached.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import patch
from uuid import uuid4

import pytest

from api.models.job import CrawlJob


@pytest.fixture
async def seeded_job(api_client, test_store):
    job_id = str(uuid4())
    await test_store.create_job(CrawlJob(
        job_id=job_id, target_url="https://example.com",
        status="complete", pages_crawled=1,
    ))
    return api_client, job_id


@pytest.fixture
def matching_creds(tmp_path):
    p = tmp_path / "wp-credentials.json"
    p.write_text(json.dumps({
        "site_url": "https://example.com",
        "login_url": "https://example.com/wp-login.php",
        "username": "admin",
        "password": "secret",
    }))
    return p


@pytest.fixture
def mismatched_creds(tmp_path):
    p = tmp_path / "wp-credentials.json"
    p.write_text(json.dumps({
        "site_url": "https://other-site.com",
        "login_url": "https://other-site.com/wp-login.php",
        "username": "admin",
        "password": "secret",
    }))
    return p


# ---------------------------------------------------------------------------
# Auth — every endpoint requires bearer token
# ---------------------------------------------------------------------------


class TestImageRouterAuth:
    @pytest.mark.parametrize("method,path", [
        ("get",  "/api/fixes/image-info?image_url=https://x/y.jpg"),
        ("post", "/api/fixes/update-image-meta?image_url=https://x/y.jpg"),
        ("post", "/api/fixes/refresh-image-from-wp?image_url=https://x/y.jpg&job_id=x"),
        ("post", "/api/fixes/optimize-image?job_id=x&image_url=https://x/y.jpg"),
        ("post", "/api/fixes/optimize-existing-preview?job_id=x&image_url=https://x/y.jpg"),
        ("post", "/api/fixes/optimize-existing"),
        ("post", "/api/fixes/optimize-upload-preview"),
        ("post", "/api/fixes/optimize-upload"),
    ])
    @pytest.mark.asyncio
    async def test_endpoint_requires_auth(self, api_client, method, path):
        if method == "post":
            r = await api_client.post(path)
        else:
            r = await api_client.get(path)
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestImageRouterValidation:
    @pytest.mark.asyncio
    async def test_image_info_missing_url_returns_422(self, api_client, auth_headers):
        r = await api_client.get("/api/fixes/image-info", headers=auth_headers)
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_optimize_image_invalid_width_returns_422(self, api_client, auth_headers):
        r = await api_client.post(
            "/api/fixes/optimize-image?job_id=x&image_url=https://x/y.jpg&target_width=50",
            headers=auth_headers,
        )
        assert r.status_code == 422  # ge=100 violated

    @pytest.mark.asyncio
    async def test_optimize_existing_missing_body_returns_422(self, api_client, auth_headers):
        r = await api_client.post("/api/fixes/optimize-existing", headers=auth_headers)
        assert r.status_code == 422  # Pydantic body required

    @pytest.mark.asyncio
    async def test_optimize_upload_preview_missing_file_returns_422(self, api_client, auth_headers):
        r = await api_client.post("/api/fixes/optimize-upload-preview", headers=auth_headers)
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# NO_CREDENTIALS branch
# ---------------------------------------------------------------------------


class TestImageRouterNoCredentials:
    @pytest.mark.asyncio
    async def test_image_info_no_credentials(self, api_client, auth_headers, tmp_path):
        nonexistent = tmp_path / "missing.json"
        with patch("api.routers.image_router._CREDS_PATH", nonexistent):
            r = await api_client.get(
                "/api/fixes/image-info?image_url=https://example.com/img.jpg",
                headers=auth_headers,
            )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "NO_CREDENTIALS"

    @pytest.mark.asyncio
    async def test_optimize_existing_no_credentials(
        self, api_client, auth_headers, seeded_job, tmp_path
    ):
        api_client, job_id = seeded_job
        nonexistent = tmp_path / "missing.json"
        with patch("api.routers.image_router._CREDS_PATH", nonexistent):
            r = await api_client.post(
                "/api/fixes/optimize-existing",
                json={
                    "job_id": job_id,
                    "image_url": "https://example.com/img.jpg",
                },
                headers=auth_headers,
            )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "NO_CREDENTIALS"


# ---------------------------------------------------------------------------
# DOMAIN_MISMATCH branch
# ---------------------------------------------------------------------------


class TestImageRouterDomainMismatch:
    @pytest.mark.asyncio
    async def test_image_info_domain_mismatch(
        self, api_client, auth_headers, matching_creds
    ):
        """Creds say example.com; image URL on other-site.com — 403."""
        with patch("api.routers.image_router._CREDS_PATH", matching_creds), \
             patch("api.routers.fixes_shared._CREDS_PATH", matching_creds):
            r = await api_client.get(
                "/api/fixes/image-info?image_url=https://other-site.com/img.jpg",
                headers=auth_headers,
            )
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "DOMAIN_MISMATCH"

    @pytest.mark.asyncio
    async def test_refresh_image_domain_mismatch(
        self, api_client, auth_headers, seeded_job, mismatched_creds
    ):
        """Creds for other-site.com; job target is example.com — 403."""
        api_client, job_id = seeded_job
        with patch("api.routers.image_router._CREDS_PATH", mismatched_creds), \
             patch("api.routers.fixes_shared._CREDS_PATH", mismatched_creds):
            r = await api_client.post(
                f"/api/fixes/refresh-image-from-wp?image_url=https://example.com/img.jpg&job_id={job_id}",
                headers=auth_headers,
            )
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "DOMAIN_MISMATCH"


# ---------------------------------------------------------------------------
# Not-found branch
# ---------------------------------------------------------------------------


class TestImageRouterNotFound:
    @pytest.mark.asyncio
    async def test_optimize_image_unknown_job(self, api_client, auth_headers):
        r = await api_client.post(
            "/api/fixes/optimize-image?job_id=nope&image_url=https://x/y.jpg",
            headers=auth_headers,
        )
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "JOB_NOT_FOUND"


# ---------------------------------------------------------------------------
# Upload-preview happy path with a tiny test PNG
# ---------------------------------------------------------------------------


class TestImageRouterUploadPreview:
    @pytest.mark.asyncio
    async def test_invalid_width_returns_422(self, api_client, auth_headers):
        files = {"file": ("test.png", BytesIO(b"\x89PNG\r\n\x1a\n"), "image/png")}
        r = await api_client.post(
            "/api/fixes/optimize-upload-preview",
            files=files,
            data={"target_width": "50"},  # below ge=100
            headers=auth_headers,
        )
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "INVALID_WIDTH"


# ---------------------------------------------------------------------------
# Architecture — all 8 routes registered
# ---------------------------------------------------------------------------


class TestImageRouterRegistration:
    def test_all_eight_endpoints_registered(self):
        from api.main import app
        registered = {r.path for r in app.routes if hasattr(r, "path")}
        for path in [
            "/api/fixes/image-info",
            "/api/fixes/update-image-meta",
            "/api/fixes/refresh-image-from-wp",
            "/api/fixes/optimize-image",
            "/api/fixes/optimize-existing-preview",
            "/api/fixes/optimize-existing",
            "/api/fixes/optimize-upload-preview",
            "/api/fixes/optimize-upload",
        ]:
            assert path in registered, f"{path} not registered on app"
