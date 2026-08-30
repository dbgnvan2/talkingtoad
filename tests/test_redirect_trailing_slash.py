"""AF2 — do not report a trailing-slash redirect we caused ourselves.

Spec:  docs/pending/2026-08-30_audit-fixes.md#AF2
Audit: docs/audit/2026-08-30_full-check-audit.md (F8)

`normalise_url` strips a trailing slash, so the crawler fetches `/x` on a site
whose canonical form is `/x/`. The server 301s back and we reported it as a
defect: 147 of 147 findings on livingsystems.ca differed only by the slash,
3,590 lifetime. Screaming Frog, which requests each URL in the form the site
publishes, reported no redirect issue at all on the same site.

The distinction that matters: if a page really does link to the pre-redirect
form, the inconsistency is the site's and must still be reported.
"""
from __future__ import annotations

import httpx
import pytest
import respx

from api.crawler.engine import (CrawlSettings, _is_self_inflicted_slash_redirect,
                                run_crawl)

BASE = "https://example.com/"
ROBOTS = "https://example.com/robots.txt"
SITEMAP = "https://example.com/sitemap.xml"


class _Issue:
    def __init__(self, code, page_url, extra):
        self.code, self.page_url, self.extra = code, page_url, extra


def _slash_issue(src, dst):
    return _Issue("REDIRECT_TRAILING_SLASH", src, {"from": src, "to": dst})


class TestSelfInflictedDetection:
    def test_af2_slash_only_redirect_the_site_never_links_is_self_inflicted(self):
        issue = _slash_issue("https://example.com/about", "https://example.com/about/")
        linked = {"https://example.com/about/"}          # the site links the SLASHED form
        assert _is_self_inflicted_slash_redirect(issue, linked) is True

    def test_af2_slash_only_redirect_the_site_really_links_is_genuine(self):
        """Adversarial: a real inconsistency must survive."""
        issue = _slash_issue("https://example.com/about", "https://example.com/about/")
        linked = {"https://example.com/about"}           # a page links the UNSLASHED form
        assert _is_self_inflicted_slash_redirect(issue, linked) is False

    def test_af2_non_slash_redirect_is_never_suppressed(self):
        issue = _slash_issue("https://example.com/old", "https://example.com/new/")
        assert _is_self_inflicted_slash_redirect(issue, set()) is False

    def test_af2_identical_urls_are_not_a_slash_redirect(self):
        issue = _slash_issue("https://example.com/a", "https://example.com/a")
        assert _is_self_inflicted_slash_redirect(issue, set()) is False

    def test_af2_missing_extra_is_not_suppressed(self):
        """A finding with no evidence must never be silently dropped."""
        assert _is_self_inflicted_slash_redirect(_Issue("REDIRECT_TRAILING_SLASH", "", {}), set()) is False


_PAGE = ("<!DOCTYPE html><html lang='en'><head><title>A Page With A Good Long Title</title>"
         "<meta name='description' content='A description long enough to pass the checks here.'>"
         "</head><body><h1>H</h1><a href='https://example.com/about/'>About</a><p>"
         + " ".join(["word"] * 80) + "</p></body></html>")


class TestEndToEnd:
    @pytest.mark.asyncio
    async def test_af2_livingsystems_shape_produces_no_finding(self):
        """The real shape: every link uses `/about/`; we fetch `/about` and get a
        301 back. No visitor ever meets that redirect."""
        with respx.mock:
            respx.get(ROBOTS).mock(return_value=httpx.Response(200, text="User-agent: *\nDisallow:\n"))
            respx.get(SITEMAP).mock(return_value=httpx.Response(404))
            respx.get(BASE).mock(return_value=httpx.Response(
                200, text=_PAGE, headers={"content-type": "text/html"}))
            respx.get("https://example.com/about").mock(return_value=httpx.Response(
                301, headers={"location": "https://example.com/about/"}))
            respx.get("https://example.com/about/").mock(return_value=httpx.Response(
                200, text=_PAGE, headers={"content-type": "text/html"}))
            result = await run_crawl("af2", BASE, CrawlSettings(crawl_delay_ms=0, max_pages=20))
        found = [i for i in result.issues if i.code == "REDIRECT_TRAILING_SLASH"]
        assert found == [], f"self-inflicted redirect reported: {[i.extra for i in found]}"
