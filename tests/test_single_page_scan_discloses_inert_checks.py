"""A single-page scan must declare the checks it could not run.

Class this guards (Cycle 2, bug-class elimination):
    `_fetch_and_check_page` -- behind POST /api/crawl/scan-page and the per-page
    rescan button -- never calls check_cross_page, and calls check_page with
    sitemap_urls=None, which check_page guards with `if sitemap_urls is not
    None`. Fourteen codes therefore cannot be produced by a single-page scan.

    Exactly one of the fourteen was disclosed: the 2026-08-29 orphan work writes
    orphan_detection={"status": "skipped_single_page"}. The other thirteen sat
    in the same module behind the same uncalled function and said nothing, so a
    page with no findings was indistinguishable from a page that passed fourteen
    checks that never ran. P5/P12 -- a defect in one path exists in the paths
    modelled on it -- plus the repo's own P31/P24 rule that a suppressed check
    must never render as a clean result.

    Two counting corrections happened while building this, both from deriving
    the set instead of listing it. A grep for make_issue("CODE" found nine; the
    AST walk found fifteen, because six ENTITY_* codes and
    ANALYTICS_ID_INCONSISTENT are emitted from multi-line calls a line-oriented
    pattern misses. Then fifteen became fourteen: CANONICAL_MISSING is emitted
    by cross_page.py AND metadata.py, and metadata.py runs on the single-page
    path, so declaring it un-run was a false claim.

    The asymmetry was visible inside one function: on the authenticated draft
    branch the same endpoint already returns `suppressed_codes` and a caveat
    naming NOT_IN_SITEMAP, while the ordinary branch left it equally
    unevaluated and silent.

Why the flag is derived, not listed:
    The disclosure reads `needs_full_crawl` off the registry, which is the
    repo's declared source of truth for issue metadata. Hardcoding the codes
    in the router would create exactly the hand-mirrored enumeration this
    cycle exists to remove. test_registry_flag_matches_cross_page_emitters
    binds the flag to what cross_page.py actually emits, so a new cross-page
    check that forgets the flag turns red.

Spec: docs/pending/2026-08-31_single-page-scan-inert-checks.md
"""

from __future__ import annotations

import ast
from pathlib import Path

import httpx
import pytest
import respx

from api.crawler.checkers.registry import _CATALOGUE
from api.routers.crawl import _PREPUBLICATION_NOISE_CODES, scan_single_page
from api.services.sqlite_store import SQLiteJobStore

REPO = Path(__file__).resolve().parent.parent
CROSS_PAGE = REPO / "api" / "crawler" / "checkers" / "cross_page.py"

BASE = "https://e.test/"
PAGE = BASE + "a-good-page/"

# A page with nothing wrong with it. The point of the adversarial test: this
# scan returns few or no findings, and must still not read as fully audited.
CLEAN_HTML = (
    "<!DOCTYPE html><html lang='en'><head>"
    "<title>A Perfectly Reasonable Page Title For Testing</title>"
    "<meta name='description' content='"
    + "A sufficiently long and entirely unremarkable meta description. " * 2
    + "'></head><body><h1>A Perfectly Reasonable Heading</h1>"
    "<p>" + " ".join(["word"] * 400) + "</p></body></html>"
)


def _cross_page_emitted_codes() -> set[str]:
    """Codes cross_page.py can emit, read from the source rather than listed.

    A hardcoded copy here would drift the same way the thing under test did.
    """
    tree = ast.parse(CROSS_PAGE.read_text(encoding="utf-8"))
    codes = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "make_issue"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            codes.add(node.args[0].value)
    return codes


def _emitted_by(paths) -> dict[str, set[str]]:
    """Map issue code -> the files that can emit it."""
    out: dict[str, set[str]] = {}
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "make_issue"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                out.setdefault(node.args[0].value, set()).add(path.name)
    return out


# Guarded off on the single-page path despite living in a module that DOES run
# there: NOT_IN_SITEMAP needs `sitemap_urls is not None` and the router passes
# None; HIGH_CRAWL_DEPTH needs `crawl_depth is not None` and parse_page leaves
# it None on this path.
_GUARDED_OFF = {"NOT_IN_SITEMAP", "HIGH_CRAWL_DEPTH"}


