"""A re-check must report what it checked, and must not resolve what it did not.

Class this guards (Cycle 3, bug-class elimination):
    `rescan_url` computed `resolved_codes = old_codes - new_codes` with no
    filter, and `delete_issues_for_url` deletes EVERY row for the URL. But 24
    catalogue codes carry `needs_full_crawl` and cannot be produced by the
    single-page path at all -- a property AST-bound to the checkers by
    tests/test_single_page_scan_discloses_inert_checks.py, not a guess.

    So on every re-check, each of those codes was deleted from the store,
    removed from the results list and the health score, and written to the
    fixed-issues ledger as resolved, on the strength of a check that never ran.

    The endpoint already knew. The 2026-08-31 work added `checks_not_run` to
    this exact response and did not connect it to `resolved_codes` three lines
    away, so one payload reported a code as resolved AND declared it unchecked.
    Measured against the real endpoint before the fix:

        resolved_codes:  ['ORPHAN_PAGE', 'TITLE_DUPLICATE']
        checks_not_run:  ... includes TITLE_DUPLICATE
        still stored:    neither
        fixed ledger:    ['ORPHAN_PAGE', 'TITLE_DUPLICATE']

    This is E1.2's own reasoning, unapplied to a second case. E1.2 established
    that "no issues found" must not become "all issues fixed" when the fetch
    taught us nothing -- and gated on the FETCH failing. Nothing gated on the
    CHECK not running, which fails on a perfectly successful 200.

    P5/P12 (a defect in one path exists in the paths modelled on it) plus the
    repo's P31/P24 rule that a suppressed check must never render as a pass.

Why the gate is derived, not listed:
    The unrunnable set is read off the registry's `needs_full_crawl` flag via
    _checks_a_single_page_scan_cannot_run(). A literal list in the router would
    recreate the hand-mirrored enumeration D2 exists to prevent, and would go
    stale the first time a cross-page check is added.

Spec: docs/functional-specification.md (D5)
"""
from __future__ import annotations

import httpx
import pytest
import respx

from api.models.issue import Issue
from api.models.job import CrawlJob
from api.models.page import CrawledPage
from api.routers.crawl import _checks_a_single_page_scan_cannot_run, rescan_url
from api.services.sqlite_store import SQLiteJobStore

BASE = "https://e.test/"
PAGE = BASE + "about"  # already normalised — normalise_url strips the trailing slash

# A page with nothing wrong in the metadata the single-page path DOES check.
# The point: the re-check succeeds and finds these codes gone, so any code it
# clears is cleared on real evidence rather than on a failed fetch.
CLEAN_HTML = (
    "<!DOCTYPE html><html lang='en'><head>"
    "<title>An Entirely Reasonable About Page Title</title>"
    "<meta name='description' content='"
    + "A sufficiently long and unremarkable meta description. " * 3
    + "'></head><body><h1>About Us</h1>"
    "<p>" + " ".join(["word"] * 400) + "</p></body></html>"
)

# Two codes the single-page path cannot produce. Chosen from the registry's
# flagged set rather than invented, and asserted to still be in it below.
UNRUNNABLE_SEEDED = ["ORPHAN_PAGE", "TITLE_DUPLICATE"]

# A code the single-page path CAN produce, and which CLEAN_HTML does not have.
# Its presence in `resolved` is what proves the gate did not simply switch
# resolution off altogether.
RUNNABLE_SEEDED = "META_DESC_MISSING"


@pytest.fixture
async def store(tmp_path):
    s = SQLiteJobStore(db_path=str(tmp_path / "t.db"))
    await s.init()
    try:
        yield s
    finally:
        await s.close()


def _issue(code: str, category: str) -> Issue:
    return Issue(
        job_id="j", page_url=PAGE, category=category, severity="warning",
        issue_code=code, description=f"seeded {code}",
        recommendation="fix it", impact=5,
    )


