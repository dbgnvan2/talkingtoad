"""Contract tests for orphaned_media_router (v2.3 M0.12.4)."""

from __future__ import annotations

import json
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


class TestOrphanedMediaEndpoint:
    @pytest.mark.asyncio
    async def test_requires_auth(self, api_client):
        r = await api_client.get(f"/api/fixes/orphaned-media/{uuid4()}")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_uuid_returns_422(self, api_client, auth_headers):
        r = await api_client.get(
            "/api/fixes/orphaned-media/not-a-uuid",
            headers=auth_headers,
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_unknown_job_returns_404(self, api_client, auth_headers):
        r = await api_client.get(
            f"/api/fixes/orphaned-media/{uuid4()}",
            headers=auth_headers,
        )
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "JOB_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_no_credentials_returns_400(
        self, api_client, auth_headers, seeded_job, tmp_path
    ):
        api_client, job_id = seeded_job
        nonexistent = tmp_path / "missing.json"
        with patch("api.routers.orphaned_media_router._CREDS_PATH", nonexistent):
            r = await api_client.get(
                f"/api/fixes/orphaned-media/{job_id}",
                headers=auth_headers,
            )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "NO_CREDENTIALS"

    @pytest.mark.asyncio
    async def test_domain_mismatch_returns_403(
        self, api_client, auth_headers, seeded_job, tmp_path
    ):
        api_client, job_id = seeded_job
        creds_path = tmp_path / "wp-credentials.json"
        creds_path.write_text(json.dumps({
            "site_url": "https://other-site.com",
            "login_url": "https://other-site.com/wp-login.php",
            "username": "admin",
            "password": "secret",
        }))
        with patch("api.routers.orphaned_media_router._CREDS_PATH", creds_path), \
             patch("api.routers.fixes_shared._CREDS_PATH", creds_path):
            r = await api_client.get(
                f"/api/fixes/orphaned-media/{job_id}",
                headers=auth_headers,
            )
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "DOMAIN_MISMATCH"


class TestOrphanedMediaRegistration:
    def test_endpoint_registered(self):
        from api.main import app
        registered = {r.path for r in app.routes if hasattr(r, "path")}
        assert "/api/fixes/orphaned-media/{job_id}" in registered