def _single_page_modules() -> list[Path]:
    """Everything the single-page path can actually execute.

    Includes api/routers/crawl.py, which runs its OWN external-link pass and
    emits EXTERNAL_LINK_SKIPPED / EXTERNAL_LINK_TIMEOUT. Leaving the router out
    would have declared those two un-run when the endpoint can raise them.
    Excludes engine.py, which is the full-crawl driver — an earlier version of
    this walked all of api/crawler/ INCLUDING engine.py and therefore treated
    ten crawl-only codes as reachable here, under-reporting the disclosure
    while its reason string told the operator the list was complete.
    """
    checkers = [q for q in (REPO / "api" / "crawler" / "checkers").glob("*.py")
                if q.name != "cross_page.py"]
    return checkers + [REPO / "api" / "crawler" / "issue_checker.py",
                       REPO / "api" / "routers" / "crawl.py"]


def _cross_page_emitted_codes() -> set[str]:
    return set(_emitted_by([CROSS_PAGE]))


def _codes_reachable_on_the_single_page_path() -> set[str]:
    return set(_emitted_by(_single_page_modules())) - _GUARDED_OFF


def _expected_unreachable() -> set[str]:
    """Codes a single-page scan genuinely cannot produce.

    NOT "everything cross_page emits" -- that rule was wrong twice. Once
    because CANONICAL_MISSING is emitted by cross_page.py AND metadata.py, and
    metadata.py runs here, so declaring it un-run would send the operator to
    run a full crawl for a check already performed. And once because the
    crawl-only codes in engine.py were missing entirely.
    """
    engine = set(_emitted_by([REPO / "api" / "crawler" / "engine.py"]))
    candidates = _cross_page_emitted_codes() | engine | _GUARDED_OFF
    return {c for c in candidates - _codes_reachable_on_the_single_page_path()
            if c in _CATALOGUE}


def _flagged() -> set[str]:
    return {c for c, s in _CATALOGUE.items() if getattr(s, "needs_full_crawl", False)}


@pytest.fixture
async def store(tmp_path):
    s = SQLiteJobStore(db_path=str(tmp_path / "t.db"))
    await s.init()
    try:
        yield s
    finally:
        await s.close()


async def _scan(store, *, authenticated=False):
    with respx.mock(assert_all_mocked=False, assert_all_called=False) as rx:
        rx.get(PAGE).mock(return_value=httpx.Response(
            200, text=CLEAN_HTML, headers={"content-type": "text/html"}))
        rx.route().mock(return_value=httpx.Response(200, text="ok"))
        return await scan_single_page(url=PAGE, authenticated=authenticated, store=store)


class TestTheFlagIsBoundToReality:
    def test_registry_flag_matches_cross_page_emitters(self):
        """The flagged set is exactly the codes unreachable on the single-page
        path -- cross_page's emitters minus any that another checker can also
        raise, plus NOT_IN_SITEMAP."""
        expected = _expected_unreachable()
        actual = _flagged()
        assert actual == expected, (
            f"registry flag has drifted from the checkers.\n"
            f"  emitted-but-unflagged: {sorted(expected - actual)}\n"
            f"  flagged-but-not-emitted: {sorted(actual - expected)}"
        )

    def test_the_flagged_set_is_not_empty(self):
        """Guards the guard: if the AST walk stopped matching, both sides of
        the comparison above would go empty and the test would pass while
        asserting nothing."""
        assert len(_cross_page_emitted_codes()) >= 7, (
            "cross_page.py emitter extraction found almost nothing — the AST "
            "walk has probably stopped matching make_issue()."
        )


