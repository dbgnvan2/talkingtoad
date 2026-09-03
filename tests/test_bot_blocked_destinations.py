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

    async def test_many_unverified_links_on_one_page_collapse_to_one_row(self):
        """Cold sweep, and the consequence the impact-0 assertion below does NOT
        guard. `PER_TARGET_CODES` (links.py) lists BROKEN_LINK_503 but not
        EXTERNAL_LINK_SKIPPED, so reclassifying moved these rows OUT of
        `collapse_per_target_occurrences`: 10 findings on one page went from 1
        stored row to 10. `by_category.broken_link` is the big number rendered
        under the label "Broken Links" in SummaryPanel and the PDF, so a page of
        50 Amazon links would show 50 "broken links" — after a change made to
        stop calling them broken (P16)."""
        def wire(mock):
            mock.route(host="nobody.test").mock(return_value=httpx.Response(503))

        body = "".join(f'<a href="https://nobody.test/l{i}">l{i}</a>' for i in range(10))
        issues = await _crawl("bb-collapse", body, wire)
        skipped = [i for i in issues if i.code == "EXTERNAL_LINK_SKIPPED"]
        assert len(skipped) == 1, (
            f"{len(skipped)} rows for one page's unverified links — they are not "
            f"collapsing, and the Broken Links tile counts every one")
        assert skipped[0].extra.get("occurrence_urls_total") or \
            skipped[0].extra.get("count") or len(skipped[0].extra.get("occurrence_urls") or []), \
            f"the collapsed row does not disclose how many links it covers: {skipped[0].extra}"

    async def test_a_dead_link_on_a_listed_host_is_still_broken(self):
        """Finding 10: the branch treated EVERY status >= 400 from a listed host
        as unverified, including the definite ones — so a shortener landing on a
        LinkedIn profile that 404s became impact 0. A 404 is an answer."""
        def wire(mock):
            mock.route(host="short.test").mock(return_value=httpx.Response(
                301, headers={"location": "https://www.linkedin.com/in/gone"}))
            mock.route(host="www.linkedin.com").mock(return_value=httpx.Response(404))

        codes = _codes(await _crawl(
            "bb-listed-404", f'<a href="{SHORTENER}/abc">Profile</a>', wire))
        assert "BROKEN_LINK_404" in codes, codes

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

    @pytest.mark.parametrize("status", [403, 401, 999])
    async def test_a_refused_external_check_is_unverified_not_silent(self, status):
        """BL1 (2026-09-03). `issue_for_status` maps 404, 410, 503 and 5xx and
        returns None for everything else, so an external 403/401/999 produced NO
        finding and the link was recorded as verified and working. Cloudflare and
        Akamai bot walls answer 403; LinkedIn answers 999. Same P2 as the 429 and
        503 work, one status over — and silence is the worst of the three
        possible answers, because it asserts the link is fine.

        A 403 is genuinely ambiguous: a bot wall (works for humans) or a real
        permission gate (works for nobody anonymous). We cannot tell, so we say
        so and name the status."""
        def wire(mock):
            mock.route(host="forbidden.test").mock(return_value=httpx.Response(status))

        issues = await _crawl(
            f"bb-{status}", '<a href="https://forbidden.test/x">Forbidden</a>', wire)
        hits = [i for i in issues if i.code == "EXTERNAL_LINK_SKIPPED"]
        assert hits, f"HTTP {status} produced no finding: {_codes(issues)}"
        assert any(i.extra.get("status_code") == status for i in hits), (
            f"the status is missing from the evidence: {[i.extra for i in hits]}")

    async def test_a_403_is_never_called_broken(self):
        """The other half: unverified, not broken. Claiming a bot-walled link is
        broken is as wrong as claiming it is fine."""
        def wire(mock):
            mock.route(host="forbidden.test").mock(return_value=httpx.Response(403))

        codes = _codes(await _crawl(
            "bb-403-notbroken", '<a href="https://forbidden.test/x">F</a>', wire))
        assert not [c for c in codes if c.startswith("BROKEN_LINK")], codes

    async def test_an_internal_403_page_produces_no_broken_link_finding(self):
        """The BASELINE for internal 403, recorded rather than assumed.

        The first version of this asserted that an internal 403 does not become
        `EXTERNAL_LINK_SKIPPED` — which is structurally impossible and so could
        never fail (cold sweep, P27): only links where `is_internal` is false are
        queued for external checking, and the `link_type == "external"` guard in
        the branch recomputes the same expression, so it is a tautology.

        What is worth pinning is the actual behaviour, because it is a gap and
        somebody will change it: an internal page returning 403 produces NO
        broken-link finding at all, because `issue_for_status` returns None for
        403. Deliberately out of scope for BL1 — a crawler blocked from the
        site's own page is a different question — and recorded in TODO."""
        def wire(mock):
            mock.get("https://example.com/private").mock(return_value=httpx.Response(
                403, text="<html><body>Forbidden</body></html>",
                headers={"content-type": "text/html"}))

        issues = await _crawl("bb-403-internal", '<a href="/private">Private</a>',
                              wire, max_pages=2)
        codes = _codes(issues)
        assert codes == [], (
            f"internal-403 handling changed; this is the recorded baseline: {codes}")

    async def test_a_listed_host_reached_via_a_redirect_that_answers_200_is_verified(self):
        """The `>= 400` guard. The first version of the condition was
        `status == 503 OR host is listed`, with no requirement that anything had
        failed — so a listed host that answered 200 was reported as unverified.
        A successful check is a successful check; the listing explains a FAILURE,
        it does not disqualify a success.

        The shortener shape is the only one that reaches this branch: a DIRECT
        link to a listed host is skipped before any request, so a test using one
        is vacuous — which the cold sweep caught in the first version of this
        test, written against amazon.ca, a host deliberately not on the list."""
        def wire(mock):
            mock.route(host="short.test").mock(return_value=httpx.Response(
                301, headers={"location": "https://www.linkedin.com/in/someone"}))
            mock.route(host="www.linkedin.com").mock(return_value=httpx.Response(200))

        codes = _codes(await _crawl(
            "bb-listed-ok", f'<a href="{SHORTENER}/abc">Profile</a>', wire))
        assert codes == [], f"a link that answered 200 was reported: {codes}"

    async def test_a_direct_link_to_a_listed_host_is_skipped_without_asking(self):
        """The other half, stated so the two are not confused: a listed host is
        never requested at all, whatever it would have answered. That is what
        the list means, and why Amazon does not belong on it."""
        def wire(mock):
            asked = mock.route(host="www.linkedin.com").mock(
                return_value=httpx.Response(200))
            wire.asked = asked

        codes = _codes(await _crawl(
            "bb-listed-direct", '<a href="https://www.linkedin.com/in/x">P</a>', wire))
        assert "EXTERNAL_LINK_SKIPPED" in codes, codes
        assert wire.asked.call_count == 0, "a listed host was requested anyway"

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


