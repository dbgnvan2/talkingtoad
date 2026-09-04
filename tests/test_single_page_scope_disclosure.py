"""P6.1 — a single-page scan must not read as a clean audit of the site.

`/scan-page` creates a real job and its docstring says the caller can navigate
straight to `/results/{job_id}`, so a one-page audit lands on the same Results
page as a full crawl. Probed before the fix:

    health_score       = 100        total_issues = 0
    health_score_basis = {'mode': 'all', 'categories_unscored': [],
                          'comparable': True, ...}
    'checks_not_run' in summary       : False
    'checks_not_run' in /results body : False

24 codes carry `needs_full_crawl` and cannot fire on that path. One of them
(`ORPHAN_PAGE`) is disclosed via `orphan_detection`; the other 23 were not, and
`health_score_basis` positively asserted that nothing was unscored.

The consequence, also measured — a full 10-page crawl with ten H1_MISSING
findings, then a one-page scan of one of those pages:

    GET /comparison?previous_job_id=full
      comparable = True   reasons = None
      current = 100  previous = 96  delta health_score = +4

The report said the site improved by four points. One page was looked at instead
of ten. `comparable` is the mechanism built to prevent that; it checks
info_detail, the emission version and the category basis, and a one-page scan
passes all three.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from api.models.issue import Issue
from api.models.job import CrawlJob, CrawlSettings
from api.models.page import CrawledPage

BASE = "https://example.com"


def _needs_full_crawl() -> set[str]:
    """Computed here, from the registry, so a hand-kept copy cannot satisfy it."""
    from api.crawler.checkers.registry import _CATALOGUE

    return {c for c, spec in _CATALOGUE.items() if spec.needs_full_crawl}


async def _single_page_job(store, *, job_id="sp", url=f"{BASE}/about", when=None):
    await store.create_job(CrawlJob(
        job_id=job_id, target_url=url, status="complete", pages_crawled=1,
        settings=CrawlSettings(single_page=True),
        started_at=when or datetime.now(timezone.utc)))
    await store.save_pages([CrawledPage(
        job_id=job_id, url=url, status_code=200, title="t",
        crawled_at=datetime.now(timezone.utc))])


async def _site_job(store, *, job_id="full", pages=10, findings=True, when=None):
    await store.create_job(CrawlJob(
        job_id=job_id, target_url=BASE, status="complete", pages_crawled=pages,
        settings=CrawlSettings(), started_at=when or datetime.now(timezone.utc)))
    await store.save_pages([CrawledPage(
        job_id=job_id, url=f"{BASE}/p{i}", status_code=200, title="t",
        crawled_at=datetime.now(timezone.utc)) for i in range(pages)])
    if findings:
        await store.save_issues([Issue(
            job_id=job_id, page_url=f"{BASE}/p{i}", category="heading",
            severity="warning", issue_code="H1_MISSING", description="d",
            recommendation="r", impact=4) for i in range(pages)])


# ---------------------------------------------------------------------------
# 3.1 / 3.2 / 3.3 — the summary says what could not run
# ---------------------------------------------------------------------------


class TestSummaryDisclosesTheChecksThatCouldNotRun:
    async def test_single_page_summary_names_the_checks_that_could_not_run(
        self, api_client, auth_headers, test_store
    ):
        """3.1 — the 24 codes reach the summary a reader actually looks at."""
        await _single_page_job(test_store)
        s = await test_store.get_summary("sp")
        assert set(s["checks_not_run"]) == _needs_full_crawl()
        assert len(s["checks_not_run"]) == 24, "the fixture's premise moved"
        assert s["checks_not_run_reason"], "a list with no reason is a puzzle"

    async def test_full_crawl_summary_has_no_checks_not_run_key(
        self, api_client, auth_headers, test_store
    ):
        """3.2 — ABSENT, not `[]`.

        An empty disclosure field is a claim that nothing was skipped, and it is
        the failure this repo has now hit twice: `info_excluded: 0` on the PDF
        path (P5.2) and `categories_unscored: []` here. On a full crawl the
        honest encoding is the absence of the key.
        """
        await _site_job(test_store)
        s = await test_store.get_summary("full")
        assert "checks_not_run" not in s, (
            f"a full crawl claimed {s.get('checks_not_run')!r} was skipped"
        )
        assert "checks_not_run_reason" not in s

    async def test_checks_not_run_is_derived_from_the_registry(
        self, api_client, auth_headers, test_store
    ):
        """3.3 — a hand-kept copy that happens to match today must still fail.

        The expected set is computed in the test from `_CATALOGUE`, so marking
        one more code `needs_full_crawl` moves both sides together and a literal
        list moves neither.
        """
        from api.crawler.checkers.registry import _CATALOGUE
        from unittest.mock import patch

        spec = _CATALOGUE["H1_MISSING"]
        widened = dict(_CATALOGUE)
        widened["H1_MISSING"] = spec.__class__(
            **{**{f: getattr(spec, f) for f in spec.__dataclass_fields__},
               "needs_full_crawl": True})

        await _single_page_job(test_store)
        with patch.dict(_CATALOGUE, widened, clear=True):
            s = await test_store.get_summary("sp")
            assert "H1_MISSING" in s["checks_not_run"], (
                "the list did not follow the registry — it is a second copy"
            )


    async def test_the_summary_and_the_endpoint_give_the_SAME_reason(
        self, api_client, auth_headers, test_store
    ):
        """3.3b — flagged by the independent QA gate, not by me.

        The first implementation wrote a fresh reason sentence inline in
        `sqlite_store.get_summary`, with different wording from the router's
        `_CHECKS_NOT_RUN_REASON`, and derived the code list a second time beside
        the router's helper. Both lists were registry-pinned so neither could
        drift silently — but the PHRASE was pinned nowhere, so one fact had two
        wordings on two surfaces. The registry's own comment beside
        `needs_full_crawl` says "do not mirror the list anywhere else".

        Same defect family as P5.2's triplicated "N scored / N not scored"
        (LEARNINGS checklist 17).
        """
        from api.crawler.checkers.registry import (
            CHECKS_NOT_RUN_REASON,
            checks_a_single_page_scan_cannot_run,
        )
        from api.routers.crawl import _CHECKS_NOT_RUN_REASON

        await _single_page_job(test_store)
        s = await test_store.get_summary("sp")
        assert s["checks_not_run_reason"] == CHECKS_NOT_RUN_REASON
        assert _CHECKS_NOT_RUN_REASON == CHECKS_NOT_RUN_REASON, (
            "the router keeps its own wording of the same fact"
        )
        assert s["checks_not_run"] == checks_a_single_page_scan_cannot_run()

    def test_the_reason_and_the_list_are_defined_once(self):
        """3.3c — structural: no second derivation of either, anywhere in api/.

        A behavioural test covers the two surfaces that exist. This is what
        catches the third.
        """
        import re
        from pathlib import Path

        api = Path(__file__).resolve().parent.parent / "api"
        derivations, phrases = [], []
        for path in api.rglob("*.py"):
            if path.name == "registry.py":
                continue                      # the single home
            src = path.read_text()
            for m in re.finditer(r"spec\.needs_full_crawl|\.needs_full_crawl\b", src):
                derivations.append(f"{path.relative_to(api.parent)}:"
                                   f"{src[:m.start()].count(chr(10)) + 1}")
            if "only run during a full crawl" in src or "single-page scan cannot evaluate" in src:
                if "CHECKS_NOT_RUN_REASON" not in src.split("\n")[0]:
                    phrases.append(str(path.relative_to(api.parent)))
        assert not derivations, (
            f"needs_full_crawl is derived outside the registry: {derivations}"
        )
        assert not phrases, (
            f"the reason sentence is spelled out outside the registry: {phrases}"
        )


# ---------------------------------------------------------------------------
# 3.4 / 3.5 / 3.6 — comparability across scopes
# ---------------------------------------------------------------------------


class TestComparabilityAcrossScopes:
    async def test_two_scans_of_the_same_page_stay_comparable(
        self, api_client, auth_headers, test_store
    ):
        """3.5 — written FIRST because it is the one the obvious fix breaks.

        "Single-page scans are never comparable" passes 3.4 and 3.6 and silently
        kills the rescan before/after, which is a shipped feature: re-scanning
        one page and comparing it with its own previous scan is the single
        comparison this scope genuinely supports.
        """
        now = datetime.now(timezone.utc)
        await _single_page_job(test_store, job_id="a", when=now - timedelta(days=1))
        await _single_page_job(test_store, job_id="b", when=now)
        r = await api_client.get("/api/crawl/b/comparison?previous_job_id=a",
                                 headers=auth_headers)
        assert r.status_code == 200, r.text
        assert r.json()["comparable"] is True, (
            f"two scans of the same page must compare: {r.json().get('reasons')}"
        )

    async def test_single_page_scan_is_not_comparable_with_a_site_crawl(
        self, api_client, auth_headers, test_store
    ):
        """3.4 — the fabricated +4.

        Asserts the delta is LABELLED, not withheld: the three existing reasons
        all return the numbers with `comparable: false`, and suppressing the
        comparison would be a different (and worse) behaviour.
        """
        now = datetime.now(timezone.utc)
        await _site_job(test_store, when=now - timedelta(days=1))
        await _single_page_job(test_store, url=f"{BASE}/p0", when=now)
        r = await api_client.get("/api/crawl/sp/comparison?previous_job_id=full",
                                 headers=auth_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["comparable"] is False, (
            "a one-page scan compared with a ten-page crawl as an improvement"
        )
        reasons = " ".join(body.get("reasons") or [body.get("reason") or ""])
        assert "single-page" in reasons.lower(), reasons
        assert body.get("delta") is not None, (
            "the guard labels the comparison; it does not withhold the numbers"
        )

    async def test_two_single_page_scans_of_different_pages_are_not_comparable(
        self, api_client, auth_headers, test_store
    ):
        """3.6 — same scope, different subject. Two measurements, not one trend."""
        now = datetime.now(timezone.utc)
        await _single_page_job(test_store, job_id="a", url=f"{BASE}/about",
                               when=now - timedelta(days=1))
        await _single_page_job(test_store, job_id="b", url=f"{BASE}/contact", when=now)
        r = await api_client.get("/api/crawl/b/comparison?previous_job_id=a",
                                 headers=auth_headers)
        assert r.json()["comparable"] is False, "different pages are not a trend"

    @pytest.mark.parametrize("single,expected_scope,expected_pages", [
        (True, "single_page", 1),
        (False, "site", 10),
    ])
    async def test_basis_carries_the_page_scope_both_ways(
        self, api_client, auth_headers, test_store, single, expected_scope, expected_pages
    ):
        """3.7 — both directions, so a constant satisfies neither."""
        if single:
            await _single_page_job(test_store, job_id="j")
        else:
            await _site_job(test_store, job_id="j")
        s = await test_store.get_summary("j")
        basis = s["health_score_basis"]
        assert basis["page_scope"] == expected_scope
        assert basis["pages_scored"] == expected_pages

    async def test_the_category_meaning_of_comparable_is_unchanged(
        self, api_client, auth_headers, test_store
    ):
        """3.7b — `comparable` still means "the category sets match".

        Widening it to cover page scope would make the three existing reason
        strings wrong and would refuse 3.5. The new fields carry the scope; this
        pins that the old field was not quietly repurposed.
        """
        await _single_page_job(test_store, job_id="j")
        basis = (await test_store.get_summary("j"))["health_score_basis"]
        assert basis["comparable"] is True, (
            "comparable was overloaded with page scope — 3.5 is what that breaks"
        )
        assert basis["mode"] == "all" and basis["categories_unscored"] == []