class TestTheScanSaysWhatItDidNotDo:
    async def test_scan_page_declares_checks_it_did_not_run(self, store):
        resp = await _scan(store)
        assert "checks_not_run" in resp, (
            "a single-page scan cannot evaluate 14 checks and said nothing"
        )
        assert set(resp["checks_not_run"]) == _flagged()
        assert resp.get("checks_not_run_reason")

    async def test_adversarial_clean_scan_is_not_reported_as_clean(self, store):
        """What would a correct-looking but wrong result look like?

        HTTP 200 with a low issue count -- indistinguishable from a page that
        passed fourteen checks it never ran. The disclosure must be present
        precisely when there is nothing else to report.
        """
        resp = await _scan(store)
        assert resp["status"] == "complete"
        assert resp["checks_not_run"], (
            "a scan with nothing to report is exactly when an absent "
            "disclosure reads as a clean bill of health"
        )

    async def test_draft_scan_keeps_suppressed_and_not_run_separate(self, store, monkeypatch):
        """`suppressed because pre-publication` and `not run because
        single-page` are different claims about different codes. Merging them
        would let one justify the other."""
        resp = await _scan(store)
        # The ordinary branch must not borrow the draft branch's vocabulary.
        assert "suppressed_codes" not in resp, (
            "an unauthenticated scan suppressed nothing; saying it did would "
            "misdescribe why these checks are missing"
        )
        # An inequality between a 3-element and a 14-element set proves
        # nothing. What must hold is that the two answer different questions:
        # NOINDEX_META is meaningless before publication but IS reachable on
        # this path, so it must never appear in checks_not_run.
        assert "NOINDEX_META" in _PREPUBLICATION_NOISE_CODES
        assert "NOINDEX_META" not in resp["checks_not_run"], (
            "a code that this scan CAN report is being declared un-run — the "
            "pre-publication set and the unreachable set are being conflated"
        )


class TestTheDisclosureDoesNotOverclaim:
    """A disclosure that names a check which DID run is worse than silence: it
    sends the operator to run a full crawl for a result they already have.
    """

    def test_adversarial_a_code_another_checker_can_raise_is_not_declared_unrun(self):
        """CANONICAL_MISSING is the live instance.

        cross_page.py emits it, so the first version of this feature flagged
        it -- but metadata.py emits it too, and metadata.py runs on the
        single-page path. Flagging it was a false claim, caught by asking which
        codes the flagged set contains that some other checker can also raise.
        """
        overclaimed = _flagged() & (_codes_reachable_on_the_single_page_path())
        assert not overclaimed, (
            f"declared un-run, but another checker on the single-page path can "
            f"raise them: {sorted(overclaimed)}"
        )

    def test_canonical_missing_specifically_is_still_reachable(self):
        """Pins the specific regression rather than only the general rule, so a
        future change to the derivation cannot quietly re-introduce it."""
        assert "CANONICAL_MISSING" not in _flagged()
        assert "CANONICAL_MISSING" in _codes_reachable_on_the_single_page_path()


class TestTheRescanPathDisclosesToo:
    """The rescan endpoint runs the same single-page path, so the same codes
    are unreachable — and there the omission is worse: `resolved` can read as
    "these are now fixed" when the check simply never ran.

    That copy of the disclosure had no test; deleting it left the suite green
    while deleting the /scan-page copy turned three red.
    """

    async def test_rescan_declares_checks_it_did_not_run(self, store):
        from datetime import datetime, timezone
        from api.models.job import CrawlJob
        from api.models.page import CrawledPage
        from api.routers.crawl import rescan_url
        from api.crawler.normaliser import normalise_url

        job = CrawlJob(job_id="j1", target_url=BASE,
                       started_at=datetime.now(timezone.utc))
        await store.create_job(job)
        await store.save_pages([CrawledPage(
            job_id="j1", url=normalise_url(PAGE), status_code=200, title="t",
            crawled_at=datetime.now(timezone.utc))])

        with respx.mock(assert_all_mocked=False, assert_all_called=False) as rx:
            rx.get(PAGE).mock(return_value=httpx.Response(
                200, text=CLEAN_HTML, headers={"content-type": "text/html"}))
            rx.route().mock(return_value=httpx.Response(200, text="ok"))
            resp = await rescan_url(job_id="j1", url=PAGE, store=store)

        assert set(resp["checks_not_run"]) == _flagged(), (
            "the rescan response does not declare the checks it could not run"
        )
        assert resp.get("checks_not_run_reason")
