"""WA5 — GET /api/wp/connection: does WordPress actually answer us?

Spec: docs/functional-specification.md §7.8 (WA1-WA5, folded 2026-09-02)

Why it exists: the Connections panel tests AI providers and Google Search
Console. Nothing tested WordPress, so the first sign of a stale credential was a
failed fix or a 502 from the audit — and on 2026-09-02 the site moved its login
page and every WordPress feature broke at once with no way to see why from
inside the app.

API-contract tests come BEFORE the frontend code (CLAUDE.md). Every field
`ConnectionsPanel.jsx` reads is asserted here; if the schema drifts, this fails
rather than the panel silently rendering blanks.

| Endpoint | Frontend expects | Test |
|---|---|---|
| GET /api/wp/connection | `configured`, `authenticated`, `site_url`, `message` | `test_response_schema_is_what_the_panel_reads` |
| GET /api/wp/connection | `roles`, `capabilities`, `can_run_fixes`, `can_run_wp_audit` | `test_a_working_connection_reports_capabilities` |
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from api.services.wp_client import WPAuthError

ENDPOINT = "/api/wp/connection"


class _Resp:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _FakeWP:
    """Stands in for a logged-in WPClient.

    Deliberately NOT used to assert URLs — that is what
    tests/test_wp_client_routes.py does over a real transport, precisely
    because a stub cannot see a URL defect (P26/P32). Here the client is
    already proven and the endpoint's own behaviour is what is in doubt.
    """

    def __init__(self, me: _Resp | None = None, *, raises: Exception | None = None):
        self.me = me or _Resp(200, {
            "id": 11, "roles": ["administrator"],
            "capabilities": {"edit_posts": True, "edit_pages": True,
                             "upload_files": True, "manage_options": True},
        })
        self.raises = raises
        self.calls: list[str] = []

    async def __aenter__(self):
        if self.raises:
            raise self.raises
        return self

    async def __aexit__(self, *_a):
        return None

    async def get(self, endpoint, **_kw):
        self.calls.append(endpoint)
        return self.me


@pytest.fixture
def creds(tmp_path, monkeypatch):
    """A credentials file on disk, pointed at by both the router and the
    domain-validation helper."""
    path = tmp_path / "wp-credentials.json"
    path.write_text(json.dumps({
        "site_url": "https://example.com",
        "login_url": "https://example.com/wp-login.php",
        "username": "u", "password": "p",
    }))
    monkeypatch.setattr("api.routers.wp_connection_router._CREDS_PATH", path)
    monkeypatch.setattr("api.routers.fixes_shared._CREDS_PATH", path)
    return path


def _patch_client(fake):
    return patch("api.routers.wp_connection_router.WPClient.from_credentials_file",
                 return_value=fake)


# ── Contract ────────────────────────────────────────────────────────────────


class TestResponseContract:
    async def test_response_schema_is_what_the_panel_reads(
            self, api_client, auth_headers, creds):
        with _patch_client(_FakeWP()):
            r = await api_client.get(ENDPOINT, headers=auth_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        for field in ("configured", "authenticated", "site_url", "message"):
            assert field in body, f"ConnectionsPanel reads `{field}`; it is absent"
        assert isinstance(body["configured"], bool)
        assert isinstance(body["authenticated"], bool)
        assert isinstance(body["message"], str) and body["message"].strip()

    async def test_a_working_connection_reports_capabilities(
            self, api_client, auth_headers, creds):
        with _patch_client(_FakeWP()):
            r = await api_client.get(ENDPOINT, headers=auth_headers)
        body = r.json()
        assert body["configured"] is True and body["authenticated"] is True
        assert body["roles"] == ["administrator"]
        assert body["capabilities"]["edit_posts"] is True
        assert body["can_run_fixes"] is True
        assert body["can_run_wp_audit"] is True
        assert body["site_url"] == "https://example.com"

    async def test_it_calls_users_me_and_nothing_else(self, api_client, auth_headers, creds):
        """Read-only by construction — a connection check must never write."""
        fake = _FakeWP()
        with _patch_client(fake):
            await api_client.get(ENDPOINT, headers=auth_headers)
        assert fake.calls == ["users/me?context=edit"], fake.calls


# ── The states the panel has to render ──────────────────────────────────────


class TestTheFailureStatesAreDistinguishable:
    """The whole point: "not configured", "configured but rejected" and "logged
    in but under-privileged" are three different problems with three different
    fixes. Collapsing them into one red box would rebuild the error message
    WA4 exists to remove."""

    async def test_no_credentials_file_is_not_configured_not_an_error(
            self, api_client, auth_headers, tmp_path, monkeypatch):
        missing = tmp_path / "absent.json"
        monkeypatch.setattr("api.routers.wp_connection_router._CREDS_PATH", missing)
        monkeypatch.setattr("api.routers.fixes_shared._CREDS_PATH", missing)
        r = await api_client.get(ENDPOINT, headers=auth_headers)
        assert r.status_code == 200, "an unconfigured integration is a state, not a fault"
        body = r.json()
        assert body["configured"] is False
        assert body["authenticated"] is False
        assert "credential" in body["message"].lower()

    async def test_a_rejected_login_reports_the_client_message_verbatim(
            self, api_client, auth_headers, creds):
        """WA4's diagnosis has to reach the screen, or it only helps whoever
        reads the server log."""
        detail = ("Login failed at https://example.com/wp-login.php — the POST was "
                  "redirected, so the credentials were not submitted.")
        with _patch_client(_FakeWP(raises=WPAuthError(detail))):
            r = await api_client.get(ENDPOINT, headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["configured"] is True and body["authenticated"] is False
        assert "redirected" in body["message"], body["message"]

    async def test_an_editor_account_is_authenticated_but_cannot_audit(
            self, api_client, auth_headers, creds):
        """Adversarial — the correct-looking-but-wrong result. An editor logs in
        fine and can run title/heading fixes, but `/wp/v2/plugins` needs an
        administrator. Reporting a bare green tick here sends the operator to
        the audit button to meet a 403 they were just told would not happen."""
        me = _Resp(200, {"id": 4, "roles": ["editor"],
                         "capabilities": {"edit_posts": True, "edit_pages": True,
                                          "upload_files": True, "manage_options": False}})
        with _patch_client(_FakeWP(me)):
            r = await api_client.get(ENDPOINT, headers=auth_headers)
        body = r.json()
        assert body["authenticated"] is True
        assert body["can_run_fixes"] is True
        assert body["can_run_wp_audit"] is False, (
            "an editor cannot list plugins; the panel must not promise the audit")

    async def test_a_403_on_users_me_is_authenticated_false_not_a_crash(
            self, api_client, auth_headers, creds):
        with _patch_client(_FakeWP(_Resp(403, {}))):
            r = await api_client.get(ENDPOINT, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["authenticated"] is False

    async def test_an_unexpected_status_names_it_rather_than_guessing(
            self, api_client, auth_headers, creds):
        """A 404 here means the REST route is wrong or REST is disabled — the
        defect this whole spec is about. It must never read as a pass (P2)."""
        with _patch_client(_FakeWP(_Resp(404, {}))):
            r = await api_client.get(ENDPOINT, headers=auth_headers)
        body = r.json()
        assert body["authenticated"] is False
        assert "404" in body["message"], body["message"]

    async def test_a_transport_failure_is_reported_not_raised(
            self, api_client, auth_headers, creds):
        with _patch_client(_FakeWP(raises=httpx.ConnectError("dns"))):
            r = await api_client.get(ENDPOINT, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["authenticated"] is False


# ── Auth and domain safety ──────────────────────────────────────────────────


class TestAuthAndDomain:
    async def test_it_requires_a_token(self, api_client, creds):
        r = await api_client.get(ENDPOINT)
        assert r.status_code in (401, 403), (
            "the endpoint logs in to WordPress; it cannot answer anonymously")

    async def test_a_job_id_from_another_domain_is_refused(
            self, api_client, auth_headers, creds, test_store):
        """CLAUDE.md: every WP-touching endpoint domain-validates. With no job
        there is nothing to mismatch — the endpoint can only ever contact the
        site named in the credentials — but when a caller names a job, the
        job's domain must match or this becomes a way to confirm credentials
        while looking at somebody else's crawl."""
        from api.models.job import CrawlJob

        await test_store.create_job(CrawlJob(job_id="other", target_url="https://other.org/"))
        with _patch_client(_FakeWP()):
            r = await api_client.get(f"{ENDPOINT}?job_id=other", headers=auth_headers)
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "DOMAIN_MISMATCH"

    async def test_a_matching_job_id_is_allowed(
            self, api_client, auth_headers, creds, test_store):
        from api.models.job import CrawlJob

        await test_store.create_job(CrawlJob(job_id="same", target_url="https://example.com/"))
        with _patch_client(_FakeWP()):
            r = await api_client.get(f"{ENDPOINT}?job_id=same", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["authenticated"] is True

    async def test_the_response_never_carries_the_password(
            self, api_client, auth_headers, creds):
        with _patch_client(_FakeWP()):
            r = await api_client.get(ENDPOINT, headers=auth_headers)
        assert "p" not in r.json().get("password", "x"), "a password field exists"
        body = r.text.lower()
        assert "password" not in body, f"the payload mentions a password: {r.text[:200]}"
