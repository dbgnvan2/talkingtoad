"""WA1/WA2/WA4 — the URL a WordPress call actually goes to.

Spec: docs/functional-specification.md §7.8 (WA1-WA5, folded 2026-09-02)

The failure this file exists to catch, and why nothing caught it for a day:
    `WPClient.get(endpoint)` builds `{site_url}/wp-json/wp/v2/{endpoint}`, and
    every caller in `wp_audit.py` passed a path that already carried the
    namespace — so every request went to `/wp-json/wp/v2//wp/v2/...` and 404ed.
    The WordPress audit shipped 2026-09-02 and could never have returned a
    report against a real site.

    `tests/test_wp_audit.py` was green throughout because `_FakeWP` is a dict
    keyed by the same wrong strings the code passes. A stub that ACCEPTS an
    endpoint argument cannot see a URL defect: the stub and the code agreed with
    each other about a path the real client never produces (P26/P32).

    So these tests drive a real `WPClient` over a mocked TRANSPORT and assert
    the exact URL string. That is the only shape of test that can fail here.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from api.services.wp_client import WPAuthError, WPClient, invalidate_session

SITE = "https://wp.test"
LOGIN = f"{SITE}/wp-login.php"
NONCE = "abc123def456"
ADMIN_HTML = (
    "<html><script>wp.apiFetch.use( wp.apiFetch.createNonceMiddleware( "
    f'"{NONCE}" ) );</script></html>'
)


def _mock_login(mock: respx.MockRouter, *, login_url: str = LOGIN) -> None:
    """The three round trips `login()` makes, with a logged-in cookie."""
    mock.get(login_url).mock(return_value=httpx.Response(200, text="<form/>"))
    mock.post(login_url).mock(return_value=httpx.Response(
        302, headers={"location": f"{SITE}/wp-admin/",
                      "set-cookie": "wordpress_logged_in_x=y; Path=/"}))
    mock.get(f"{SITE}/wp-admin/").mock(return_value=httpx.Response(200, text=ADMIN_HTML))


@pytest.fixture(autouse=True)
def _no_session_cache():
    """The client caches sessions in a module global keyed by (login_url,
    username). Left alone, one test's session silently satisfies the next and
    the login assertions stop meaning anything."""
    invalidate_session(LOGIN, "u")
    yield
    invalidate_session(LOGIN, "u")


def _client() -> WPClient:
    return WPClient(site_url=SITE, login_url=LOGIN, username="u", password="p")


# ── The one that matters (P10) ──────────────────────────────────────────────


class TestTheUrlThatIsActuallyRequested:
    """Every endpoint the WordPress audit needs, asserted as a URL string."""

    @pytest.mark.parametrize("endpoint,expected", [
        ("plugins", f"{SITE}/wp-json/wp/v2/plugins"),
        ("themes", f"{SITE}/wp-json/wp/v2/themes"),
        ("users/me?context=edit", f"{SITE}/wp-json/wp/v2/users/me?context=edit"),
    ])
    async def test_get_requests_the_documented_url(self, endpoint, expected):
        with respx.mock(assert_all_called=False) as mock:
            _mock_login(mock)
            route = mock.get(expected).mock(return_value=httpx.Response(200, json=[]))
            async with _client() as wp:
                r = await wp.get(endpoint)
            assert r.status_code == 200
            assert route.called, (
                f"{endpoint!r} did not request {expected} — "
                f"got {[str(c.request.url) for c in mock.calls]}")

    async def test_the_namespace_is_never_emitted_twice(self):
        """The defect itself. `/wp-json/wp/v2//wp/v2/plugins` is a 404 on every
        WordPress install, and it is what shipped."""
        with respx.mock(assert_all_called=False) as mock:
            _mock_login(mock)
            mock.get(url__startswith=f"{SITE}/wp-json/").mock(
                return_value=httpx.Response(200, json=[]))
            async with _client() as wp:
                await wp.get("/wp/v2/plugins")
                await wp.get("plugins")
            urls = [str(c.request.url) for c in mock.calls
                    if "/wp-json/" in str(c.request.url)]
        assert urls, "no REST call was made"
        for u in urls:
            assert "/wp/v2//wp/v2/" not in u, f"doubled namespace: {u}"
            assert u.count("/wp/v2/") == 1, f"namespace appears twice: {u}"


class TestBothSpellingsAgree:
    """WA1 adversarial — the normalisation, not just the corrected call sites.

    Fixing `wp_audit.py` alone leaves the trap armed for the next caller who
    writes the leading-slash form, which is the natural way to write a REST
    route and is what four call sites already did."""

    @pytest.mark.parametrize("written", [
        "plugins", "/plugins", "wp/v2/plugins", "/wp/v2/plugins",
    ])
    async def test_every_spelling_issues_the_same_request(self, written):
        target = f"{SITE}/wp-json/wp/v2/plugins"
        with respx.mock(assert_all_called=False) as mock:
            _mock_login(mock)
            route = mock.get(target).mock(return_value=httpx.Response(200, json=[]))
            async with _client() as wp:
                await wp.get(written)
        assert route.called, f"{written!r} did not reach {target}"

    async def test_a_query_string_survives_normalisation(self):
        target = f"{SITE}/wp-json/wp/v2/users/me?context=edit"
        with respx.mock(assert_all_called=False) as mock:
            _mock_login(mock)
            route = mock.get(target).mock(return_value=httpx.Response(200, json={}))
            async with _client() as wp:
                await wp.get("/wp/v2/users/me?context=edit")
        assert route.called

    async def test_the_write_verbs_normalise_too(self):
        """`post`/`patch`/`delete` build the URL the same way, so they carry the
        same defect. The audit is read-only, but the fix flows are not."""
        target = f"{SITE}/wp-json/wp/v2/posts/7"
        with respx.mock(assert_all_called=False) as mock:
            _mock_login(mock)
            post = mock.post(target).mock(return_value=httpx.Response(200, json={}))
            patch = mock.patch(target).mock(return_value=httpx.Response(200, json={}))
            delete = mock.delete(target).mock(return_value=httpx.Response(200, json={}))
            async with _client() as wp:
                await wp.post("/wp/v2/posts/7", json={})
                await wp.patch("/wp/v2/posts/7", json={})
                await wp.delete("/wp/v2/posts/7")
        assert post.called and patch.called and delete.called


class TestANamespaceThatIsNotWpV2:
    """WA2 — Site Health lives in `wp-site-health/v1`, and `get()` hard-codes
    `wp/v2`. No endpoint string can reach it; the fault is structural, not a
    typo, and the silent `except Exception` around it meant a missing Site
    Health section read as 'checked, nothing to report'."""

    ROUTE = "wp-site-health/v1/tests/background-updates"

    async def test_get_route_reaches_the_other_namespace(self):
        target = f"{SITE}/wp-json/{self.ROUTE}"
        with respx.mock(assert_all_called=False) as mock:
            _mock_login(mock)
            route = mock.get(target).mock(
                return_value=httpx.Response(200, json={"status": "good"}))
            async with _client() as wp:
                r = await wp.get_route(self.ROUTE)
        assert route.called, f"get_route did not reach {target}"
        assert r.json()["status"] == "good"

    async def test_get_route_never_prefixes_wp_v2(self):
        with respx.mock(assert_all_called=False) as mock:
            _mock_login(mock)
            mock.get(url__startswith=f"{SITE}/wp-json/").mock(
                return_value=httpx.Response(200, json={}))
            async with _client() as wp:
                await wp.get_route(f"/{self.ROUTE}")
            urls = [str(c.request.url) for c in mock.calls if "/wp-json/" in str(c.request.url)]
        assert any(u.endswith(self.ROUTE) for u in urls), urls
        for u in urls:
            assert "/wp-json/wp/v2/" not in u, f"get_route went through wp/v2: {u}"

    async def test_get_route_sends_the_nonce(self):
        """It is an authenticated route like any other."""
        target = f"{SITE}/wp-json/{self.ROUTE}"
        with respx.mock(assert_all_called=False) as mock:
            _mock_login(mock)
            route = mock.get(target).mock(return_value=httpx.Response(200, json={}))
            async with _client() as wp:
                await wp.get_route(self.ROUTE)
        assert route.calls[0].request.headers.get("x-wp-nonce") == NONCE


# ── WA4 — the login error stops guessing ────────────────────────────────────


class TestTheLoginErrorNamesWhatItSaw:
    """The old message was "Check username and password in wp-credentials.json"
    for every failure. On livingsystems.ca the password was correct and the
    cause was a `login_url` that REDIRECTS: SiteGround Security 302s the pretty
    slug to `wp-login.php?sgs-token=...`, and httpx replays a 302 on a POST as a
    GET, so the credentials were dropped in flight. The message sent the reader
    to the one thing that was not wrong (P14)."""

    async def test_a_redirecting_login_url_is_named_as_such(self):
        pretty = f"{SITE}/b0w3n"
        with respx.mock(assert_all_called=False) as mock:
            mock.get(pretty).mock(return_value=httpx.Response(200, text="<form/>"))
            # The POST redirects; httpx replays it as a GET and the body is lost.
            mock.post(pretty).mock(return_value=httpx.Response(
                302, headers={"location": f"{LOGIN}?sgs-token=b0w3n"}))
            mock.get(url__startswith=LOGIN).mock(
                return_value=httpx.Response(200, text="<form/>"))
            wp = WPClient(site_url=SITE, login_url=pretty, username="u", password="p")
            with pytest.raises(WPAuthError) as exc:
                async with wp:
                    pass
        msg = str(exc.value)
        # Assert the DESTINATION, not the word "redirect": the standing causes
        # list mentions redirects on every failure, so a test that only looked
        # for that word could not fail against a client that never detected one
        # (P27 — the trap this file exists to avoid).
        assert f"{LOGIN}?sgs-token=b0w3n" in msg, (
            f"the message does not name where the POST was redirected to: {msg}")
        assert msg.count("password") <= 1, (
            f"the message still leads with the password: {msg}")

    async def test_the_message_lists_the_causes_it_cannot_distinguish(self):
        """Adversarial: the honest failure names its candidates instead of
        asserting one. A message that says only "wrong password" when it cannot
        tell is the defect, whichever cause it happens to pick."""
        with respx.mock(assert_all_called=False) as mock:
            mock.get(LOGIN).mock(return_value=httpx.Response(200, text="<form/>"))
            mock.post(LOGIN).mock(return_value=httpx.Response(200, text="<form/>"))
            with pytest.raises(WPAuthError) as exc:
                async with _client():
                    pass
        msg = str(exc.value).lower()
        for expected in ("password", "login url", "two-factor"):
            assert expected in msg, f"the message does not mention {expected!r}: {msg}"

    async def test_the_message_names_the_url_it_posted_to(self):
        with respx.mock(assert_all_called=False) as mock:
            mock.get(LOGIN).mock(return_value=httpx.Response(200, text="<form/>"))
            mock.post(LOGIN).mock(return_value=httpx.Response(200, text="<form/>"))
            with pytest.raises(WPAuthError) as exc:
                async with _client():
                    pass
        assert LOGIN in str(exc.value), (
            f"the operator cannot see which URL was tried: {exc.value}")

    async def test_a_password_that_is_simply_wrong_still_says_so(self):
        """Not a regression test for verbosity: the common cause must stay
        prominent, or the honest message is worse than the dishonest one."""
        with respx.mock(assert_all_called=False) as mock:
            mock.get(LOGIN).mock(return_value=httpx.Response(200, text="<form/>"))
            mock.post(LOGIN).mock(return_value=httpx.Response(
                200, text="<div id='login_error'>Unknown username</div><form/>"))
            with pytest.raises(WPAuthError) as exc:
                async with _client():
                    pass
        assert "password" in str(exc.value).lower()
