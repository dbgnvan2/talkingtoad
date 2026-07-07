"""
Tests for M6.1 + M6.4 — GSC OAuth, data ingest, and performance endpoints.

All Google API calls are mocked; NO live calls in this suite.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app
from api.models.performance import PerformanceRecord
from api.services.gsc_client import fetch_page_performance, list_properties


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def clear_gsc_env(monkeypatch):
    """Ensure GSC env is unset by default; individual tests opt in."""
    monkeypatch.delenv("GSC_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("GSC_OAUTH_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("GSC_OAUTH_REDIRECT_URI", raising=False)
    monkeypatch.delenv("AI_CREDS_ENCRYPTION_KEY", raising=False)
    # Clear any cached credentials from other tests
    from api.routers.gsc import _creds_cache, _pkce_store
    _creds_cache.clear()
    _pkce_store.clear()
    yield


@pytest.fixture
def gsc_env(monkeypatch):
    """Set GSC env vars for tests that need them."""
    monkeypatch.setenv("GSC_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GSC_OAUTH_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("GSC_OAUTH_REDIRECT_URI", "http://localhost:8000/api/gsc/callback")


@pytest.fixture
async def gsc_client():
    """Async HTTP test client with auth disabled."""
    from api.services.auth import require_auth

    app.dependency_overrides[require_auth] = lambda: None

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
async def gsc_store():
    """In-memory store for GSC integration tests."""
    from api.services.sqlite_store import SQLiteJobStore

    async with SQLiteJobStore(db_path=":memory:") as s:
        yield s


# ── gsc_client unit tests ────────────────────────────────────────────────────


class TestFetchPagePerformance:
    @pytest.mark.asyncio
    async def test_parses_response(self):
        """Mock GSC API response -> parsed list of dicts."""
        mock_service = MagicMock()
        mock_query = MagicMock()
        mock_query.execute.return_value = {
            "rows": [
                {
                    "keys": ["https://example.com/page1"],
                    "clicks": 10,
                    "impressions": 100,
                    "ctr": 0.1,
                    "position": 5.0,
                },
                {
                    "keys": ["https://example.com/page2"],
                    "clicks": 5,
                    "impressions": 50,
                    "ctr": 0.1,
                    "position": 3.2,
                },
            ]
        }
        mock_service.searchanalytics.return_value.query.return_value = mock_query

        with patch("api.services.gsc_client.build") as mock_build:
            mock_build.return_value = mock_service
            creds = MagicMock()
            result = await fetch_page_performance(creds, "https://example.com/")

        assert len(result) == 2
        assert result[0]["url"] == "https://example.com/page1"
        assert result[0]["clicks"] == 10
        assert result[0]["impressions"] == 100
        assert result[0]["ctr"] == 0.1
        assert result[0]["position"] == 5.0

    @pytest.mark.asyncio
    async def test_empty_response(self):
        """Empty rows -> empty list (not an error)."""
        mock_service = MagicMock()
        mock_query = MagicMock()
        mock_query.execute.return_value = {"rows": []}
        mock_service.searchanalytics.return_value.query.return_value = mock_query

        with patch("api.services.gsc_client.build") as mock_build:
            mock_build.return_value = mock_service
            result = await fetch_page_performance(MagicMock(), "https://example.com/")

        assert result == []

    @pytest.mark.asyncio
    async def test_backoff_on_429(self):
        """Mock 429 then 200 -> retried and succeeded."""
        from googleapiclient.errors import HttpError

        mock_service = MagicMock()
        mock_query = MagicMock()
        # First call raises 429, second succeeds
        mock_query.execute.side_effect = [
            HttpError(MagicMock(status=429), b"Rate limited"),
            {
                "rows": [
                    {
                        "keys": ["https://example.com/page"],
                        "clicks": 1,
                        "impressions": 10,
                        "ctr": 0.1,
                        "position": 1.0,
                    }
                ]
            },
        ]
        mock_service.searchanalytics.return_value.query.return_value = mock_query

        with patch("api.services.gsc_client.build") as mock_build, \
             patch("api.services.gsc_client.time.sleep"):
            mock_build.return_value = mock_service
            result = await fetch_page_performance(MagicMock(), "https://example.com/")

        assert len(result) == 1
        assert mock_query.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_raises_on_non_retryable_error(self):
        """403 should NOT be retried — raises immediately."""
        from googleapiclient.errors import HttpError

        mock_service = MagicMock()
        mock_query = MagicMock()
        mock_query.execute.side_effect = HttpError(
            MagicMock(status=403), b"Forbidden"
        )
        mock_service.searchanalytics.return_value.query.return_value = mock_query

        with patch("api.services.gsc_client.build") as mock_build:
            mock_build.return_value = mock_service
            with pytest.raises(HttpError):
                await fetch_page_performance(MagicMock(), "https://example.com/")

        assert mock_query.execute.call_count == 1


class TestListProperties:
    def test_returns_properties(self):
        """Mock sites().list() -> parsed list."""
        mock_service = MagicMock()
        mock_service.sites.return_value.list.return_value.execute.return_value = {
            "siteEntry": [
                {"siteUrl": "https://example.com/", "permissionLevel": "siteOwner"},
                {
                    "siteUrl": "sc-domain:example.com",
                    "permissionLevel": "siteUnverifiedUser",
                },
            ]
        }

        with patch("api.services.gsc_client.build") as mock_build:
            mock_build.return_value = mock_service
            result = list_properties(MagicMock())

        assert len(result) == 2
        assert result[0]["site_url"] == "https://example.com/"
        assert result[0]["permission_level"] == "siteOwner"


# ── Opt-in guarantee ─────────────────────────────────────────────────────────


class TestOptInGuarantee:
    """When GSC env vars are unset, all /api/gsc/* endpoints return 503."""

    @pytest.mark.asyncio
    async def test_connect_503_when_env_unset(self, gsc_client):
        resp = await gsc_client.get("/api/gsc/connect")
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_status_503_when_env_unset(self, gsc_client):
        resp = await gsc_client.get("/api/gsc/status")
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_disconnect_503_when_env_unset(self, gsc_client):
        resp = await gsc_client.post("/api/gsc/disconnect")
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_ingest_503_when_env_unset(self, gsc_client):
        resp = await gsc_client.post(
            "/api/gsc/ingest", params={"site_url": "x", "job_id": "y"}
        )
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_performance_503_when_env_unset(self, gsc_client):
        resp = await gsc_client.get("/api/gsc/performance", params={"url": "x"})
        assert resp.status_code == 503


# ── OAuth endpoint tests ─────────────────────────────────────────────────────


class TestGscConnect:
    @pytest.mark.asyncio
    async def test_302_redirect_when_configured(self, gsc_client, gsc_env):
        """GSC env vars set -> redirect to Google consent."""
        with patch("api.routers.gsc.build_flow") as mock_build:
            mock_flow = MagicMock()
            mock_flow.authorization_url.return_value = (
                "https://accounts.google.com/o/oauth2/auth?state=test",
                "test",
            )
            mock_flow.code_verifier = "test_verifier"
            mock_build.return_value = mock_flow

            resp = await gsc_client.get(
                "/api/gsc/connect", follow_redirects=False
            )

        assert resp.status_code == 302
        assert resp.headers["location"].startswith(
            "https://accounts.google.com"
        )


class TestGscCallback:
    @pytest.mark.asyncio
    async def test_exchange_and_store(self, gsc_client, gsc_env):
        """Mock token exchange -> creds stored; status shows connected."""
        from api.routers.gsc import _pkce_store

        _pkce_store["test_state"] = {
            "code_verifier": "test_verifier",
            "state": "test_state",
        }

        with patch("api.routers.gsc.build_flow") as mock_build:
            mock_flow = MagicMock()
            mock_flow.credentials.to_json.return_value = json.dumps(
                {"token": "fake", "refresh_token": "fake_refresh"}
            )
            mock_build.return_value = mock_flow

            resp = await gsc_client.get(
                "/api/gsc/callback",
                params={"code": "test_code", "state": "test_state"},
            )

        assert resp.status_code == 200
        assert "GSC Connected" in resp.text

    @pytest.mark.asyncio
    async def test_callback_error(self, gsc_client, gsc_env):
        """OAuth error param -> 400."""
        resp = await gsc_client.get(
            "/api/gsc/callback",
            params={"code": "x", "state": "x", "error": "access_denied"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_callback_invalid_state(self, gsc_client, gsc_env):
        """Unknown state param -> 400."""
        resp = await gsc_client.get(
            "/api/gsc/callback",
            params={"code": "x", "state": "unknown"},
        )
        assert resp.status_code == 400


class TestGscStatus:
    @pytest.mark.asyncio
    async def test_not_connected_when_no_creds(self, gsc_client, gsc_env):
        """No stored creds -> connected=false."""
        resp = await gsc_client.get("/api/gsc/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["connected"] is False
        assert data["properties"] == []
        # configured-but-not-connected must be distinguishable from
        # genuinely-not-configured (503) so the panel shows the Connect button.
        assert data["configured"] is True

    @pytest.mark.asyncio
    async def test_connected_with_creds(self, gsc_client, gsc_env):
        """Stored creds -> connected with properties."""
        fake_creds_json = json.dumps({
            "token": "fake",
            "refresh_token": "r",
            "client_id": "test-id",
            "client_secret": "test-secret",
        })
        with patch("api.routers.gsc._load_creds") as mock_load, \
             patch("api.routers.gsc.list_properties") as mock_list:
            mock_load.return_value = fake_creds_json
            mock_list.return_value = [
                {
                    "site_url": "https://example.com/",
                    "permission_level": "siteOwner",
                }
            ]

            resp = await gsc_client.get("/api/gsc/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["connected"] is True
        assert len(data["properties"]) == 1
        assert data["configured"] is True

    @pytest.mark.asyncio
    async def test_status_response_contract_fields(self, gsc_client, gsc_env):
        """Frontend contract (ConnectionsPanel): /api/gsc/status always returns
        `connected` and `properties`. Locks the shape the panel reads.

        Spec: docs/pending/OLD/2026-07-06_connections-panel.md
        """
        resp = await gsc_client.get("/api/gsc/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "connected" in data
        assert "properties" in data
        assert isinstance(data["properties"], list)


class TestGscDisconnect:
    @pytest.mark.asyncio
    async def test_disconnect_clears_creds(self, gsc_client, gsc_env):
        """Disconnect removes stored creds."""
        from api.routers.gsc import _creds_cache

        _creds_cache["gsc_credentials"] = "fake"

        resp = await gsc_client.post("/api/gsc/disconnect")
        assert resp.status_code == 200
        assert resp.json() == {"status": "disconnected"}
        assert "gsc_credentials" not in _creds_cache


# ── Ingest endpoint tests ────────────────────────────────────────────────────


class TestGscIngest:
    @pytest.mark.asyncio
    async def test_ingest_writes_records(self, gsc_client, gsc_env, gsc_store):
        """Mock fetch -> writes PerformanceRecords to the ledger."""
        mock_rows = [
            {
                "url": "https://example.com/page1",
                "clicks": 10,
                "impressions": 100,
                "ctr": 0.1,
                "position": 5.0,
            },
            {
                "url": "https://example.com/page2",
                "clicks": 5,
                "impressions": 50,
                "ctr": 0.1,
                "position": 3.2,
            },
        ]

        with patch("api.routers.gsc._load_creds") as mock_load, \
             patch("api.routers.gsc.fetch_page_performance", new_callable=AsyncMock) as mock_fetch, \
             patch("api.routers.gsc._get_store") as mock_get_store:
            mock_load.return_value = json.dumps({
                "token": "fake", "refresh_token": "r",
                "client_id": "test-id", "client_secret": "test-secret",
            })
            mock_fetch.return_value = mock_rows
            mock_get_store.return_value = gsc_store

            resp = await gsc_client.post(
                "/api/gsc/ingest",
                params={
                    "site_url": "https://example.com/",
                    "job_id": "test_job",
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["ingested"] == 2
        assert data["period"] == time.strftime("%Y-%m")

        # Verify records were actually stored
        records = await gsc_store.get_performance_records(
            url="https://example.com/page1"
        )
        assert len(records) == 1
        assert records[0].gsc_clicks_mo == 10
        assert records[0].gsc_impressions_mo == 100

    @pytest.mark.asyncio
    async def test_ingest_idempotent(self, gsc_client, gsc_env, gsc_store):
        """Re-ingest for same (url, period) updates — doesn't duplicate."""
        mock_rows = [
            {
                "url": "https://example.com/page1",
                "clicks": 10,
                "impressions": 100,
                "ctr": 0.1,
                "position": 5.0,
            },
        ]
        mock_rows_v2 = [
            {
                "url": "https://example.com/page1",
                "clicks": 20,
                "impressions": 200,
                "ctr": 0.1,
                "position": 4.0,
            },
        ]

        for rows in [mock_rows, mock_rows_v2]:
            with patch("api.routers.gsc._load_creds") as mock_load, \
                 patch("api.routers.gsc.fetch_page_performance", new_callable=AsyncMock) as mock_fetch, \
                 patch("api.routers.gsc._get_store") as mock_get_store:
                mock_load.return_value = json.dumps({
                    "token": "fake", "refresh_token": "r",
                    "client_id": "test-id", "client_secret": "test-secret",
                })
                mock_fetch.return_value = rows
                mock_get_store.return_value = gsc_store

                resp = await gsc_client.post(
                    "/api/gsc/ingest",
                    params={
                        "site_url": "https://example.com/",
                        "job_id": "test_job",
                    },
                )
                assert resp.status_code == 200

        # Only 1 record (upsert, not duplicate)
        records = await gsc_store.get_performance_records(
            url="https://example.com/page1"
        )
        assert len(records) == 1
        assert records[0].gsc_clicks_mo == 20  # Updated value

    @pytest.mark.asyncio
    async def test_ingest_401_when_not_connected(self, gsc_client, gsc_env):
        """No stored creds -> 401."""
        resp = await gsc_client.post(
            "/api/gsc/ingest",
            params={"site_url": "https://example.com/", "job_id": "test"},
        )
        assert resp.status_code == 401


# ── Performance endpoint tests (M6.4 surfacing) ──────────────────────────────


class TestGscPerformance:
    @pytest.mark.asyncio
    async def test_returns_records_and_review_flag(self, gsc_client, gsc_env, gsc_store):
        """Returns ledger rows + ReviewFlag."""
        # Seed some performance records
        records = [
            PerformanceRecord(
                url="https://example.com/page",
                period="2026-05",
                gsc_clicks_mo=10,
                gsc_impressions_mo=100,
                gsc_ctr_mo=0.1,
                gsc_avg_position_mo=5.0,
            ),
        ]
        await gsc_store.save_performance_records(records)

        with patch("api.routers.gsc._get_store") as mock_get_store:
            mock_get_store.return_value = gsc_store

            resp = await gsc_client.get(
                "/api/gsc/performance",
                params={
                    "url": "https://example.com/page",
                    "health_score": 80,
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["records"]) == 1
        assert data["records"][0]["url"] == "https://example.com/page"
        assert data["records"][0]["gsc_clicks_mo"] == 10
        assert data["review_flag"] is not None
        assert "flagged" in data["review_flag"]
        assert "reasons" in data["review_flag"]

    @pytest.mark.asyncio
    async def test_empty_records(self, gsc_client, gsc_env, gsc_store):
        """No records for URL -> empty list, no review_flag."""
        with patch("api.routers.gsc._get_store") as mock_get_store:
            mock_get_store.return_value = gsc_store

            resp = await gsc_client.get(
                "/api/gsc/performance",
                params={"url": "https://example.com/missing"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["records"] == []
        assert data["review_flag"] is None

    @pytest.mark.asyncio
    async def test_vulnerable_star_flagged(self, gsc_client, gsc_env, gsc_store):
        """High impressions + low health_score -> Vulnerable Star flag."""
        records = [
            PerformanceRecord(
                url="https://example.com/star",
                period="2026-05",
                gsc_clicks_mo=5,
                gsc_impressions_mo=200,  # >= 100 threshold
                gsc_ctr_mo=0.025,
                gsc_avg_position_mo=8.0,
            ),
        ]
        await gsc_store.save_performance_records(records)

        with patch("api.routers.gsc._get_store") as mock_get_store:
            mock_get_store.return_value = gsc_store

            resp = await gsc_client.get(
                "/api/gsc/performance",
                params={
                    "url": "https://example.com/star",
                    "health_score": 40,  # < 60 threshold
                },
            )

        data = resp.json()
        assert data["review_flag"]["flagged"] is True
        assert "Vulnerable Star" in data["review_flag"]["reasons"]


# ── Auth tests ────────────────────────────────────────────────────────────────


class TestAuth:
    @pytest.mark.asyncio
    async def test_401_without_auth(self, gsc_env, monkeypatch):
        """Authed endpoints return 401 without valid token."""
        monkeypatch.setenv("AUTH_TOKEN", "real-secret-token")

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/gsc/status")
            assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_200_with_auth(self, gsc_env, monkeypatch):
        """Valid bearer token -> request passes auth."""
        monkeypatch.setenv("AUTH_TOKEN", "real-secret-token")

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/gsc/status",
                headers={"Authorization": "Bearer real-secret-token"},
            )
            # 200 (not 401) — auth passed even if no creds stored
            assert resp.status_code == 200


# ── Credential encryption tests ──────────────────────────────────────────────


class TestCredentialEncryption:
    def test_roundtrip_no_encryption_key(self):
        """Without encryption key, creds stored as raw JSON."""
        from api.routers.gsc import _encrypt_creds, _decrypt_creds

        original = json.dumps({"token": "test123"})
        encrypted = _encrypt_creds(original)
        assert encrypted == original  # No encryption
        assert _decrypt_creds(encrypted) == original

    def test_roundtrip_with_encryption_key(self, monkeypatch):
        """With encryption key, creds are Fernet-encrypted."""
        from cryptography.fernet import Fernet
        from api.routers.gsc import _encrypt_creds, _decrypt_creds

        key = Fernet.generate_key().decode()
        monkeypatch.setenv("AI_CREDS_ENCRYPTION_KEY", key)

        original = json.dumps({"token": "test123"})
        encrypted = _encrypt_creds(original)
        assert encrypted != original  # Actually encrypted
        assert _decrypt_creds(encrypted) == original  # Decrypts back
