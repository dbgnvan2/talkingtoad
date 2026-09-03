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
    async def test_ten_links_to_one_host_produce_no_finding_at_all(self):
        """The self-throttling case. This asserted `BROKEN_LINK_503 not in codes`
        when it was written, and the cold sweep proved that cannot fail: BB3
        (same day) means an external 503 never produces that code whatever the
        concurrency, so the whole EL1/EL2 fix could be reverted and this stayed
        green while the crawler throttled itself 17 times (P27).

        The assertion is now the outcome that actually depends on the fix: a host
        that only refuses CONCURRENT requests answers every one of them when we
        ask politely, so there is nothing to report."""
        throttle = _Throttle(allowed=1)
        with respx.mock(assert_all_called=False) as mock:
            _site(mock, _home())
            mock.route(host="short.test").mock(side_effect=throttle)
            issues = await _crawl("job-throttle")

        codes = [i.code for i in issues if i.code.startswith(("BROKEN_LINK", "EXTERNAL_LINK"))]
        assert codes == [], (
            f"the crawler throttled itself and reported it: {codes} "
            f"(max concurrent to one host: {throttle.max_inflight}, "
            f"throttled responses: {throttle.throttled})")
        assert throttle.throttled == 0, (
            f"{throttle.throttled} requests were refused for concurrency")

    async def test_repeated_requests_to_one_host_are_actually_spaced(self):
        """`_EXT_PER_HOST_DELAY_S` had no test at all — setting it to 0.0 left
        the whole suite green (cold sweep)."""
        import time as _t

        from api.crawler import engine

        stamps: list[float] = []

        async def clock(request):
            stamps.append(_t.monotonic())
            return httpx.Response(200, headers={"content-type": "text/html"})

        with respx.mock(assert_all_called=False) as mock:
            _site(mock, _home(n=4))
            mock.route(host="short.test").mock(side_effect=clock)
            await _crawl("job-spacing")

        assert len(stamps) >= 4, stamps
        gaps = [b - a for a, b in zip(stamps, stamps[1:])]
        delay = engine._EXT_PER_HOST_DELAY_S
        assert all(g >= delay * 0.8 for g in gaps), (
            f"requests to one host were not spaced by ~{delay}s: {gaps}")

    def test_the_spacing_sleep_is_outside_the_global_semaphore(self):
        """D6 — a STRUCTURAL guard, and honest about being one.

        The spacing sleep must not be held inside the global semaphore: a host
        serving out its politeness debt would occupy a slot another host could
        use (measured 0.79s vs 0.56s over 50 links / 25 hosts). Two behavioural
        shapes were tried first — wall clock and peak concurrent requests — and
        BOTH passed with the defect reinstated, so neither was kept: a test that
        passes either way claims a guard that does not exist (P27).

        This reads the source instead, the way `test_wp_audit.py::TestReadOnly`
        asserts the audit never writes. It cannot prove the timing. It catches
        the one edit that reintroduces the defect, which is what was actually
        wanted.
        """
        import inspect
        import re

        from api.crawler import engine

        src = inspect.getsource(engine.run_crawl)
        body = src[src.index("async def _check_one"):]
        body = body[:body.index("tasks = [_check_one")]

        sleep_at = body.index("await asyncio.sleep(slot - now)")
        sem_at = body.index("async with sem:")
        assert sleep_at < sem_at, (
            "the per-host spacing sleep is inside `async with sem` — a host "
            "waiting out its politeness debt is holding a global slot")
        # And the host semaphore IS held across it, or the spacing spaces nothing.
        host_at = body.index("async with host_sem:")
        assert host_at < sleep_at, "the spacing sleep is outside the per-host lock"
        # The slot is reserved before the await, not recomputed after it: the
        # read-modify-write used to straddle the sleep, so a per-host bound above
        # 1 turned the delay into bursts.
        assert body.index("_host_next_ok[host] = slot") < sleep_at, (
            "the next-slot reservation happens after the sleep, not before")

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
    """The fix must not become 'stop reporting 503' — the link still has to
    appear, whatever we call it."""

    async def test_a_host_that_always_503s_is_still_reported(self):
        """This asserted `BROKEN_LINK_503` when it was written. BB3 (same day)
        then established that an EXTERNAL 503 cannot be distinguished from a
        bot-block and is reported as unverified — so the expectation changed and
        the guard did not: the link must still be surfaced, never silently
        counted as working. The "must not stop reporting 503" intent now lives
        in tests/test_bot_blocked_destinations.py, which pins that an INTERNAL
        503 keeps `BROKEN_LINK_503`."""
        with respx.mock(assert_all_called=False) as mock:
            _site(mock, _home(n=2))
            mock.route(host="short.test").mock(return_value=httpx.Response(503))
            issues = await _crawl("job-dead")

        hits = [i for i in issues if i.code in ("BROKEN_LINK_503", "EXTERNAL_LINK_SKIPPED")]
        assert hits, (
            "a host that 503s every single request vanished from the report — "
            "unverified must not mean unmentioned")
        assert any(i.extra.get("status_code") == 503 for i in hits), (
            f"the status that produced it is missing: {[i.extra for i in hits]}")

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

    async def test_a_short_retry_after_is_actually_waited(self):
        """The "honoured" half of the bounded-Retry-After test was unguarded:
        ignoring the header entirely also satisfies "did not wait an hour"."""
        import time as _t

        from api.crawler.fetcher import fetch_page, make_client

        with respx.mock(assert_all_called=False) as mock:
            mock.route(host="rl.test").mock(
                return_value=httpx.Response(429, headers={"retry-after": "2"}))
            started = _t.monotonic()
            async with make_client() as c:
                await fetch_page("https://rl.test/slow", c, is_head=True)
            elapsed = _t.monotonic() - started
        assert elapsed >= 1.5, (
            f"Retry-After: 2 was ignored — returned in {elapsed:.2f}s")

    @pytest.mark.parametrize("header", [
        "9" * 400,          # 309-4300 digits: int() succeeds, float() overflows
        "9" * 320,
        "-5", "0", "5.5", "not-a-number", "", "   ",
        "Wed, 21 Oct 2015 07:28:00 GMT",      # a date in the past
        "Fri, 31 Dec 2199 23:59:59 GMT",      # far future — must still cap
    ])
    async def test_a_hostile_retry_after_never_crashes_the_crawl(self, header):
        """`float(int(raw))` caught only ValueError. A 309-to-4300-digit header
        raises OverflowError, which escapes `fetch_page` — whose `try` catches
        only httpx errors — and aborts the entire crawl. The header is parsed on
        EVERY response, so the audited site's own home page carrying it returned
        a silent zero-page audit. Third-party controllable: any outbound link on
        the site can point at a host that sends it (P5/P2)."""
        from api.crawler import fetcher
        from api.crawler.fetcher import _retry_after_seconds

        class _R:
            headers = {"retry-after": header}

        got = _retry_after_seconds(_R())
        assert got is None or 0.0 <= got <= fetcher._RETRY_AFTER_MAX_S, got

    async def test_a_hostile_retry_after_does_not_abort_a_crawl(self):
        with respx.mock(assert_all_called=False) as mock:
            _site(mock, _home(n=1))
            mock.route(host="short.test").mock(return_value=httpx.Response(
                503, headers={"retry-after": "9" * 400}))
            issues = await _crawl("job-hostile-header")
        assert issues, "the crawl produced nothing — it aborted"

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

        hits = [i for i in issues if i.code == "EXTERNAL_LINK_SKIPPED"]
        assert hits, (
            "a rate-limited link produced no finding at all — it was counted as "
            "verified and working")
        assert any(i.extra.get("status_code") == 429 for i in hits), (
            f"the real status is missing from the evidence: {[i.extra for i in hits]}")

    async def test_a_rate_limit_is_not_filed_as_a_slow_link(self):
        """Cold sweep (P14). 429 was routed to EXTERNAL_LINK_TIMEOUT, whose whole
        help surface says the destination did not answer: "Slow External Link",
        "did not respond — destination may be slow or unavailable", "may be
        leaving supporters staring at a blank screen". The destination answered
        instantly and told us to slow down. Worse, the honest inline description
        did not survive: collapsed with a genuine connect-failure on the same
        page, one row absorbed the other and which `status_code` won was decided
        by completion order. A rate limit means the same thing as a bot-block —
        we could not verify — so it belongs with it."""
        with respx.mock(assert_all_called=False) as mock:
            _site(mock, _home(n=2))
            mock.route(host="short.test").mock(return_value=httpx.Response(429))
            issues = await _crawl("job-429-not-slow")

        assert not [i for i in issues if i.code == "EXTERNAL_LINK_TIMEOUT"], (
            "a rate limit is reported under a code that says the link was slow")

    async def test_a_429_is_not_reported_as_broken(self):
        with respx.mock(assert_all_called=False) as mock:
            _site(mock, _home(n=2))
            mock.route(host="short.test").mock(return_value=httpx.Response(429))
            issues = await _crawl("job-429b")

        assert not [i for i in issues if i.code.startswith("BROKEN_LINK")], (
            "a rate limit is not a broken destination")
