"""Image fetches are SSRF-guarded, like every other outbound call.

Spec:  CLAUDE.md, Security Defaults — all outbound fetches go through
       api/crawler/fetcher.py::is_ssrf_safe, blocked at start and on every
       redirect hop.
Tests: this file

Image URLs come out of crawled HTML, so they are exactly as trustworthy as the
page that carried them. Both image passes — the HEAD metadata pass and the IM1
dimension pass — used the plain crawl client, which follows redirects and
checks nothing. The dimension pass raised the stakes: HEAD leaks little, a GET
returns the whole body, so a page could name http://169.254.169.254/... as an
image src and have the crawler fetch cloud instance credentials.
"""
from __future__ import annotations

import httpx
import pytest
import respx

from api.crawler.engine import CrawlSettings, _fetch_image_dimensions, run_crawl
from api.crawler.fetcher import make_ssrf_guarded_client

BASE = "https://example.com/"


def _png(w: int, h: int) -> bytes:
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (10, 90, 10)).save(buf, format="PNG")
    return buf.getvalue()


class TestGuardedClientRefusesInternalTargets:
    """Each internal URL is mocked to return a PERFECTLY GOOD IMAGE.

    That is the whole design of these tests. _fetch_image_dimensions returns {}
    on any failure, so asserting {} against an unmocked internal address passes
    whether the guard refused the request or the connection simply failed —
    it cannot fail against the defect it names. Mutation-checked: neutralising
    the guard hook left the earlier version of these tests green.

    With the target mocked to succeed, {} can only mean the request was never
    made.
    """

    INTERNAL = [
        "http://169.254.169.254/latest/meta-data/iam/security-credentials/img.png",
        "http://localhost:8000/x.png",
        "http://10.0.0.5/logo.png",
        "http://127.0.0.1/y.png",
        "http://192.168.1.1/router.png",
    ]

    @pytest.mark.parametrize("url", INTERNAL)
    @pytest.mark.asyncio
    async def test_ssrf_internal_image_is_never_requested(self, url):
        with respx.mock:
            route = respx.get(url).mock(return_value=httpx.Response(
                200, content=_png(300, 200),
                headers={"content-type": "image/png"}))
            async with make_ssrf_guarded_client() as client:
                _, meta = await _fetch_image_dimensions(url, client)
        assert not route.called, (
            f"the crawler issued a request to {url}. The SSRF guard must "
            f"refuse an internal target before it is fetched.")
        assert meta == {}, f"measured an internal target: {meta!r}"

    @pytest.mark.asyncio
    async def test_ssrf_public_host_redirecting_inward_is_refused(self):
        """The hop case: a public image URL that 302s to the metadata service.

        Mutation-checked, and the result is worth recording: disabling EITHER
        hook alone leaves this green, because httpx runs the request hook again
        for the redirected request, so each guard independently refuses this.
        It fails only with both disabled. That is genuine defence in depth, not
        a dead guard — but it does mean no single-hook mutation can prove this
        test, and claiming otherwise would be a false assurance.
        """
        with respx.mock:
            respx.get(f"{BASE}innocent.png").mock(return_value=httpx.Response(
                302, headers={"location": "http://169.254.169.254/creds.png"}))
            inner = respx.get("http://169.254.169.254/creds.png").mock(
                return_value=httpx.Response(200, content=_png(10, 10),
                                            headers={"content-type": "image/png"}))
            async with make_ssrf_guarded_client() as client:
                _, meta = await _fetch_image_dimensions(f"{BASE}innocent.png",
                                                        client)
        assert not inner.called, (
            "a redirect to an internal host was followed — the guard must "
            "check every hop, not only the first request")
        assert meta == {}

    @pytest.mark.asyncio
    async def test_ssrf_a_public_image_still_measures(self):
        """The guard must not simply break the feature it protects."""
        with respx.mock:
            respx.get(f"{BASE}ok.png").mock(return_value=httpx.Response(
                200, content=_png(300, 200),
                headers={"content-type": "image/png"}))
            async with make_ssrf_guarded_client() as client:
                _, meta = await _fetch_image_dimensions(f"{BASE}ok.png", client)
        assert meta["width"] == 300 and meta["height"] == 200


