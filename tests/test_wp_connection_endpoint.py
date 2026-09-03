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
        if endpoint.startswith("plugins"):
            return getattr(self, "plugins", _Resp(200, [{"plugin": "x"}]))
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

    async def test_it_makes_only_read_only_calls(self, api_client, auth_headers, creds):
        """Read-only by construction — a connection check must never write.

        Two GETs since D4: the account, then a one-row `plugins` probe, because
        `allcaps` is the role map rather than the effective capability and the
        panel must not promise an audit that 403s."""
        fake = _FakeWP()
        with _patch_client(fake):
            await api_client.get(ENDPOINT, headers=auth_headers)
        assert fake.calls == ["users/me?context=edit", "plugins?per_page=1"], fake.calls
        assert all(not hasattr(fake, verb) for verb in ("post", "patch", "delete"))


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
                                          "upload_files": True,
                                          "manage_options": False,
                                          "activate_plugins": False}})
        fake = _FakeWP(me)
        fake.plugins = _Resp(403, {})      # what an editor actually gets (D4)
        with _patch_client(fake):
            r = await api_client.get(ENDPOINT, headers=auth_headers)
        body = r.json()
        assert body["authenticated"] is True
        assert body["can_run_fixes"] is True
        assert body["can_run_wp_audit"] is False, (
            "an editor cannot list plugins; the panel must not promise the audit")

    async def test_the_audit_capability_is_the_one_the_plugins_route_gates_on(
            self, api_client, auth_headers, creds):
        """`WP_REST_Plugins_Controller::get_items_permissions_check` gates on
        `activate_plugins`, not `manage_options`. Checking the wrong one is the
        very failure the fix/audit split exists to prevent — a green tick, then
        a 403 from the button it promised."""
        me = _Resp(200, {"id": 5, "roles": ["custom"],
                         "capabilities": {"edit_posts": True, "edit_pages": True,
                                          "upload_files": True,
                                          "manage_options": True,
                                          "activate_plugins": False}})
        fake = _FakeWP(me)
        fake.plugins = _Resp(403, {})
        with _patch_client(fake):
            r = await api_client.get(ENDPOINT, headers=auth_headers)
        body = r.json()
        assert body["can_run_fixes"] is True
        assert body["can_run_wp_audit"] is False, (
            "manage_options is not what /wp/v2/plugins checks")

    async def test_the_audit_capability_is_probed_not_inferred(self, api_client, auth_headers, creds):
        """D4 (2026-09-03). `users/me` returns `allcaps` — the raw role map,
        unfiltered by `map_meta_cap` — so a role plugin or a multisite subsite
        that filters `activate_plugins` at the meta layer still reports it true,
        and the panel promises an audit that then 403s. That is exactly the
        failure the fix/audit split exists to prevent (P6: a status trusted
        without exercising the artifact).

        One extra read-only call settles it."""
        me = _Resp(200, {"id": 1, "roles": ["administrator"],
                         "capabilities": {"edit_posts": True, "edit_pages": True,
                                          "upload_files": True,
                                          "manage_options": True,
                                          "activate_plugins": True}})
        fake = _FakeWP(me)
        fake.plugins = _Resp(403, {})      # WordPress disagrees with allcaps
        with _patch_client(fake):
            r = await api_client.get(ENDPOINT, headers=auth_headers)
        body = r.json()
        assert body["authenticated"] is True
        assert body["can_run_wp_audit"] is False, (
            "allcaps said activate_plugins; WordPress refused the plugin list")

    async def test_a_working_admin_still_reports_true(self, api_client, auth_headers, creds):
        """Adversarial: the probe must not turn every account into a 'no'."""
        with _patch_client(_FakeWP()):
            r = await api_client.get(ENDPOINT, headers=auth_headers)
        assert r.json()["can_run_wp_audit"] is True

    async def test_the_probe_is_read_only(self, api_client, auth_headers, creds):
        fake = _FakeWP()
        with _patch_client(fake):
            await api_client.get(ENDPOINT, headers=auth_headers)
        assert fake.calls == ["users/me?context=edit", "plugins?per_page=1"], fake.calls

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

    async def test_a_200_that_is_not_wordpress_json_is_not_a_capability_verdict(
            self, api_client, auth_headers, creds):
        """P2/P14. A cache interstitial, a WAF challenge or a maintenance page
        answers 200 with HTML. `me.json()` raised, `body` fell back to `{}`, and
        every capability read False — so the panel rendered, in the GREEN box,
        "Connected, but this account is missing edit_posts, edit_pages,
        upload_files, so the fixes will fail": a specific, wrong, actionable
        verdict about the operator's WordPress account, from a response that
        established nothing. WA3 set the rule for the audit three files over;
        a 200 that does not parse establishes nothing either."""
        class _Html:
            status_code = 200

            def json(self):
                raise ValueError("not json")

        with _patch_client(_FakeWP(_Html())):
            r = await api_client.get(ENDPOINT, headers=auth_headers)
        body = r.json()
        assert body["authenticated"] is False, (
            "an unparseable body was reported as an authenticated account")
        assert "edit_posts" not in body["message"], (
            f"a capability verdict was invented from a non-JSON body: {body['message']}")

    async def test_a_200_json_that_is_not_a_user_object_is_refused(
            self, api_client, auth_headers, creds):
        """Adversarial sibling: valid JSON, wrong shape (a REST error envelope,
        or a list). No `id` means this is not the account description we asked
        for, and its absent capabilities are not a finding about the account."""
        for payload in ({"code": "rest_forbidden", "message": "no"}, [], "text"):
            with _patch_client(_FakeWP(_Resp(200, payload))):
                r = await api_client.get(ENDPOINT, headers=auth_headers)
            assert r.json()["authenticated"] is False, payload

    async def test_a_transport_failure_is_reported_not_raised(
            self, api_client, auth_headers, creds):
        with _patch_client(_FakeWP(raises=httpx.ConnectError("dns"))):
            r = await api_client.get(ENDPOINT, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["authenticated"] is False


class TestItActuallyTestsTheCredentials:
    """The finding that matters (P6). `WPClient.login()` returns early on a
    session-cache hit — restoring a cookie and a nonce, never touching
    `self.password` — and the cache lives 10 hours. So the endpoint whose whole
    job is "do the stored credentials still work" answered from a cookie: change
    the password in wp-credentials.json with a warm cache and it still reported
    "Connected. This account can run the fixes and the configuration audit."

    A connection TEST must do the round trip it claims to."""

    async def test_the_session_cache_is_cleared_before_the_check(
            self, api_client, auth_headers, creds, monkeypatch):
        import api.routers.wp_connection_router as mod

        cleared: list[tuple] = []
        monkeypatch.setattr(mod, "invalidate_session",
                            lambda login_url, username: cleared.append((login_url, username)))
        with _patch_client(_FakeWP()):
            r = await api_client.get(ENDPOINT, headers=auth_headers)
        assert r.status_code == 200
        assert cleared == [("https://example.com/wp-login.php", "u")], (
            "the check answered from whatever session was already cached — "
            f"invalidate_session calls: {cleared}")

    async def test_a_real_client_performs_the_login_round_trip(
            self, api_client, auth_headers, tmp_path, monkeypatch):
        """End to end through a real WPClient over a mocked transport: a warm
        cache must not spare the POST. A stubbed client cannot show this — the
        cache lives inside the client this endpoint would otherwise reuse.

        Driven over HTTP rather than by calling the function directly: the
        rate-limit decorator rejects a non-Request argument and is disabled in
        tests, so a direct call would exercise a path production never takes
        (P27)."""
        import respx

        from api.services.wp_client import WPClient

        site, login = "https://wp.test", "https://wp.test/wp-login.php"
        path = tmp_path / "wp-credentials.json"
        path.write_text(json.dumps({"site_url": site, "login_url": login,
                                    "username": "u", "password": "p"}))
        monkeypatch.setattr("api.routers.wp_connection_router._CREDS_PATH", path)

        admin = ('<html><script>wp.apiFetch.use( wp.apiFetch.createNonceMiddleware( '
                 '"abc123" ) );</script></html>')
        with respx.mock(assert_all_called=False) as mock:
            mock.get(login).mock(return_value=httpx.Response(200, text="<form/>"))
            post = mock.post(login).mock(return_value=httpx.Response(
                302, headers={"location": f"{site}/wp-admin/",
                              "set-cookie": "wordpress_logged_in_x=y; Path=/"}))
            mock.get(f"{site}/wp-admin/").mock(return_value=httpx.Response(200, text=admin))
            mock.get(f"{site}/wp-json/wp/v2/users/me?context=edit").mock(
                return_value=httpx.Response(200, json={"id": 1, "roles": ["administrator"],
                                                       "capabilities": {}}))
            # Warm the cache the way a prior fix or audit would have.
            async with WPClient(site_url=site, login_url=login, username="u", password="p"):
                pass
            before = post.call_count
            r = await api_client.get(ENDPOINT, headers=auth_headers)
            after = post.call_count

        assert r.status_code == 200, r.text[:200]
        assert r.json()["authenticated"] is True, r.json()["message"]
        assert after == before + 1, (
            "the connection check reused a cached session instead of logging in — "
            "a stale password would still report Connected")


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
            self, api_client, auth_headers, tmp_path, monkeypatch):
        """The first version asserted `"p" not in body.get("password","x")` —
        vacuously true — and then that the WORD "password" was absent, which
        only held because the configured path happens not to use it. Assert the
        VALUE, with a value distinctive enough to find (P26)."""
        secret = "Sup3rSecretW0rd-notinanymessage"
        path = tmp_path / "wp-credentials.json"
        path.write_text(json.dumps({
            "site_url": "https://example.com",
            "login_url": "https://example.com/wp-login.php",
            "username": "u", "password": secret,
        }))
        monkeypatch.setattr("api.routers.wp_connection_router._CREDS_PATH", path)
        monkeypatch.setattr("api.routers.fixes_shared._CREDS_PATH", path)

        for fake in (_FakeWP(), _FakeWP(raises=WPAuthError(f"tried with {secret}"))):
            with _patch_client(fake):
                r = await api_client.get(ENDPOINT, headers=auth_headers)
            assert secret not in r.text, (
                f"the password reached the payload: {r.text[:300]}")
