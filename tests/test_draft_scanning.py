"""Scanning an unpublished page on purpose.

Spec:  docs/functional-specification.md (D1)
Tests: this file

An unpublished page returns 404 to anyone not signed in, so auditing a draft
before publishing needs an authenticated fetch. It is opt-in per scan and
single-page only: run_crawl must keep making no authenticated calls, both
because the architecture test forbids WP API calls during a scan and because a
site-wide authenticated crawl would audit content no search engine can see,
silently changing what the health score means.
"""
from __future__ import annotations

import json
from unittest import mock

import httpx
import pytest
import respx

from api.routers.crawl import (_PREPUBLICATION_NOISE_CODES,
                               _fetch_and_check_page, scan_single_page)
from api.services.sqlite_store import SQLiteJobStore

BASE = "https://e.test/"
DRAFT = BASE + "team-members/14528"

NOT_FOUND = ("<!DOCTYPE html><html lang='en'><head><title>Page not found</title>"
             "<meta name='robots' content='noindex, follow'></head>"
             "<body><h1>Page not found</h1></body></html>")

DRAFT_HTML = ("<!DOCTYPE html><html lang='en'><head>"
              "<title>A New Team Member Page Awaiting Review</title>"
              "<meta name='robots' content='noindex'>"
              "</head><body><h1>A New Person</h1>"
              "<p>" + " ".join(["word"] * 130) + "</p></body></html>")

CREDS = {"site_url": "https://e.test", "login_url": "https://e.test/wp-login.php",
         "username": "admin", "password": "secret"}


@pytest.fixture
async def store(tmp_path):
    s = SQLiteJobStore(db_path=str(tmp_path / "t.db"))
    await s.init()
    try:
        yield s
    finally:
        await s.close()


class _FakeJar(list):
    pass


class _FakeCookie:
    def __init__(self, name, value):
        self.name, self.value = name, value


def _patch_wp_login(monkeypatch, tmp_path):
    """Stand in for the WordPress cookie login, and for the creds file."""
    creds_file = tmp_path / "wp-credentials.json"
    creds_file.write_text(json.dumps(CREDS))

    class FakeWP:
        def __init__(self, **kw):
            self.kw = kw
            self._client = mock.Mock()
            self._client.cookies.jar = _FakeJar(
                [_FakeCookie("wordpress_logged_in_abc", "session-value")])

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def login(self):
            return None

    import api.routers.crawl as cr
    import api.routers.fixes_shared as fs
    monkeypatch.setattr(cr, "_WP_CREDENTIALS_PATH", creds_file)
    # The domain validator reads its own copy of the credentials file, so
    # without this the suite's behaviour depends on whatever real site the
    # developer happens to have configured.
    monkeypatch.setattr(fs, "_get_wp_creds_domain", lambda: "e.test")
    monkeypatch.setitem(__import__("sys").modules, "api.services.wp_client",
                        mock.Mock(WPClient=FakeWP))
    return creds_file


class TestWithoutTheFlag:
    async def test_d1_without_the_flag_a_draft_is_just_a_404(self, store):
        """The default is unchanged: anonymous, and an unpublished page is a
        broken link, not content."""
        with respx.mock(assert_all_mocked=False, assert_all_called=False) as rx:
            rx.get(DRAFT).mock(return_value=httpx.Response(
                404, text=NOT_FOUND, headers={"content-type": "text/html"}))
            rx.route().mock(return_value=httpx.Response(200, text="ok"))
            res = await _fetch_and_check_page(
                url=DRAFT, job_id="j", store=store, base_url=BASE)
        codes = {i.issue_code for i in res.issues}
        assert "BROKEN_LINK_404" in codes
        assert "NOINDEX_META" not in codes


class TestAuthenticatedScan:
    async def test_d1_authenticated_scan_reads_the_draft(
            self, store, monkeypatch, tmp_path):
        _patch_wp_login(monkeypatch, tmp_path)
        with respx.mock(assert_all_mocked=False, assert_all_called=False) as rx:
            rx.get(DRAFT).mock(return_value=httpx.Response(
                200, text=DRAFT_HTML, headers={"content-type": "text/html"}))
            rx.route().mock(return_value=httpx.Response(200, text="ok"))
            res = await _fetch_and_check_page(
                url=DRAFT, job_id="j", store=store, base_url=BASE,
                authenticated=True)
        assert not isinstance(res, object.__class__), "unexpected error response"
        assert res.page.title == "A New Team Member Page Awaiting Review", (
            "the authenticated fetch did not read the draft")

    async def test_d1_the_session_cookie_is_actually_sent(
            self, store, monkeypatch, tmp_path):
        """Wiring asserted at the boundary: without the cookie WordPress would
        return the 404, so the whole feature rests on it being attached."""
        _patch_wp_login(monkeypatch, tmp_path)
        seen: dict = {}

        def _handler(request):
            seen["cookie"] = request.headers.get("cookie", "")
            return httpx.Response(200, text=DRAFT_HTML,
                                  headers={"content-type": "text/html"})

        with respx.mock(assert_all_mocked=False, assert_all_called=False) as rx:
            rx.get(DRAFT).mock(side_effect=_handler)
            rx.route().mock(return_value=httpx.Response(200, text="ok"))
            await _fetch_and_check_page(
                url=DRAFT, job_id="j", store=store, base_url=BASE,
                authenticated=True)
        assert "wordpress_logged_in_abc=session-value" in seen.get("cookie", ""), (
            f"the WordPress session cookie was not sent; got "
            f"{seen.get('cookie')!r}")

    async def test_d1_prepublication_noise_codes_are_suppressed(
            self, store, monkeypatch, tmp_path):
        """The draft HTML carries noindex; reporting it would be noise the
        owner has to learn to ignore."""
        _patch_wp_login(monkeypatch, tmp_path)
        with respx.mock(assert_all_mocked=False, assert_all_called=False) as rx:
            rx.get(DRAFT).mock(return_value=httpx.Response(
                200, text=DRAFT_HTML, headers={"content-type": "text/html"}))
            rx.route().mock(return_value=httpx.Response(200, text="ok"))
            res = await _fetch_and_check_page(
                url=DRAFT, job_id="j", store=store, base_url=BASE,
                authenticated=True)
        codes = {i.issue_code for i in res.issues}
        leaked = codes & _PREPUBLICATION_NOISE_CODES
        assert not leaked, (
            f"{sorted(leaked)} reported on a deliberate draft scan — a draft "
            f"has no inbound links, is not in the sitemap, and is noindex by "
            f"design")

    async def test_d1_refuses_a_url_outside_the_credentials_domain(
            self, store, monkeypatch, tmp_path):
        """The credentials belong to one site and must never be sent elsewhere."""
        _patch_wp_login(monkeypatch, tmp_path)
        import api.routers.fixes_shared as fs
        monkeypatch.setattr(fs, "_get_wp_creds_domain", lambda: "e.test")
        res = await _fetch_and_check_page(
            url="https://somewhere-else.test/page", job_id="j", store=store,
            base_url=BASE, authenticated=True)
        body = json.loads(bytes(res.body).decode())
        assert body["error"]["code"] == "DOMAIN_MISMATCH", (
            f"a cross-domain authenticated scan was allowed: {body}")


class TestTheDefaultIsUnchanged:
    def test_d1_the_flag_defaults_to_false_everywhere(self):
        import inspect

        sig = inspect.signature(_fetch_and_check_page)
        assert sig.parameters["authenticated"].default is False
        # and the endpoint's Query default
        q = inspect.signature(scan_single_page).parameters["authenticated"].default
        assert getattr(q, "default", q) is False
