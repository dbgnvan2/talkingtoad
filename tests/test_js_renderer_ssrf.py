"""The JS renderer checks every hop and every browser request, not just the entry URL.

Spec:  CLAUDE.md, Security Defaults — all outbound fetches go through
       is_ssrf_safe, blocked at start AND on every redirect hop.
Tests: this file

run_js_render_checks already refused an internal *entry* URL. Two paths went
past that check anyway:

  _fetch_raw            used a bare client with follow_redirects=True, so a
                        public host answering 302 to an internal address was
                        followed.
  _render_with_playwright  ran a full browser. A browser is not one fetch: it
                        follows redirects, loads every subresource, and runs
                        the page's JavaScript, so a perfectly public page could
                        issue fetch("http://169.254.169.254/...") and read cloud
                        instance credentials from the crawler's network position.
                        Guarding the URL we typed in protects nothing there.

Every internal target below is mocked to SUCCEED. Asserting "no data came back"
against an unroutable address passes whether the guard refused the request or
the connection merely failed — it cannot fail against the defect it names. The
assertion is that the request was never made.
"""
from __future__ import annotations

import httpx
import pytest
import respx

from api.services.js_renderer import _fetch_raw, _guard_browser_request

INTERNAL = [
    "http://169.254.169.254/latest/meta-data/iam/security-credentials/",
    "http://localhost:8000/admin",
    "http://10.0.0.5/internal",
    "http://127.0.0.1/x",
    "http://192.168.1.1/router",
]


class TestFetchRawHops:
    @pytest.mark.asyncio
    async def test_ssrf_fetch_raw_does_not_follow_a_redirect_inward(self):
        with respx.mock:
            respx.get("https://example.com/page").mock(return_value=httpx.Response(
                302, headers={"location": "http://169.254.169.254/creds"}))
            inner = respx.get("http://169.254.169.254/creds").mock(
                return_value=httpx.Response(200, text="SECRET-CREDENTIALS"))
            try:
                html = await _fetch_raw("https://example.com/page", "UA")
            except Exception:
                html = ""
        assert not inner.called, (
            "the renderer followed a redirect to the cloud metadata service")
        assert "SECRET" not in html

    @pytest.mark.asyncio
    async def test_ssrf_fetch_raw_still_reads_a_public_page(self):
        """The guard must not break the feature it protects."""
        with respx.mock:
            respx.get("https://example.com/ok").mock(
                return_value=httpx.Response(200, text="<html>hello</html>"))
            html = await _fetch_raw("https://example.com/ok", "UA")
        assert "hello" in html


class _FakeRequest:
    def __init__(self, url: str) -> None:
        self.url = url


class _FakeRoute:
    """Records what the guard decided, so the decision is asserted directly
    rather than inferred from a browser that may not be installed."""

    def __init__(self) -> None:
        self.continued = False
        self.aborted = False

    async def continue_(self) -> None:
        self.continued = True

    async def abort(self) -> None:
        self.aborted = True


class TestBrowserRequestGuard:
    @pytest.mark.parametrize("url", INTERNAL)
    @pytest.mark.asyncio
    async def test_ssrf_browser_request_to_internal_host_is_aborted(self, url):
        route = _FakeRoute()
        await _guard_browser_request(route, _FakeRequest(url))
        assert route.aborted and not route.continued, (
            f"the browser was allowed to request {url}. page.goto follows "
            f"redirects, loads subresources and runs the page's JavaScript, so "
            f"the entry-URL check cannot cover this.")

    @pytest.mark.asyncio
    async def test_ssrf_browser_request_to_public_host_is_allowed(self):
        route = _FakeRoute()
        await _guard_browser_request(route, _FakeRequest("https://example.com/a.js"))
        assert route.continued and not route.aborted

    @pytest.mark.asyncio
    async def test_ssrf_a_guard_that_errors_denies(self, monkeypatch):
        """Fail closed. A guard that raises must not fall through to allow."""
        import api.services.js_renderer as jr

        def boom(_url):
            raise RuntimeError("resolver exploded")

        monkeypatch.setattr(jr, "is_ssrf_safe", boom)
        route = _FakeRoute()
        await _guard_browser_request(route, _FakeRequest("https://example.com/x"))
        assert route.aborted and not route.continued, (
            "the guard raised and the request was allowed through")

    @pytest.mark.asyncio
    async def test_ssrf_guard_is_actually_installed_on_the_page(self, monkeypatch):
        """P25 — a guard that exists but is never attached is decoration.

        Asserted behaviourally against a fake browser, not by grepping the
        source: a source assertion breaks green the moment the name changes.
        """
        import api.services.js_renderer as jr

        routes: list[tuple[str, object]] = []
        visited: list[str] = []

        class FakePage:
            async def route(self, pattern, handler):
                routes.append((pattern, handler))

            async def goto(self, url, wait_until=None):
                visited.append(url)

            async def content(self):
                return "<html>rendered</html>"

        class FakeBrowser:
            async def new_page(self):
                return FakePage()

            async def close(self):
                pass

        class FakeChromium:
            async def launch(self, headless=True):
                return FakeBrowser()

        class FakePW:
            chromium = FakeChromium()

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

        monkeypatch.setattr(jr, "HAS_PLAYWRIGHT", True)
        monkeypatch.setattr(jr, "async_playwright", lambda: FakePW(), raising=False)

        html = await jr._render_with_playwright("https://example.com/")

        assert html == "<html>rendered</html>", "the fake browser did not run"
        assert routes, (
            "_render_with_playwright registered no route handler, so every "
            "request the browser makes — redirects, subresources, and any "
            "fetch() the page's own JavaScript issues — goes unchecked")
        pattern, handler = routes[0]
        assert pattern == "**/*", (
            f"the handler is scoped to {pattern!r}; it must see every request")
        assert handler is jr._guard_browser_request

        # and the registered handler must actually deny an internal target
        route = _FakeRoute()
        await handler(route, _FakeRequest("http://169.254.169.254/creds"))
        assert route.aborted, "the registered handler does not block"

    @pytest.mark.asyncio
    async def test_ssrf_guard_is_installed_before_navigation(self, monkeypatch):
        """Order matters: routing attached after goto() would leave the
        navigation itself — and its redirects — unguarded."""
        import api.services.js_renderer as jr

        events: list[str] = []

        class FakePage:
            async def route(self, pattern, handler):
                events.append("route")

            async def goto(self, url, wait_until=None):
                events.append("goto")

            async def content(self):
                return "<html></html>"

        class FakeBrowser:
            async def new_page(self):
                return FakePage()

            async def close(self):
                pass

        class FakeChromium:
            async def launch(self, headless=True):
                return FakeBrowser()

        class FakePW:
            chromium = FakeChromium()

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

        monkeypatch.setattr(jr, "HAS_PLAYWRIGHT", True)
        monkeypatch.setattr(jr, "async_playwright", lambda: FakePW(), raising=False)
        await jr._render_with_playwright("https://example.com/")

        assert events.index("route") < events.index("goto"), (
            f"routing was attached after navigation ({events}) — the goto "
            f"itself, and every redirect it follows, would be unguarded")
