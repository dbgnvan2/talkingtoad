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


class TestAnUnreadablePageIsNotAFixedPage:
    """403/401/429 are not 404. `issue_for_status` returns a finding only for
    404, 410, 503 and 5xx — every other 4xx yields None.

    The E1 guard took "no issue" to mean "no problems", so a page behind
    Cloudflare (403), rate-limited (429) or login-gated (401) came back with
    ZERO issues. On the rescan path that is not merely silent: the endpoint
    deletes the URL's stored issues and writes the difference to the
    fixed-issues ledger, so every prior finding is recorded as RESOLVED because
    the page could not be read. A transient block is written as a permanent
    positive (P1), and invisibly (P2).
    """

    @pytest.fixture
    async def store(self, tmp_path):
        s = SQLiteJobStore(db_path=str(tmp_path / "t.db"))
        await s.init()
        try:
            yield s
        finally:
            await s.close()

    @pytest.mark.parametrize("status", [401, 403, 405, 429, 451])
    async def test_e1_blocked_page_is_not_reported_as_clean(self, store, status):
        """A status the broken-link mapper does not cover must still not read
        as a page with nothing wrong with it."""
        with respx.mock(assert_all_mocked=False, assert_all_called=False) as rx:
            rx.get(GONE).mock(return_value=httpx.Response(
                status, text=NOT_FOUND_HTML, headers={"content-type": "text/html"}))
            rx.route().mock(return_value=httpx.Response(200, text="ok"))
            res = await _fetch_and_check_page(
                url=GONE, job_id="j", store=store, base_url=BASE)

        assert getattr(res, "page_unreadable", None) is True, (
            f"HTTP {status}: the page could not be read, and nothing in the "
            f"result says so — the caller cannot tell it apart from a clean page"
        )

    @pytest.mark.parametrize("status", [403, 429])
    async def test_e1_a_blocked_rescan_never_records_issues_as_fixed(self, store, status):
        """The consequential half. Deleting stored findings and writing them to
        the fixed-issues ledger, because a bot-block stopped us reading the
        page, corrupts data the operator acts on."""
        from api.routers.crawl import _rescan_is_conclusive
        assert _rescan_is_conclusive(200) is True
        assert _rescan_is_conclusive(status) is False, (
            f"HTTP {status} is not evidence that anything was fixed"
        )
        # 404/410 ARE conclusive: the page is genuinely gone, and its old
        # findings genuinely no longer apply.
        assert _rescan_is_conclusive(404) is True