class TestTheCrawlUsesTheGuardedClient:
    """Wiring, asserted by what the DOWNLOAD actually did.

    The first version of this test asserted that a guarded client was
    *constructed*. That is not the same claim: leaving the construction intact
    and handing the dimension pass a bare `httpx.AsyncClient(follow_redirects=
    True)` left the whole file green. The pass that pulls a full body back
    could be un-guarded without a single red light (P25 — the assertion sat one
    layer below the thing it named).

    So this drives a real crawl whose image redirects inward, and asserts the
    internal target was never requested.
    """

    @pytest.mark.asyncio
    async def test_ssrf_crawl_image_pass_does_not_follow_a_redirect_inward(self):
        page = ("<!DOCTYPE html><html lang='en'><head>"
                "<title>A Page With A Good Long Title</title>"
                "<meta name='description' content='A description long enough to "
                "pass the checks that run here without tripping them.'>"
                "</head><body><h1>H</h1>"
                "<img src='/a.png' alt='A described photograph' width='300'>"
                "<p>" + " ".join(["word"] * 80) + "</p></body></html>")
        with respx.mock:
            respx.get("https://example.com/robots.txt").mock(
                return_value=httpx.Response(200, text="User-agent: *\nDisallow:\n"))
            respx.get("https://example.com/sitemap.xml").mock(
                return_value=httpx.Response(404))
            respx.get(BASE).mock(return_value=httpx.Response(
                200, text=page, headers={"content-type": "text/html"}))
            respx.head(f"{BASE}a.png").mock(return_value=httpx.Response(
                200, headers={"content-type": "image/png",
                              "content-length": "120000"}))
            # the image itself redirects to the cloud metadata service
            respx.get(f"{BASE}a.png").mock(return_value=httpx.Response(
                302, headers={"location": "http://169.254.169.254/creds.png"}))
            inner = respx.get("http://169.254.169.254/creds.png").mock(
                return_value=httpx.Response(200, content=_png(300, 200),
                                            headers={"content-type": "image/png"}))
            result = await run_crawl("ssrf1", BASE,
                                     CrawlSettings(crawl_delay_ms=0, max_pages=3))

        assert not inner.called, (
            "the crawl's dimension pass followed an image redirect to the "
            "cloud metadata service and pulled the body back")
        assert result.images_measured == 0, (
            "something was recorded as measured from a refused fetch")

    @pytest.mark.asyncio
    async def test_ssrf_crawl_image_pass_still_measures_a_public_image(self):
        """The guard must not disable the pass it protects."""
        page = ("<!DOCTYPE html><html lang='en'><head>"
                "<title>A Page With A Good Long Title</title>"
                "<meta name='description' content='A description long enough to "
                "pass the checks that run here without tripping them.'>"
                "</head><body><h1>H</h1>"
                "<img src='/ok.png' alt='A described photograph' width='300'>"
                "<p>" + " ".join(["word"] * 80) + "</p></body></html>")
        with respx.mock:
            respx.get("https://example.com/robots.txt").mock(
                return_value=httpx.Response(200, text="User-agent: *\nDisallow:\n"))
            respx.get("https://example.com/sitemap.xml").mock(
                return_value=httpx.Response(404))
            respx.get(BASE).mock(return_value=httpx.Response(
                200, text=page, headers={"content-type": "text/html"}))
            respx.head(f"{BASE}ok.png").mock(return_value=httpx.Response(
                200, headers={"content-type": "image/png",
                              "content-length": "9000"}))
            respx.get(f"{BASE}ok.png").mock(return_value=httpx.Response(
                200, content=_png(900, 600),
                headers={"content-type": "image/png"}))
            result = await run_crawl("ssrf2", BASE,
                                     CrawlSettings(crawl_delay_ms=0, max_pages=3))
        assert result.images_measured == 1, "the public image was not measured"
        img = next(i for i in result.images if i.url.endswith("ok.png"))
        assert img.width == 900 and img.height == 600
