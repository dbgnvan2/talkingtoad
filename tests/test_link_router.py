"""Contract tests for link_router (v2.3 M0.12.6).

8 endpoints. Verify-broken-links is the most complex (it goes out to the
network); we test the empty-broken-links path here, and trust the SSRF
adversarial tests in test_fetcher.py to cover the safe-fetch behaviour.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from api.models.issue import Issue
from api.models.job import CrawlJob
from api.models.page import CrawledPage


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


class TestLinkRouterAuth:
    @pytest.mark.parametrize("method,path", [
        ("get",  "/api/fixes/link-sources?job_id=x&target_url=https://x/y"),
        ("post", "/api/fixes/replace-link"),
        ("post", "/api/fixes/verify-broken-links/some-job"),
        ("post", "/api/fixes/mark-broken-link-fixed"),
        ("post", "/api/fixes/mark-anchor-fixed"),
        ("post", "/api/fixes/mark-issue-fixed"),
        ("post", "/api/fixes/apply-one"),
        ("get",  "/api/fixes/wp-value?page_url=https://x/y&field=title"),
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


class TestLinkRouterValidation:
    @pytest.mark.asyncio
    async def test_link_sources_missing_required_returns_422(
        self, api_client, auth_headers
    ):
        r = await api_client.get("/api/fixes/link-sources", headers=auth_headers)
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_mark_issue_fixed_empty_codes_rejected(
        self, api_client, auth_headers, seeded_job
    ):
        api_client, job_id = seeded_job
        r = await api_client.post(
            "/api/fixes/mark-issue-fixed",
            json={"job_id": job_id, "page_url": "https://x/y", "issue_codes": []},
            headers=auth_headers,
        )
        assert r.status_code == 422   # min_length=1


# ---------------------------------------------------------------------------
# Not-found
# ---------------------------------------------------------------------------


class TestLinkRouterNotFound:
    @pytest.mark.asyncio
    async def test_link_sources_unknown_job(self, api_client, auth_headers):
        r = await api_client.get(
            "/api/fixes/link-sources?job_id=does-not-exist&target_url=https://x/y",
            headers=auth_headers,
        )
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "JOB_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_verify_broken_links_unknown_job(self, api_client, auth_headers):
        r = await api_client.post(
            "/api/fixes/verify-broken-links/does-not-exist",
            headers=auth_headers,
        )
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_mark_anchor_no_issue_returns_404(
        self, api_client, auth_headers, seeded_job
    ):
        api_client, job_id = seeded_job
        r = await api_client.post(
            "/api/fixes/mark-anchor-fixed",
            json={
                "job_id": job_id,
                "page_url": "https://example.com/foo",
                "anchor_href": "#some-target",
            },
            headers=auth_headers,
        )
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "ISSUE_NOT_FOUND"


# ---------------------------------------------------------------------------
# Happy paths (store-only — no WP)
# ---------------------------------------------------------------------------


class TestLinkRouterStoreOnly:
    @pytest.mark.asyncio
    async def test_link_sources_returns_empty_when_no_links(
        self, api_client, auth_headers, seeded_job
    ):
        api_client, job_id = seeded_job
        r = await api_client.get(
            f"/api/fixes/link-sources?job_id={job_id}&target_url=https://example.com/no-such",
            headers=auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 0
        assert body["sources"] == []
        assert body["target_url"] == "https://example.com/no-such"

    @pytest.mark.asyncio
    async def test_verify_broken_links_returns_zero_when_no_issues(
        self, api_client, auth_headers, seeded_job
    ):
        api_client, job_id = seeded_job
        r = await api_client.post(
            f"/api/fixes/verify-broken-links/{job_id}",
            headers=auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["checked"] == 0
        assert body["still_broken"] == 0
        assert body["now_ok"] == 0

    @pytest.mark.asyncio
    async def test_mark_issue_fixed_deletes_issues(
        self, api_client, auth_headers, test_store, seeded_job
    ):
        api_client, job_id = seeded_job
        # Seed an issue to delete
        await test_store.save_issues([
            Issue(
                job_id=job_id,
                page_url="https://example.com/about",
                issue_code="TITLE_TOO_LONG",
                category="metadata",
                severity="warning",
                description="Title too long",
                recommendation="Trim it",
            ),
        ])

        r = await api_client.post(
            "/api/fixes/mark-issue-fixed",
            json={
                "job_id": job_id,
                "page_url": "https://example.com/about",
                "issue_codes": ["TITLE_TOO_LONG"],
            },
            headers=auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["deleted"] >= 1


# ---------------------------------------------------------------------------
# NO_CREDENTIALS / DOMAIN_MISMATCH branches on WP-touching endpoints
# ---------------------------------------------------------------------------


class TestLinkRouterWPBranches:
    @pytest.mark.asyncio
    async def test_replace_link_no_credentials(
        self, api_client, auth_headers, seeded_job, tmp_path
    ):
        api_client, job_id = seeded_job
        nonexistent = tmp_path / "missing.json"
        with patch("api.routers.link_router._CREDS_PATH", nonexistent):
            r = await api_client.post(
                "/api/fixes/replace-link",
                json={
                    "job_id": job_id,
                    "source_url": "https://example.com/page",
                    "old_url": "https://example.com/old",
                    "new_url": "https://example.com/new",
                },
                headers=auth_headers,
            )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "NO_CREDENTIALS"

    @pytest.mark.asyncio
    async def test_apply_one_domain_mismatch(
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
        with patch("api.routers.link_router._CREDS_PATH", creds_path), \
             patch("api.routers.fixes_shared._CREDS_PATH", creds_path):
            r = await api_client.post(
                "/api/fixes/apply-one",
                json={
                    "job_id": job_id,
                    "page_url": "https://example.com/about",
                    "issue_code": "TITLE_TOO_LONG",
                    "proposed_value": "Trimmed",
                },
                headers=auth_headers,
            )
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "DOMAIN_MISMATCH"

    @pytest.mark.asyncio
    async def test_wp_value_no_credentials(
        self, api_client, auth_headers, tmp_path
    ):
        nonexistent = tmp_path / "missing.json"
        with patch("api.routers.link_router._CREDS_PATH", nonexistent):
            r = await api_client.get(
                "/api/fixes/wp-value?page_url=https://example.com/x&field=title",
                headers=auth_headers,
            )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "NO_CREDENTIALS"


# ---------------------------------------------------------------------------
# Architecture
# ---------------------------------------------------------------------------


class TestLinkRouterRegistration:
    def test_all_eight_endpoints_registered(self):
        from api.main import app
        registered = {r.path for r in app.routes if hasattr(r, "path")}
        for path in [
            "/api/fixes/link-sources",
            "/api/fixes/replace-link",
            "/api/fixes/verify-broken-links/{job_id}",
            "/api/fixes/mark-broken-link-fixed",
            "/api/fixes/mark-anchor-fixed",
            "/api/fixes/mark-issue-fixed",
            "/api/fixes/apply-one",
            "/api/fixes/wp-value",
        ]:
            assert path in registered, f"{path} not registered on app"
