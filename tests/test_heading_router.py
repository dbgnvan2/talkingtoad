"""Contract tests for heading_router endpoints (v2.3 M0.12.2).

Endpoints under test:
    GET  /api/fixes/find-heading
    GET  /api/fixes/analyze-heading-sources
    POST /api/fixes/change-heading-level
    POST /api/fixes/change-heading-text
    POST /api/fixes/bulk-replace-heading
    POST /api/fixes/heading-to-bold

Plus service-level tests for the 3 functions re-introduced in this milestone:
- find_heading (pure read against store, no WP)
- bulk_replace_heading (preview mode + no-op guard + per-page iteration)
- convert_heading_to_bold (regex find/replace with inner-tag handling)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from api.models.job import CrawlJob
from api.models.page import CrawledPage


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def seeded_job_with_headings(api_client, test_store):
    """Three pages with various headings for find_heading / bulk_replace_heading tests."""
    job_id = str(uuid4())
    job = CrawlJob(
        job_id=job_id,
        target_url="https://example.com",
        status="complete",
        pages_crawled=3,
    )
    await test_store.create_job(job)
    pages = [
        CrawledPage(
            job_id=job_id,
            url="https://example.com/about",
            status_code=200,
            title="About",
            headings_outline=[
                {"level": 1, "text": "About Us"},
                {"level": 2, "text": "Our Mission"},
                {"level": 4, "text": "Stop Bullying"},
            ],
            crawled_at=datetime.now(timezone.utc),
        ),
        CrawledPage(
            job_id=job_id,
            url="https://example.com/services",
            status_code=200,
            title="Services",
            headings_outline=[
                {"level": 1, "text": "Services"},
                {"level": 4, "text": "Stop Bullying"},
            ],
            crawled_at=datetime.now(timezone.utc),
        ),
        CrawledPage(
            job_id=job_id,
            url="https://example.com/contact",
            status_code=200,
            title="Contact",
            headings_outline=[
                {"level": 1, "text": "Contact"},
            ],
            crawled_at=datetime.now(timezone.utc),
        ),
    ]
    await test_store.save_pages(pages)
    return api_client, job_id


# ---------------------------------------------------------------------------
# Service: find_heading (pure read, no WP)
# ---------------------------------------------------------------------------


class TestFindHeadingService:
    @pytest.mark.asyncio
    async def test_finds_matching_text_across_pages(self, test_store):
        from api.services.wp_heading_fixer import find_heading

        job_id = str(uuid4())
        await test_store.create_job(CrawlJob(
            job_id=job_id, target_url="https://example.com", pages_crawled=2,
        ))
        await test_store.save_pages([
            CrawledPage(
                job_id=job_id, url="https://example.com/a", status_code=200,
                headings_outline=[{"level": 4, "text": "Stop Bullying"}],
                crawled_at=datetime.now(timezone.utc),
            ),
            CrawledPage(
                job_id=job_id, url="https://example.com/b", status_code=200,
                headings_outline=[{"level": 4, "text": "Stop Bullying"}],
                crawled_at=datetime.now(timezone.utc),
            ),
        ])

        matches = await find_heading(test_store, job_id, "Stop Bullying")
        assert len(matches) == 2
        assert {m["page_url"] for m in matches} == {
            "https://example.com/a", "https://example.com/b",
        }

    @pytest.mark.asyncio
    async def test_level_filter_excludes_other_levels(self, test_store):
        """Adversarial: a page with 'X' at both H2 and H4 — requesting level=2 must
        not return the H4 match."""
        from api.services.wp_heading_fixer import find_heading

        job_id = str(uuid4())
        await test_store.create_job(CrawlJob(
            job_id=job_id, target_url="https://example.com", pages_crawled=1,
        ))
        await test_store.save_pages([
            CrawledPage(
                job_id=job_id, url="https://example.com/x", status_code=200,
                headings_outline=[
                    {"level": 2, "text": "Same Title"},
                    {"level": 4, "text": "Same Title"},
                ],
                crawled_at=datetime.now(timezone.utc),
            ),
        ])

        matches = await find_heading(test_store, job_id, "Same Title", level=2)
        assert len(matches) == 1
        assert matches[0]["level"] == 2

    @pytest.mark.asyncio
    async def test_fuzzy_text_match(self, test_store):
        """Smart quotes and extra whitespace are normalized."""
        from api.services.wp_heading_fixer import find_heading

        job_id = str(uuid4())
        await test_store.create_job(CrawlJob(
            job_id=job_id, target_url="https://example.com", pages_crawled=1,
        ))
        await test_store.save_pages([
            CrawledPage(
                job_id=job_id, url="https://example.com/x", status_code=200,
                # Heading stored with smart quotes
                headings_outline=[{"level": 2, "text": "It’s “Bold”"}],
                crawled_at=datetime.now(timezone.utc),
            ),
        ])

        # Caller passes plain ASCII — should still match
        matches = await find_heading(test_store, job_id, 'It\'s "Bold"')
        assert len(matches) == 1

    @pytest.mark.asyncio
    async def test_no_matches_returns_empty_list(self, test_store):
        from api.services.wp_heading_fixer import find_heading

        job_id = str(uuid4())
        await test_store.create_job(CrawlJob(
            job_id=job_id, target_url="https://example.com", pages_crawled=0,
        ))
        matches = await find_heading(test_store, job_id, "Nonexistent")
        assert matches == []


# ---------------------------------------------------------------------------
# Service: bulk_replace_heading
# ---------------------------------------------------------------------------


class TestBulkReplaceHeadingService:
    @pytest.mark.asyncio
    async def test_preview_mode_no_wp_calls(self, test_store):
        """to_level=None must return matches without touching WP."""
        from api.services.wp_heading_fixer import bulk_replace_heading

        job_id = str(uuid4())
        await test_store.create_job(CrawlJob(
            job_id=job_id, target_url="https://example.com", pages_crawled=1,
        ))
        await test_store.save_pages([
            CrawledPage(
                job_id=job_id, url="https://example.com/x", status_code=200,
                headings_outline=[{"level": 4, "text": "Stop Bullying"}],
                crawled_at=datetime.now(timezone.utc),
            ),
        ])

        wp = MagicMock(spec=["get", "patch"])  # would raise if called
        result = await bulk_replace_heading(
            wp, test_store, job_id, "Stop Bullying", from_level=4, to_level=None,
        )
        assert result["matched"] == 1
        assert result["applied"] == 0
        assert result["skipped"] == 1
        assert result["errors"] == 0
        assert result["results"][0]["preview"] is True

    @pytest.mark.asyncio
    async def test_no_op_when_from_equals_to(self, test_store):
        """Adversarial: caller passes from_level == to_level — guard rejects."""
        from api.services.wp_heading_fixer import bulk_replace_heading

        job_id = str(uuid4())
        await test_store.create_job(CrawlJob(
            job_id=job_id, target_url="https://example.com", pages_crawled=1,
        ))
        await test_store.save_pages([
            CrawledPage(
                job_id=job_id, url="https://example.com/x", status_code=200,
                headings_outline=[{"level": 4, "text": "Stop Bullying"}],
                crawled_at=datetime.now(timezone.utc),
            ),
        ])

        wp = MagicMock(spec=["get", "patch"])
        result = await bulk_replace_heading(
            wp, test_store, job_id, "Stop Bullying", from_level=4, to_level=4,
        )
        assert result["applied"] == 0
        assert "no-op" in result["results"][0]["error"]

    @pytest.mark.asyncio
    async def test_per_page_error_increments_errors(self, test_store):
        """When change_heading_level raises for one page, errors counter increments
        but the loop continues for other pages."""
        from api.services.wp_heading_fixer import bulk_replace_heading

        job_id = str(uuid4())
        await test_store.create_job(CrawlJob(
            job_id=job_id, target_url="https://example.com", pages_crawled=2,
        ))
        await test_store.save_pages([
            CrawledPage(
                job_id=job_id, url="https://example.com/ok", status_code=200,
                headings_outline=[{"level": 4, "text": "Stop Bullying"}],
                crawled_at=datetime.now(timezone.utc),
            ),
            CrawledPage(
                job_id=job_id, url="https://example.com/boom", status_code=200,
                headings_outline=[{"level": 4, "text": "Stop Bullying"}],
                crawled_at=datetime.now(timezone.utc),
            ),
        ])

        with patch(
            "api.services.wp_heading_fixer.change_heading_level",
            new_callable=AsyncMock,
        ) as mock_change:
            mock_change.side_effect = [
                {"success": True, "changed": 1, "error": None},
                Exception("Connection reset"),
            ]
            wp = MagicMock()
            result = await bulk_replace_heading(
                wp, test_store, job_id, "Stop Bullying",
                from_level=4, to_level=2,
            )

        assert result["matched"] == 2
        assert result["applied"] == 1
        assert result["errors"] == 1
        # `.get("error") or ""` handles both missing key and explicit None.
        assert any(
            "Connection reset" in (r.get("error") or "") for r in result["results"]
        )


# ---------------------------------------------------------------------------
# Service: convert_heading_to_bold
# ---------------------------------------------------------------------------


class TestConvertHeadingToBoldService:
    @pytest.mark.asyncio
    async def test_invalid_level_rejected(self):
        from api.services.wp_heading_fixer import convert_heading_to_bold
        wp = MagicMock()
        result = await convert_heading_to_bold(wp, "https://x/y", "X", level=7)
        assert result["success"] is False
        assert "Invalid level" in result["error"]


# ---------------------------------------------------------------------------
# Router: GET /find-heading
# ---------------------------------------------------------------------------


class TestFindHeadingEndpoint:
    @pytest.mark.asyncio
    async def test_requires_auth(self, api_client):
        r = await api_client.get(
            "/api/fixes/find-heading?job_id=x&heading_text=y"
        )
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_required_param_returns_422(self, api_client, auth_headers):
        r = await api_client.get("/api/fixes/find-heading", headers=auth_headers)
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_unknown_job_returns_404(self, api_client, auth_headers):
        r = await api_client.get(
            "/api/fixes/find-heading?job_id=does-not-exist&heading_text=x",
            headers=auth_headers,
        )
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "JOB_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_returns_matches_and_count(
        self, api_client, auth_headers, seeded_job_with_headings
    ):
        api_client, job_id = seeded_job_with_headings
        r = await api_client.get(
            f"/api/fixes/find-heading?job_id={job_id}&heading_text=Stop+Bullying",
            headers=auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 2
        assert len(body["matches"]) == 2
        urls = {m["page_url"] for m in body["matches"]}
        assert urls == {
            "https://example.com/about", "https://example.com/services",
        }

    @pytest.mark.asyncio
    async def test_level_filter(
        self, api_client, auth_headers, seeded_job_with_headings
    ):
        api_client, job_id = seeded_job_with_headings
        r = await api_client.get(
            f"/api/fixes/find-heading?job_id={job_id}&heading_text=Stop+Bullying&level=2",
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["count"] == 0   # no H2 match exists


# ---------------------------------------------------------------------------
# Router: POST endpoints — auth, validation, NO_CREDENTIALS,
# DOMAIN_MISMATCH paths. Happy-path WP behaviour is covered by the
# service-level tests in test_wp_fixer.py and the service classes above.
# ---------------------------------------------------------------------------


class TestHeadingRouterAuthAndValidation:
    @pytest.mark.parametrize("method,path", [
        ("post", "/api/fixes/change-heading-level"),
        ("post", "/api/fixes/change-heading-text"),
        ("post", "/api/fixes/bulk-replace-heading"),
        ("post", "/api/fixes/heading-to-bold"),
        ("get",  "/api/fixes/analyze-heading-sources"),
    ])
    @pytest.mark.asyncio
    async def test_requires_auth(self, api_client, method, path):
        if method == "post":
            r = await api_client.post(path)
        else:
            r = await api_client.get(path)
        assert r.status_code == 401

    @pytest.mark.parametrize("method,path", [
        ("post", "/api/fixes/change-heading-level"),
        ("post", "/api/fixes/change-heading-text"),
        ("post", "/api/fixes/bulk-replace-heading"),
        ("post", "/api/fixes/heading-to-bold"),
        ("get",  "/api/fixes/analyze-heading-sources"),
    ])
    @pytest.mark.asyncio
    async def test_missing_required_params_returns_422(
        self, api_client, auth_headers, method, path
    ):
        if method == "post":
            r = await api_client.post(path, headers=auth_headers)
        else:
            r = await api_client.get(path, headers=auth_headers)
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_no_credentials_change_heading_level(
        self, api_client, auth_headers, tmp_path
    ):
        nonexistent = tmp_path / "no-such-file.json"
        with patch("api.routers.heading_router._CREDS_PATH", nonexistent):
            r = await api_client.post(
                "/api/fixes/change-heading-level"
                "?page_url=https://example.com/x"
                "&heading_text=foo&from_level=2&to_level=3",
                headers=auth_headers,
            )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "NO_CREDENTIALS"

    @pytest.mark.asyncio
    async def test_domain_mismatch_heading_to_bold(
        self, api_client, auth_headers, tmp_path
    ):
        creds_path = tmp_path / "wp-credentials.json"
        creds_path.write_text(json.dumps({
            "site_url": "https://example.com",
            "login_url": "https://example.com/wp-login.php",
            "username": "admin",
            "password": "secret",
        }))
        with patch("api.routers.heading_router._CREDS_PATH", creds_path), \
             patch("api.routers.fixes_shared._CREDS_PATH", creds_path):
            r = await api_client.post(
                "/api/fixes/heading-to-bold"
                "?page_url=https://other-site.com/x&heading_text=foo&level=4",
                headers=auth_headers,
            )
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "DOMAIN_MISMATCH"


# ---------------------------------------------------------------------------
# Architecture test
# ---------------------------------------------------------------------------


class TestHeadingRouterRegistration:
    def test_all_six_endpoints_registered(self):
        """Adversarial: someone removes include_router(heading_router) in fixes.py
        — these endpoints silently 404. Fails loudly here."""
        from api.main import app
        registered = {r.path for r in app.routes if hasattr(r, "path")}
        for path in [
            "/api/fixes/find-heading",
            "/api/fixes/analyze-heading-sources",
            "/api/fixes/change-heading-level",
            "/api/fixes/change-heading-text",
            "/api/fixes/bulk-replace-heading",
            "/api/fixes/heading-to-bold",
        ]:
            assert path in registered, f"{path} not registered on app"