async def _seed(store, codes: list[tuple[str, str]]) -> None:
    await store.create_job(CrawlJob(job_id="j", target_url=BASE))
    await store.save_pages([CrawledPage(
        job_id="j", url=PAGE, status_code=200,
        title="An Entirely Reasonable About Page Title")])
    await store.save_issues([_issue(c, cat) for c, cat in codes])


async def _recheck(store, *, status: int = 200, body: str = CLEAN_HTML):
    with respx.mock(assert_all_mocked=False, assert_all_called=False) as rx:
        rx.get(PAGE).mock(return_value=httpx.Response(
            status, text=body, headers={"content-type": "text/html"}))
        rx.route().mock(return_value=httpx.Response(200, text="ok"))
        res = await rescan_url("j", url=PAGE, store=store)
    assert isinstance(res, dict), f"expected a payload, got {res!r}"
    return res


async def _stored_codes(store) -> set[str]:
    _, by_cat = await store.get_page_issues_by_url("j", PAGE)
    return {i.issue_code for v in by_cat.values() for i in v}


DEFAULT_SEED = [("ORPHAN_PAGE", "crawlability"), ("TITLE_DUPLICATE", "metadata")]


class TestTheSeedIsRealisticNotInvented:
    def test_the_seeded_codes_really_are_unrunnable_here(self):
        """If the registry ever makes these reachable on the single-page path,
        every assertion below becomes vacuous. Fail loudly instead."""
        unrunnable = set(_checks_a_single_page_scan_cannot_run())
        assert set(UNRUNNABLE_SEEDED) <= unrunnable, (
            f"seeded codes are no longer flagged needs_full_crawl: "
            f"{sorted(set(UNRUNNABLE_SEEDED) - unrunnable)} — this test suite "
            f"is now asserting nothing. Pick codes that are still flagged."
        )

    def test_the_runnable_seed_really_is_runnable_here(self):
        """Mirror of the above for the guards-the-guard test."""
        assert RUNNABLE_SEEDED not in set(_checks_a_single_page_scan_cannot_run())


class TestARecheckDoesNotResolveWhatItCannotCheck:
    async def test_a_code_it_cannot_check_is_not_reported_resolved(self, store):
        await _seed(store, DEFAULT_SEED)
        res = await _recheck(store)
        leaked = set(res["resolved_codes"]) & set(UNRUNNABLE_SEEDED)
        assert not leaked, (
            f"{sorted(leaked)} reported resolved by a path that cannot run "
            f"those checks — the operator is told a finding is fixed on the "
            f"strength of a check that never executed")

    async def test_a_code_it_cannot_check_is_not_written_to_the_ledger(self, store):
        """The ledger is the un-undoable half: re-running does not clear it."""
        await _seed(store, DEFAULT_SEED)
        await _recheck(store)
        ledgered = {h["issue_code"] for h in await store.get_fix_history("j")}
        leaked = ledgered & set(UNRUNNABLE_SEEDED)
        assert not leaked, (
            f"{sorted(leaked)} written to the fixed-issues ledger without a "
            f"check behind it")

    async def test_a_code_it_cannot_check_survives_in_the_store(self, store):
        """Not resolving it is not enough — deleting it removes it from the
        results list and the health score just the same."""
        await _seed(store, DEFAULT_SEED)
        await _recheck(store)
        remaining = await _stored_codes(store)
        lost = set(UNRUNNABLE_SEEDED) - remaining
        assert not lost, (
            f"{sorted(lost)} erased from the store by a re-check that could "
            f"not evaluate them")

    async def test_a_carried_over_finding_is_still_in_the_response(self, store):
        """The panel renders from this payload. A finding kept in the database
        but dropped from the response is invisible, which is the same failure."""
        await _seed(store, DEFAULT_SEED)
        res = await _recheck(store)
        returned = {i["issue_code"]: i
                    for v in res["by_category"].values() for i in v}
        for code in UNRUNNABLE_SEEDED:
            assert code in returned, f"{code} missing from the re-check response"
            assert returned[code].get("rechecked") is False, (
                f"{code} returned without rechecked=false, so the panel cannot "
                f"distinguish a re-checked finding from a carried-over one")

    async def test_the_response_names_what_it_carried_over(self, store):
        await _seed(store, DEFAULT_SEED)
        res = await _recheck(store)
        assert res["carried_over_codes"] == sorted(UNRUNNABLE_SEEDED)
        assert res["checks_not_run_reason"], "carried over with no reason given"