class TestAnErrorPageWithNoContentTypeIsStillReported:
    """D1 — `engine.py` branches on `is_html` / `is_asset`, and a response with
    no `content-type` header fell to the "unknown binary" arm where
    `page_issues = []`. A bare 503 or 500 from a misconfigured server — the case
    where the status matters MOST — was crawled, stored and reported as nothing
    (P2). The content-type branch decides which CONTENT checks run; it must not
    decide whether the STATUS is reported.

    Spec: docs/functional-specification.md §4.3 (D1, 2026-09-03)
    """

    async def test_a_503_with_no_content_type_is_reported(self):
        def wire(mock):
            mock.get("https://example.com/down").mock(return_value=httpx.Response(503))

        issues = await _crawl("d1-503", '<a href="/down">Down</a>', wire, max_pages=2)
        assert "BROKEN_LINK_503" in [i.code for i in issues], (
            "a bare 503 with no content-type produced no finding")

    async def test_a_404_with_no_content_type_is_reported(self):
        def wire(mock):
            mock.get("https://example.com/gone").mock(return_value=httpx.Response(404))

        issues = await _crawl("d1-404", '<a href="/gone">Gone</a>', wire, max_pages=2)
        assert "BROKEN_LINK_404" in [i.code for i in issues]

    async def test_an_html_error_page_still_behaves_as_before(self):
        def wire(mock):
            mock.get("https://example.com/down").mock(return_value=httpx.Response(
                503, text="<html><body>Down</body></html>",
                headers={"content-type": "text/html"}))

        issues = await _crawl("d1-html", '<a href="/down">Down</a>', wire, max_pages=2)
        assert "BROKEN_LINK_503" in [i.code for i in issues]

    async def test_a_200_with_no_content_type_is_not_a_broken_link(self):
        """Adversarial: the change is scoped to error statuses. A body we cannot
        classify is not a broken link."""
        def wire(mock):
            mock.get("https://example.com/blob").mock(return_value=httpx.Response(200))

        issues = await _crawl("d1-200", '<a href="/blob">Blob</a>', wire, max_pages=2)
        assert not [i for i in issues if i.code.startswith("BROKEN_LINK")]
