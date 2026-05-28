"""Contract tests for batch_optimizer_router (v2.3 M0.12.5).

Service-level batch behaviour (create, start, pause/resume/cancel, status,
list) is covered in tests/test_batch_optimizer.py. This file focuses on the
HTTP contract surface.
"""

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


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class TestBatchRouterAuth:
    @pytest.mark.parametrize("method,path", [
        ("post", "/api/fixes/batch-optimize/start"),
        ("get",  "/api/fixes/batch-optimize/some-id/status"),
        ("post", "/api/fixes/batch-optimize/some-id/pause"),
        ("post", "/api/fixes/batch-optimize/some-id/resume"),
        ("post", "/api/fixes/batch-optimize/some-id/cancel"),
        ("get",  "/api/fixes/batch-optimize/list"),
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


class TestBatchRouterValidation:
    @pytest.mark.asyncio
    async def test_start_missing_body_returns_422(self, api_client, auth_headers):
        r = await api_client.post("/api/fixes/batch-optimize/start", headers=auth_headers)
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_start_empty_image_urls_rejected(
        self, api_client, auth_headers, seeded_job
    ):
        """Adversarial: empty image_urls list — Pydantic min_length=1 rejects."""
        api_client, job_id = seeded_job
        r = await api_client.post(
            "/api/fixes/batch-optimize/start",
            json={"job_id": job_id, "image_urls": []},
            headers=auth_headers,
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_start_parallel_limit_capped(
        self, api_client, auth_headers, seeded_job
    ):
        """Adversarial: parallel_limit=999 must be rejected (le=10 guard)."""
        api_client, job_id = seeded_job
        r = await api_client.post(
            "/api/fixes/batch-optimize/start",
            json={
                "job_id": job_id,
                "image_urls": ["https://example.com/img.jpg"],
                "parallel_limit": 999,
            },
            headers=auth_headers,
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Not-found branches
# ---------------------------------------------------------------------------


class TestBatchRouterNotFound:
    @pytest.mark.asyncio
    async def test_start_unknown_job_returns_404(self, api_client, auth_headers):
        r = await api_client.post(
            "/api/fixes/batch-optimize/start",
            json={
                "job_id": "does-not-exist",
                "image_urls": ["https://example.com/img.jpg"],
            },
            headers=auth_headers,
        )
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "JOB_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_status_unknown_batch_returns_404(self, api_client, auth_headers):
        r = await api_client.get(
            "/api/fixes/batch-optimize/no-such-batch/status",
            headers=auth_headers,
        )
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "BATCH_NOT_FOUND"

    @pytest.mark.parametrize("op", ["pause", "resume", "cancel"])
    @pytest.mark.asyncio
    async def test_op_unknown_batch_returns_404(self, api_client, auth_headers, op):
        r = await api_client.post(
            f"/api/fixes/batch-optimize/no-such-batch/{op}",
            headers=auth_headers,
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# NO_CREDENTIALS branch
# ---------------------------------------------------------------------------


class TestBatchRouterNoCredentials:
    @pytest.mark.asyncio
    async def test_start_no_credentials(
        self, api_client, auth_headers, seeded_job, tmp_path
    ):
        api_client, job_id = seeded_job
        nonexistent = tmp_path / "missing.json"
        with patch("api.routers.batch_optimizer_router._CREDS_PATH", nonexistent):
            r = await api_client.post(
                "/api/fixes/batch-optimize/start",
                json={
                    "job_id": job_id,
                    "image_urls": ["https://example.com/img.jpg"],
                },
                headers=auth_headers,
            )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "NO_CREDENTIALS"


# ---------------------------------------------------------------------------
# List returns empty
# ---------------------------------------------------------------------------


class TestBatchRouterList:
    @pytest.mark.asyncio
    async def test_list_returns_empty_when_no_batches(
        self, api_client, auth_headers
    ):
        r = await api_client.get(
            "/api/fixes/batch-optimize/list?job_id=nonexistent-filter",
            headers=auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert "batches" in body
        assert "count" in body
        assert body["count"] == len(body["batches"])


# ---------------------------------------------------------------------------
# Architecture
# ---------------------------------------------------------------------------


class TestBatchRouterRegistration:
    def test_all_six_endpoints_registered(self):
        from api.main import app
        registered = {r.path for r in app.routes if hasattr(r, "path")}
        for path in [
            "/api/fixes/batch-optimize/start",
            "/api/fixes/batch-optimize/{batch_id}/status",
            "/api/fixes/batch-optimize/{batch_id}/pause",
            "/api/fixes/batch-optimize/{batch_id}/resume",
            "/api/fixes/batch-optimize/{batch_id}/cancel",
            "/api/fixes/batch-optimize/list",
        ]:
            assert path in registered, f"{path} not registered on app"