class TestTheLedgerIsActuallyProtected:
    """End-to-end, through the endpoint. The predicate test above proves only
    that a function exists and returns the right booleans — it would stay green
    if nothing called it, which is the wiring trap this repo has hit before.
    """

    @pytest.fixture
    async def store(self, tmp_path):
        s = SQLiteJobStore(db_path=str(tmp_path / "t.db"))
        await s.init()
        try:
            yield s
        finally:
            await s.close()

    async def _seed(self, store):
        from datetime import datetime, timezone
        from api.models.job import CrawlJob
        from api.models.page import CrawledPage
        from api.crawler.checkers.registry import make_issue
        from api.routers.crawl import _engine_issue_to_model

        job = CrawlJob(job_id="j1", target_url=BASE,
                       started_at=datetime.now(timezone.utc))
        await store.create_job(job)
        await store.save_pages([CrawledPage(
            job_id="j1", url=GONE, status_code=200, title="The Real Title",
            meta_description="d" * 80, h1_tags=["Real H1"],
            crawled_at=datetime.now(timezone.utc))])
        issues = [_engine_issue_to_model(make_issue(c, GONE), "j1")
                  for c in ("H1_MISSING", "TITLE_TOO_SHORT")]
        for i in issues:
            i.page_url = GONE
        await store.save_issues(issues)
        return {i.issue_code for i in issues}

    @pytest.mark.parametrize("status", [403, 429])
    async def test_e1_a_blocked_rescan_leaves_the_stored_findings_alone(self, store, status):
        from api.routers.crawl import rescan_url
        seeded = await self._seed(store)

        with respx.mock(assert_all_mocked=False, assert_all_called=False) as rx:
            rx.get(GONE).mock(return_value=httpx.Response(
                status, text=NOT_FOUND_HTML, headers={"content-type": "text/html"}))
            rx.route().mock(return_value=httpx.Response(200, text="ok"))
            resp = await rescan_url(job_id="j1", url=GONE, store=store)

        assert resp.get("page_unreadable") is True
        assert resp["resolved"] == 0 and resp["resolved_codes"] == [], (
            f"HTTP {status} was treated as evidence that findings were fixed: {resp}"
        )
        # The findings must still be in the store.
        _, by_cat = await store.get_page_issues_by_url("j1", GONE)
        still = {i.issue_code for v in by_cat.values() for i in v}
        assert seeded <= still, f"stored findings were deleted by a failed read: {still}"

        # And the page record must not have been overwritten by the error page.
        pages = await store.get_pages("j1")
        row = [p for p in pages if p.url == GONE][0]
        assert row.title == "The Real Title", (
            f"the stored page was overwritten with the error page's parse: {row.title!r}"
        )

    async def test_e1_a_readable_rescan_still_records_fixes(self, store):
        """The inverse. A fix that simply never records resolutions would turn
        every test above green while breaking the feature."""
        from api.routers.crawl import rescan_url
        await self._seed(store)
        good = ("<!DOCTYPE html><html lang='en'><head>"
                "<title>A Perfectly Good Page Title Here</title>"
                "<meta name='description' content='" + "x" * 80 + "'>"
                "</head><body><h1>Real H1</h1><p>" + " ".join(["w"] * 400) +
                "</p></body></html>")
        with respx.mock(assert_all_mocked=False, assert_all_called=False) as rx:
            rx.get(GONE).mock(return_value=httpx.Response(
                200, text=good, headers={"content-type": "text/html"}))
            rx.route().mock(return_value=httpx.Response(200, text="ok"))
            resp = await rescan_url(job_id="j1", url=GONE, store=store)

        assert not resp.get("page_unreadable")
        assert "H1_MISSING" in resp["resolved_codes"], (
            f"a genuine fix is no longer recorded as resolved: {resp}"
        )


class TestTheImagePipelineSkipsErrorPages:
    """The E1 guard is inside _fetch_and_check_page. /scan-page continued past
    it using check.page — the parsed ERROR TEMPLATE — and ran the whole image
    collection, storing IMG_ALT_* findings against a URL that does not exist
    and counting them in the response.
    """

    @pytest.fixture
    async def store(self, tmp_path):
        s = SQLiteJobStore(db_path=str(tmp_path / "t.db"))
        await s.init()
        try:
            yield s
        finally:
            await s.close()

    async def test_e1_a_404_templates_images_are_not_audited(self, store):
        from api.routers.crawl import scan_single_page
        html = NOT_FOUND_HTML.replace(
            "</body>",
            "<img src='/wp-content/logo.png'><img src='/wp-content/icon.png' alt='x'></body>")
        with respx.mock(assert_all_mocked=False, assert_all_called=False) as rx:
            rx.get(GONE).mock(return_value=httpx.Response(
                404, text=html, headers={"content-type": "text/html"}))
            rx.route().mock(return_value=httpx.Response(200, text="ok"))
            resp = await scan_single_page(url=GONE, store=store)

        job_id = resp["job_id"]
        issues, _ = await store.get_issues(job_id)
        codes = {i.issue_code for i in issues}
        img_codes = {c for c in codes if c.startswith("IMG_")}
        assert not img_codes, (
            f"the 404 template's images were audited against a URL that does "
            f"not exist: {sorted(img_codes)}"
        )
        # AI_BOT_* comes from the site's robots.txt, which /scan-page fetches
        # separately. It describes the DOMAIN, not this page, so it is
        # legitimately present. What must not appear is anything derived from
        # the error template's own markup.
        from api.crawler.checkers.registry import _CATALOGUE
        page_level = {c for c in codes
                      if c != "BROKEN_LINK_404" and not c.startswith("AI_BOT_")}
        assert not page_level, (
            f"the error template's markup was audited as page content: "
            f"{sorted(page_level)}"
        )