class TestTheOutcomeSetsAreCoherent:
    async def test_resolved_still_present_and_newly_found_partition_the_codes(self, store):
        await _seed(store, DEFAULT_SEED + [(RUNNABLE_SEEDED, "metadata")])
        res = await _recheck(store)
        resolved = set(res["resolved_codes"])
        still = set(res["still_present_codes"])
        newly = set(res["newly_found_codes"])
        carried = set(res["carried_over_codes"])
        for a, b, names in ((resolved, still, "resolved/still_present"),
                            (resolved, newly, "resolved/newly_found"),
                            (still, newly, "still_present/newly_found"),
                            (resolved, carried, "resolved/carried_over")):
            assert not (a & b), f"{names} overlap on {sorted(a & b)}"

    async def test_an_unreadable_page_resolves_nothing_and_carries_the_caveat(self, store):
        """E1.2 still holds, and the new keys are present rather than absent —
        a consumer must not have to branch on which shape it got."""
        await _seed(store, DEFAULT_SEED)
        res = await _recheck(store, status=403, body="<html>blocked</html>")
        assert res["page_unreadable"] is True
        assert res["caveat"]
        assert res["resolved_codes"] == []
        for key in ("still_present_codes", "newly_found_codes", "carried_over_codes"):
            assert key in res, f"{key} absent on the unreadable-page branch"
        assert await _stored_codes(store) == set(UNRUNNABLE_SEEDED)


class TestAdversarial:
    """What would a correct-looking but wrong result look like? (CLAUDE.md)"""

    async def test_no_code_is_both_resolved_and_declared_unchecked(self, store):
        """The measured pre-fix output: a green "2 findings resolved" where
        neither check ran, contradicted by `checks_not_run` in the same object."""
        await _seed(store, DEFAULT_SEED)
        res = await _recheck(store)
        contradiction = set(res["resolved_codes"]) & set(res["checks_not_run"])
        assert not contradiction, (
            f"the response reports {sorted(contradiction)} as resolved and "
            f"declares the same codes were not run — one payload, two "
            f"incompatible claims")

    async def test_a_genuinely_fixed_code_is_still_reported_resolved(self, store):
        """Guards the guard. A change that resolved NOTHING would satisfy every
        assertion above while making the re-check useless — which is precisely
        the complaint that started this work."""
        await _seed(store, [(RUNNABLE_SEEDED, "metadata")])
        res = await _recheck(store)
        assert RUNNABLE_SEEDED in res["resolved_codes"], (
            f"{RUNNABLE_SEEDED} is checkable here and the page now has a meta "
            f"description, so the re-check must clear it; the gate has been "
            f"drawn too wide and the feature no longer verifies anything")
        ledgered = {h["issue_code"] for h in await store.get_fix_history("j")}
        assert RUNNABLE_SEEDED in ledgered

    async def test_carrying_over_does_not_resurrect_a_deleted_page_finding(self, store):
        """A too-broad re-save would restore every old issue, making the
        re-check incapable of ever clearing anything while still looking
        like it ran."""
        await _seed(store, DEFAULT_SEED + [(RUNNABLE_SEEDED, "metadata")])
        await _recheck(store)
        assert RUNNABLE_SEEDED not in await _stored_codes(store), (
            f"{RUNNABLE_SEEDED} was carried over although this path checks it "
            f"and the fresh page no longer has it")
