"""
Tests for WordPress domain validation across all WP-touching endpoints.

Verifies that endpoints reject requests when the WP credentials domain
doesn't match the crawl job's target domain or the request URL's domain.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from api.models.job import CrawlJob
from api.models.page import CrawledPage

os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("AUTH_TOKEN", "test-token")

AUTH = {"Authorization": "Bearer test-token"}

MISMATCHED_CREDS = {
    "site_url": "https://other-site.com",
    "login_url": "https://other-site.com/wp-login.php",
    "username": "admin",
    "password": "secret",
}

MATCHING_CREDS = {
    "site_url": "https://example.com",
    "login_url": "https://example.com/wp-login.php",
    "username": "admin",
    "password": "secret",
}


@pytest.fixture
async def store():
    from api.services.job_store import SQLiteJobStore
    async with SQLiteJobStore(db_path=":memory:") as s:
        yield s


@pytest.fixture
async def client_and_store(store):
    from api.main import app
    from api.routers.crawl import get_store as crawl_get_store
    from api.routers.fixes import get_store as fixes_get_store

    app.dependency_overrides[crawl_get_store] = lambda: store
    app.dependency_overrides[fixes_get_store] = lambda: store

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client, store

    app.dependency_overrides.clear()


@pytest.fixture
async def seeded(client_and_store):
    client, store = client_and_store
    job_id = str(uuid4())
    job = CrawlJob(job_id=job_id, target_url="https://example.com", status="complete", pages_crawled=2)
    await store.create_job(job)
    page = CrawledPage(job_id=job_id, url="https://example.com/about", status_code=200, title="About Us", crawled_at=datetime.now(timezone.utc))
    await store.save_pages([page])
    return client, store, job_id


def _assert_domain_mismatch(r):
    assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
    assert r.json()["error"]["code"] == "DOMAIN_MISMATCH"


class TestJobIdEndpoints:
    @pytest.fixture(autouse=True)
    def _mock_creds(self, tmp_path):
        creds_path = tmp_path / "wp-credentials.json"
        creds_path.write_text(json.dumps(MISMATCHED_CREDS))
        with patch("api.routers.fixes._CREDS_PATH", creds_path):
            yield

    async def test_generate_fixes_rejects_mismatch(self, seeded):
        client, store, job_id = seeded
        r = await client.post(f"/api/fixes/generate/{job_id}", headers=AUTH)
        _assert_domain_mismatch(r)

    async def test_orphaned_media_rejects_mismatch(self, seeded):
        client, store, job_id = seeded
        r = await client.get(f"/api/fixes/orphaned-media/{job_id}", headers=AUTH)
        _assert_domain_mismatch(r)

    async def test_delete_media_rejects_mismatch(self, seeded):
        client, store, job_id = seeded
        r = await client.delete("/api/fixes/media/123", params={"job_id": job_id}, headers=AUTH)
        _assert_domain_mismatch(r)

    async def test_apply_fixes_rejects_mismatch(self, seeded):
        client, store, job_id = seeded
        r = await client.post(f"/api/fixes/apply/{job_id}", headers=AUTH)
        _assert_domain_mismatch(r)

    async def test_batch_optimize_rejects_mismatch(self, seeded):
        client, store, job_id = seeded
        r = await client.post("/api/fixes/batch-optimize/start", json={"job_id": job_id, "image_urls": ["https://example.com/img.jpg"]}, headers=AUTH)
        _assert_domain_mismatch(r)


class TestUrlOnlyEndpoints:
    @pytest.fixture(autouse=True)
    def _mock_creds(self, tmp_path):
        creds_path = tmp_path / "wp-credentials.json"
        creds_path.write_text(json.dumps(MATCHING_CREDS))
        with patch("api.routers.fixes._CREDS_PATH", creds_path):
            yield

    async def test_trim_title_one_rejects_wrong_url_domain(self, seeded):
        client, store, job_id = seeded
        r = await client.post("/api/fixes/trim-title-one", params={"page_url": "https://wrong-domain.com/page"}, headers=AUTH)
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "DOMAIN_MISMATCH"

    async def test_image_info_rejects_wrong_url_domain(self, seeded):
        client, store, job_id = seeded
        r = await client.get("/api/fixes/image-info", params={"image_url": "https://wrong-domain.com/img.jpg"}, headers=AUTH)
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "DOMAIN_MISMATCH"


class TestHelperFunctions:
    def test_validate_wp_domain_for_url_mismatch(self, tmp_path):
        from api.routers.fixes import _validate_wp_domain_for_url
        creds_path = tmp_path / "wp-credentials.json"
        creds_path.write_text(json.dumps(MATCHING_CREDS))
        with patch("api.routers.fixes._CREDS_PATH", creds_path):
            result = _validate_wp_domain_for_url("https://wrong-site.org/page")
            assert result is not None
            assert result.status_code == 403

    def test_validate_wp_domain_for_url_match(self, tmp_path):
        from api.routers.fixes import _validate_wp_domain_for_url
        creds_path = tmp_path / "wp-credentials.json"
        creds_path.write_text(json.dumps(MATCHING_CREDS))
        with patch("api.routers.fixes._CREDS_PATH", creds_path):
            result = _validate_wp_domain_for_url("https://example.com/page")
            assert result is None

    async def test_validate_wp_domain_for_job_mismatch(self, store):
        from api.routers.fixes import _validate_wp_domain_for_job
        job_id = str(uuid4())
        await store.create_job(CrawlJob(job_id=job_id, target_url="https://example.com", status="complete"))
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(MISMATCHED_CREDS, f)
            creds_path = Path(f.name)
        try:
            with patch("api.routers.fixes._CREDS_PATH", creds_path):
                result = await _validate_wp_domain_for_job(store, job_id)
                assert result is not None
                assert result.status_code == 403
        finally:
            creds_path.unlink()


class TestSummaryIncludesTargetUrl:
    """Verify the summary endpoint returns target_url for domain display."""

    async def test_summary_has_target_url(self, store):
        job_id = str(uuid4())
        job = CrawlJob(job_id=job_id, target_url="https://example.com", status="complete", pages_crawled=1)
        await store.create_job(job)
        summary = await store.get_summary(job_id)
        assert "target_url" in summary
        assert summary["target_url"] == "https://example.com"
