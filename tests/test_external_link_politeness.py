"""EL1–EL4 — the crawler must be as polite to the hosts it verifies as to the site it audits.

Spec: docs/functional-specification.md §4.3 (EL1-EL4, folded 2026-09-03)

Found while investigating a batch of `BROKEN_LINK_503` findings on
livingsystems.ca — and **not** their cause. Those links all redirect to Amazon,
which answers automated clients with 503; a single spaced request reproduces it,
so concurrency was never the mechanism. The defects below are real on their own
merits:

* `crawl_delay_ms` is robots-aware and governs the site being audited. It
  governed nothing about the third-party hosts whose links we verify, so ten
  links to one host meant ten simultaneous connections to a stranger's server.
* 429 — the canonical rate-limit response, named first in LEARNINGS' retryable
  list — was never retried, because the retry set was 5xx only.
* `issue_for_status` returns None for 429, so a throttled link produced no
  finding and was counted as verified and working (P2).

These tests drive the REAL engine over a mocked transport. A unit test of the
semaphore would assert the implementation rather than the outcome (P26).
"""

from __future__ import annotations

import asyncio
import time

import httpx
import pytest
import respx

from api.crawler.engine import CrawlSettings, run_crawl

BASE = "https://example.com/"
ROBOTS = "https://example.com/robots.txt"
ALLOW = "User-agent: *\nAllow: /\n"
SHORTENER = "https://short.test"

_LINKS = 10


def _home(host: str = SHORTENER, n: int = _LINKS) -> str:
    anchors = "".join(f'<a href="{host}/l{i}">link {i}</a>' for i in range(n))
    return ("<!DOCTYPE html><html lang='en'><head>"
            "<title>A Page With A Perfectly Reasonable Title Here</title>"
            "<meta name='description' content='A description long enough to pass the checks.'>"
            "</head><body><h1>Links</h1>"
            f"<p>{'word ' * 60}</p>{anchors}</body></html>")


def _site(mock: respx.MockRouter, html: str) -> None:
    mock.get(ROBOTS).mock(return_value=httpx.Response(200, text=ALLOW))
    mock.get("https://example.com/sitemap.xml").mock(return_value=httpx.Response(404))
    mock.get(BASE).mock(return_value=httpx.Response(
        200, text=html, headers={"content-type": "text/html"}))
    mock.route(host="example.com").mock(return_value=httpx.Response(404))


class _Throttle:
    """A host that answers 503 while more than `allowed` requests are in flight.

    This is what a shortener does to a burst, and it is the condition the crawler
    was creating for itself.
    """

    def __init__(self, allowed: int = 1):
        self.allowed = allowed
        self.inflight = 0
        self.max_inflight = 0
        self.throttled = 0

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        self.inflight += 1
        self.max_inflight = max(self.max_inflight, self.inflight)
        try:
            if self.inflight > self.allowed:
                self.throttled += 1
                return httpx.Response(503)
            await asyncio.sleep(0.02)          # hold the slot so overlap is real
            return httpx.Response(200, headers={"content-type": "text/html"})
        finally:
            self.inflight -= 1


async def _crawl(job: str) -> list:
    res = await run_crawl(job, BASE, CrawlSettings(crawl_delay_ms=0, max_pages=1))
    return res.issues


# ── The one that matters (P10) ──────────────────────────────────────────────


class TestTheReportedCase:
    async def test_ten_links_to_one_host_are_not_reported_as_broken(self):
        """The livingsystems.ca case, reproduced in miniature."""
        throttle = _Throttle(allowed=1)
        with respx.mock(assert_all_called=False) as mock:
            _site(mock, _home())
            mock.route(host="short.test").mock(side_effect=throttle)
            issues = await _crawl("job-throttle")

        codes = [i.code for i in issues if i.code.startswith(("BROKEN_LINK", "EXTERNAL_LINK"))]
        assert "BROKEN_LINK_503" not in codes, (
            f"the crawler throttled itself and blamed the site: {codes} "
            f"(max concurrent requests to one host: {throttle.max_inflight})")

    async def test_the_host_never_sees_more_than_the_per_host_bound(self):
        from api.crawler import engine

        throttle = _Throttle(allowed=99)      # never throttles; just counts
        with respx.mock(assert_all_called=False) as mock:
            _site(mock, _home())
            mock.route(host="short.test").mock(side_effect=throttle)
            await _crawl("job-inflight")

        bound = getattr(engine, "_EXT_PER_HOST_CONCURRENCY", 1)
        assert throttle.max_inflight <= bound, (
            f"{throttle.max_inflight} simultaneous requests to one host (bound {bound})")
        # Pin the VALUE too. The assertion above takes its oracle from the
        # constant, so it stays green if someone raises the bound to 10 — it
        # proves the bound is honoured, not that the bound is right (P32).
        # Raising this is a deliberate edit to a test, with the politeness
        # argument in docs/thresholds.md to argue with.
        assert bound == 1, (
            f"per-host concurrency is {bound}; opening parallel connections to a "
            f"third party we are only verifying a link against needs a reason")

    async def test_different_hosts_still_overlap(self):
        """Adversarial partner: serialising per host must not serialise the whole
        pass. If it does, a site with 50 external hosts crawls 50x slower and
        somebody will 'fix' it by removing the bound."""
        from api.crawler import engine

        hosts = [f"https://h{i}.test" for i in range(6)]
        anchors = "".join(f'<a href="{h}/x">l{i}</a>' for i, h in enumerate(hosts))
        html = _home(n=0).replace("</body>", f"{anchors}</body>")

        seen = _Throttle(allowed=99)
        with respx.mock(assert_all_called=False) as mock:
            _site(mock, html)
            for h in hosts:
                mock.route(host=h.split("//")[1]).mock(side_effect=seen)
            await _crawl("job-multihost")

        assert seen.max_inflight > 1, (
            "requests to DIFFERENT hosts were serialised — global parallelism was lost")


