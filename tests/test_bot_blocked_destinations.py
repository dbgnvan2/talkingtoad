"""BB1–BB4 — a destination that blocks bots is unverified, not broken.

Spec: docs/functional-specification.md §4.3 (BB1-BB4, folded 2026-09-03)

The report: a rescan of livingsystems.ca produced 9 `BROKEN_LINK_503` findings.
All nine resolve to amazon.ca — seven directly, two via `shorturl.at`'s own www
hop — and Amazon answers automated clients with 503. Every link works for a
human.

Two faults, and the second is why the first is only a convenience:

* `_BOT_BLOCKING_DOMAINS` was matched against the link AS WRITTEN, so a URL
  shortener bypassed it entirely: `tinyurl.com/x` is not in the list, and the
  `amazon.ca` it redirects to was never consulted, though `fetch_page` has
  returned `final_url` all along.
* For an EXTERNAL destination the tool cannot tell "temporarily down" from
  "blocking us" — both mean *we could not verify*. `authority.yaml` already
  records RFC 9110 §15.6.4 against `BROKEN_LINK_503` ("a transient condition,
  not a broken destination") and the engine filed it under broken_link anyway.

The adversarial partner matters more than usual here: this must not decay into
"stop reporting 503". An internal 503 is a real fact about the operator's own
server and is still reported.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from api.crawler.engine import CrawlSettings, run_crawl

BASE = "https://example.com/"
ROBOTS = "https://example.com/robots.txt"
ALLOW = "User-agent: *\nAllow: /\n"

BLOCKER = "https://www.amazon.ca"      # answers automated clients with 503
SHORTENER = "https://short.test"       # innocent; redirects to the blocker


def _page(body: str, title: str = "A Perfectly Reasonable Page Title Here") -> str:
    return ("<!DOCTYPE html><html lang='en'><head>"
            f"<title>{title}</title>"
            "<meta name='description' content='A description long enough to pass the checks.'>"
            f"</head><body><h1>Links</h1><p>{'word ' * 60}</p>{body}</body></html>")


def _site(mock: respx.MockRouter, body: str) -> None:
    mock.get(ROBOTS).mock(return_value=httpx.Response(200, text=ALLOW))
    mock.get("https://example.com/sitemap.xml").mock(return_value=httpx.Response(404))
    mock.get(BASE).mock(return_value=httpx.Response(
        200, text=_page(body), headers={"content-type": "text/html"}))


async def _crawl(job: str, body: str, wire, *, max_pages: int = 1) -> list:
    with respx.mock(assert_all_called=False) as mock:
        _site(mock, body)
        wire(mock)
        mock.route(host="example.com").mock(return_value=httpx.Response(404))
        res = await run_crawl(job, BASE, CrawlSettings(
            crawl_delay_ms=0, max_pages=max_pages))
    return res.issues


def _codes(issues) -> list[str]:
    return [i.code for i in issues if i.code.startswith(("BROKEN_LINK", "EXTERNAL_LINK"))]


# ── The one that matters (P10) ──────────────────────────────────────────────


class TestABotBlockedDestinationIsUnverified:
    async def test_a_direct_link_to_a_blocking_host_is_not_called_broken(self):
        def wire(mock):
            mock.route(host="www.amazon.ca").mock(return_value=httpx.Response(503))

        issues = await _crawl(
            "bb-direct", f'<a href="{BLOCKER}/book/dp/123">A book</a>', wire)
        codes = _codes(issues)
        assert "BROKEN_LINK_503" not in codes, codes
        assert "EXTERNAL_LINK_SKIPPED" in codes, codes

    async def test_the_shortener_shape_from_the_report(self):
        """BB1 — the fault that makes the domain list a convenience rather than
        the mechanism. A test that only linked DIRECTLY to a blocked host passes
        without BB1 and would have shipped this bug again."""
        def wire(mock):
            mock.route(host="short.test").mock(return_value=httpx.Response(
                307, headers={"location": f"{BLOCKER}/book/dp/123"}))
            mock.route(host="www.amazon.ca").mock(return_value=httpx.Response(503))

        issues = await _crawl("bb-short", f'<a href="{SHORTENER}/abc123">A book</a>', wire)
        codes = _codes(issues)
        assert "BROKEN_LINK_503" not in codes, (
            f"the redirect hid the blocking destination: {codes}")
        assert "EXTERNAL_LINK_SKIPPED" in codes, codes

    async def test_the_evidence_names_where_it_actually_landed(self):
        """An operator cannot act on 'short.test/abc123 was skipped'. The finding
        has to say which host refused, or it is unactionable and undisputable."""
        def wire(mock):
            mock.route(host="short.test").mock(return_value=httpx.Response(
                307, headers={"location": f"{BLOCKER}/book/dp/123"}))
            mock.route(host="www.amazon.ca").mock(return_value=httpx.Response(503))

        issues = await _crawl("bb-evidence", f'<a href="{SHORTENER}/abc123">A book</a>', wire)
        skipped = [i for i in issues if i.code == "EXTERNAL_LINK_SKIPPED"]
        assert skipped
        blob = f"{skipped[0].description} {skipped[0].extra}"
        assert "amazon.ca" in blob, f"the blocking host is not in the finding: {blob}"

    async def test_an_unknown_host_that_503s_is_also_unverified(self):
        """BB3 — the general rule. A host nobody has listed still cannot be
        distinguished from one that is merely down, so it is unverified too.
        This is what stops the domain list becoming whack-a-mole."""
        def wire(mock):
            mock.route(host="nobody.test").mock(return_value=httpx.Response(503))

        codes = _codes(await _crawl(
            "bb-unknown", '<a href="https://nobody.test/x">Something</a>', wire))
        assert "BROKEN_LINK_503" not in codes, codes
        assert "EXTERNAL_LINK_SKIPPED" in codes, codes

    def test_an_unverified_link_costs_the_site_nothing(self):
        """Impact 0, asserted against the scoring table so a future recalibration
        cannot quietly start charging for a link nobody checked."""
        from api.crawler.checkers.registry import _ISSUE_SCORING

        assert _ISSUE_SCORING["EXTERNAL_LINK_SKIPPED"][0] == 0


# ── The check must survive (adversarial) ────────────────────────────────────


class TestItDoesNotBecomeStopReporting503:
    async def test_an_internal_page_that_503s_is_still_broken(self):
        """The operator's own server returning 503 is a real fact — we are
        already crawling it, so 'it blocks bots' is not the explanation."""
        def wire(mock):
            mock.get("https://example.com/down").mock(return_value=httpx.Response(
                503, text="<html><body>Service Unavailable</body></html>",
                headers={"content-type": "text/html"}))

        # max_pages=2 so the internal page is actually crawled — at 1 the link is
        # never followed and the test would pass for the wrong reason.
        issues = await _crawl("bb-internal", '<a href="/down">Our other page</a>',
                              wire, max_pages=2)
        codes = [i.code for i in issues]
        assert "BROKEN_LINK_503" in codes, (
            f"an internal 503 stopped being reported: {sorted(set(codes))}")

    async def test_an_external_404_is_still_broken(self):
        """Reclassification is scoped to 503 — the one status whose own RFC
        definition is 'temporary'. A 404 is a definite answer."""
        def wire(mock):
            mock.route(host="gone.test").mock(return_value=httpx.Response(404))

        codes = _codes(await _crawl(
            "bb-404", '<a href="https://gone.test/x">Gone</a>', wire))
        assert "BROKEN_LINK_404" in codes, codes

    async def test_an_external_403_is_still_broken(self):
        def wire(mock):
            mock.route(host="forbidden.test").mock(return_value=httpx.Response(403))

        issues = await _crawl(
            "bb-403", '<a href="https://forbidden.test/x">Forbidden</a>', wire)
        assert "EXTERNAL_LINK_SKIPPED" not in _codes(issues), (
            "a 403 is a definite answer and must not be reclassified as unverified")

    async def test_a_listed_host_that_actually_answers_is_verified_not_skipped(self):
        """Self-caught before the sweep: the first version of the condition was
        `status == 503 OR host is listed`, so a link to Amazon that answered 200
        was reported as unverified. A successful check is a successful check —
        the listing exists to explain a FAILURE, not to disqualify a success."""
        def wire(mock):
            mock.route(host="www.amazon.ca").mock(return_value=httpx.Response(200))

        codes = _codes(await _crawl(
            "bb-listed-ok", f'<a href="{BLOCKER}/book/dp/123">A book</a>', wire))
        assert codes == [], f"a link that answered 200 was reported: {codes}"

    async def test_a_shortener_to_a_LISTED_host_is_still_caught_after_the_fetch(self):
        """BB1's remaining job now that Amazon is not listed: a short link that
        lands on a genuinely skip-worthy platform is recognised from `final_url`,
        which the pre-request check cannot see."""
        def wire(mock):
            mock.route(host="short.test").mock(return_value=httpx.Response(
                301, headers={"location": "https://www.linkedin.com/in/someone"}))
            mock.route(host="www.linkedin.com").mock(return_value=httpx.Response(999))

        codes = _codes(await _crawl(
            "bb-short-linkedin", f'<a href="{SHORTENER}/abc">Profile</a>', wire))
        assert "EXTERNAL_LINK_SKIPPED" in codes, codes

    async def test_a_working_external_link_produces_nothing(self):
        def wire(mock):
            mock.route(host="fine.test").mock(return_value=httpx.Response(200))

        assert _codes(await _crawl(
            "bb-ok", '<a href="https://fine.test/x">Fine</a>', wire)) == []


class TestTheDomainListIsAConvenienceNotTheMechanism:
    """BB2 — Amazon is listed so we skip the request where we already know the
    answer. The listing must not be what makes the behaviour correct: BB3 covers
    the unlisted hosts, asserted above."""

    def test_amazon_is_deliberately_NOT_listed(self):
        """Listing it was the first attempt and it made things worse: the list
        means "do not even ask", so Amazon links stopped being checked at all and
        a genuinely dead product link would never be caught. BB3 handles it —
        make the request, and if it refuses, report the link as unverified.
        Asserted so nobody re-adds it thinking they are fixing something."""
        from api.crawler.engine import _is_bot_blocking_domain

        for host in ("https://www.amazon.ca/x", "https://amazon.com/y"):
            assert not _is_bot_blocking_domain(host), (
                f"{host} is skipped before any request — see BB2 in engine.py")

    def test_the_original_social_hosts_still_match(self):
        from api.crawler.engine import _is_bot_blocking_domain

        for host in ("https://www.linkedin.com/in/x", "https://facebook.com/y",
                     "https://www.instagram.com/z"):
            assert _is_bot_blocking_domain(host), host

    def test_an_ordinary_host_does_not_match(self):
        from api.crawler.engine import _is_bot_blocking_domain

        for host in ("https://example.org/x", "https://notamazon.test/y",
                     "https://amazonia-charity.org/z"):
            assert not _is_bot_blocking_domain(host), host
