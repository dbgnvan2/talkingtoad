"""An error page is not content, on every path that can reach it.

Spec:  docs/functional-specification.md (E1)
Tests: this file

Reported from a real report: a scoped scan showed
https://livingsystems.ca/team-members/14528 as a regular page carrying
NOINDEX_META, MISSING_HSTS, UNSAFE_CROSS_ORIGIN_LINK and
CONSENT_MODE_MISSING. The URL returns 404. Every finding described
WordPress's 404 TEMPLATE — the six "unsafe cross-origin links" were the site
footer's Facebook/Instagram/LinkedIn icons, and the noindex was the 404
template's own, which is correct for a 404. All of them charged the site's
health score for a page that does not exist.

run_crawl had guarded this from the start. _fetch_and_check_page — the rescan
and single-page path — guarded only status_code == 0, so the same URL was
audited or not depending on which button reached it. The repo already pinned
the two paths to agree on BROKEN LINKS; nothing pinned them to agree on the
page itself.
"""
from __future__ import annotations

import httpx
import pytest
import respx

from api.crawler.engine import CrawlSettings, run_crawl
from api.routers.crawl import _fetch_and_check_page
from api.services.sqlite_store import SQLiteJobStore

BASE = "https://e.test/"
GONE = BASE + "team-members/14528"

# WordPress's 404 template: full themed page, site footer, its own noindex.
NOT_FOUND_HTML = (
    "<!DOCTYPE html><html lang='en'><head>"
    "<title>Page not found - Living Systems</title>"
    "<meta name='robots' content='noindex, follow'>"
    "</head><body><h1>Page not found</h1>"
    "<a href='https://www.facebook.com/x' target='_blank'>Facebook</a>"
    "<a href='https://www.instagram.com/x' target='_blank'>Instagram</a>"
    "<a href='https://www.linkedin.com/x' target='_blank'>Linkedin</a>"
    "<p>Sorry, that page could not be found.</p></body></html>"
)

HEALTHY_HTML = (
    "<!DOCTYPE html><html lang='en'><head>"
    "<title>A Real Team Member Page With A Title</title>"
    "<meta name='description' content='A description long enough to pass the "
    "metadata checks that run here without tripping any of them.'>"
    "</head><body><h1>A Real Person</h1>"
    "<p>" + " ".join(["word"] * 120) + "</p></body></html>"
)

CONTENT_CODES = {"NOINDEX_META", "UNSAFE_CROSS_ORIGIN_LINK",
                 "CONSENT_MODE_MISSING", "ANALYTICS_TAG_MISSING",
                 "META_DESC_MISSING", "THIN_CONTENT"}


@pytest.fixture
async def store(tmp_path):
    s = SQLiteJobStore(db_path=str(tmp_path / "t.db"))
    await s.init()
    try:
        yield s
    finally:
        await s.close()


async def _rescan(store, url, status, body):
    with respx.mock(assert_all_mocked=False, assert_all_called=False) as rx:
        rx.get(url).mock(return_value=httpx.Response(
            status, text=body, headers={"content-type": "text/html"}))
        rx.route().mock(return_value=httpx.Response(200, text="ok"))
        return await _fetch_and_check_page(
            url=url, job_id="j", store=store, base_url=BASE)


class TestRescanPath:
    @pytest.mark.parametrize("status", [404, 410])
    async def test_e1_rescan_of_a_404_reports_broken_not_content(self, store, status):
        res = await _rescan(store, GONE, status, NOT_FOUND_HTML)
        codes = {i.issue_code for i in res.issues}
        assert codes & {"BROKEN_LINK_404", "BROKEN_LINK_410"}, (
            f"an error page must report as broken; got {sorted(codes)}")
        leaked = codes & CONTENT_CODES
        assert not leaked, (
            f"content checks ran on a {status} error page and charged "
            f"{sorted(leaked)} — those describe the site's error template, "
            f"not any page of the site")

    async def test_e1_rescan_of_a_500_reports_broken_not_content(self, store):
        res = await _rescan(store, GONE, 500, NOT_FOUND_HTML)
        codes = {i.issue_code for i in res.issues}
        assert not (codes & CONTENT_CODES), (
            f"content checks ran on a 500: {sorted(codes & CONTENT_CODES)}")

    async def test_e1_a_healthy_page_is_still_fully_checked(self, store):
        """The guard must not disable checking of real pages."""
        res = await _rescan(store, BASE + "real/", 200, HEALTHY_HTML)
        codes = {i.issue_code for i in res.issues}
        assert "BROKEN_LINK_404" not in codes
        assert res.page.title, "a healthy page was not parsed"
        # it really did run content checks (this page has no analytics tag)
        assert codes, "no checks ran at all on a healthy page"


class TestBothPathsAgree:
    async def test_e1_both_paths_agree_on_an_error_page(self, store):
        """The dual-path invariant, extended from links to the page itself."""
        with respx.mock(assert_all_mocked=False, assert_all_called=False) as rx:
            rx.get(f"{BASE}robots.txt").mock(return_value=httpx.Response(
                200, text="User-agent: *\nDisallow:\n"))
            rx.get(f"{BASE}sitemap.xml").mock(return_value=httpx.Response(404))
            rx.get(BASE).mock(return_value=httpx.Response(
                200, text=HEALTHY_HTML, headers={"content-type": "text/html"}))
            rx.get(GONE).mock(return_value=httpx.Response(
                404, text=NOT_FOUND_HTML, headers={"content-type": "text/html"}))
            rx.route().mock(return_value=httpx.Response(200, text="ok"))
            settings = CrawlSettings(crawl_delay_ms=0, max_pages=10)
            settings.scope_urls = {GONE}
            settings.priority_urls = [GONE]
            crawl = await run_crawl("dual", BASE, settings)

        crawl_codes = {i.code for i in crawl.issues
                       if GONE in (i.page_url or "")}
        rescan = await _rescan(store, GONE, 404, NOT_FOUND_HTML)
        rescan_codes = {i.issue_code for i in rescan.issues}

        assert not (crawl_codes & CONTENT_CODES), (
            f"the crawl path charged content findings: "
            f"{sorted(crawl_codes & CONTENT_CODES)}")
        assert not (rescan_codes & CONTENT_CODES), (
            f"the rescan path charged content findings: "
            f"{sorted(rescan_codes & CONTENT_CODES)}")