class TestAGenuinelyDeadHostIsStillReported:
    """The fix must not become 'stop reporting 503'."""

    async def test_a_host_that_always_503s_is_still_flagged(self):
        with respx.mock(assert_all_called=False) as mock:
            _site(mock, _home(n=2))
            mock.route(host="short.test").mock(return_value=httpx.Response(503))
            issues = await _crawl("job-dead")

        assert any(i.code == "BROKEN_LINK_503" for i in issues), (
            "a host that 503s every single request is a real finding")

    async def test_a_404_is_unaffected(self):
        with respx.mock(assert_all_called=False) as mock:
            _site(mock, _home(n=2))
            mock.route(host="short.test").mock(return_value=httpx.Response(404))
            issues = await _crawl("job-404")

        assert any(i.code == "BROKEN_LINK_404" for i in issues)


# ── EL3/EL4 — 429 ───────────────────────────────────────────────────────────


class TestRateLimitStatusIsRetriedAndDisclosed:
    """429 is the canonical rate-limit response, and LEARNINGS' checklist names
    it first in the retryable list. `fetch_page` retried only 5xx, and
    `issue_for_status` returned None for it — so a 429 was retried zero times and
    then counted as a working link. "Could not check" rendered as "checked, it
    works" (P2)."""

    async def test_a_429_is_retried(self):
        from api.crawler.fetcher import fetch_page, make_client

        calls = {"n": 0}

        async def flaky(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(429)
            return httpx.Response(200, headers={"content-type": "text/html"})

        with respx.mock(assert_all_called=False) as mock:
            mock.route(host="rl.test").mock(side_effect=flaky)
            async with make_client() as c:
                r = await fetch_page("https://rl.test/x", c, is_head=True)
        assert calls["n"] >= 2, "a 429 was not retried"
        assert r.status_code == 200

    async def test_retry_after_is_honoured_but_bounded(self):
        """An hour-long `Retry-After` must not stall the crawl."""
        from api.crawler import fetcher
        from api.crawler.fetcher import fetch_page, make_client

        with respx.mock(assert_all_called=False) as mock:
            mock.route(host="rl.test").mock(
                return_value=httpx.Response(429, headers={"retry-after": "3600"}))
            started = time.monotonic()
            async with make_client() as c:
                await fetch_page("https://rl.test/y", c, is_head=True)
            elapsed = time.monotonic() - started

        cap = getattr(fetcher, "_RETRY_AFTER_MAX_S", 5)
        assert elapsed < cap + 3, (
            f"waited {elapsed:.1f}s on Retry-After: 3600 — the cap is not applied")

    async def test_a_429_that_survives_retries_is_reported_as_unverified(self):
        with respx.mock(assert_all_called=False) as mock:
            _site(mock, _home(n=2))
            mock.route(host="short.test").mock(return_value=httpx.Response(429))
            issues = await _crawl("job-429")

        hits = [i for i in issues if i.code == "EXTERNAL_LINK_TIMEOUT"]
        assert hits, (
            "a rate-limited link produced no finding at all — it was counted as "
            "verified and working")
        assert any(i.extra.get("status_code") == 429 for i in hits), (
            f"the real status is missing from the evidence: {[i.extra for i in hits]}")

    async def test_a_429_is_not_reported_as_broken(self):
        with respx.mock(assert_all_called=False) as mock:
            _site(mock, _home(n=2))
            mock.route(host="short.test").mock(return_value=httpx.Response(429))
            issues = await _crawl("job-429b")

        assert not [i for i in issues if i.code.startswith("BROKEN_LINK")], (
            "a rate limit is not a broken destination")
