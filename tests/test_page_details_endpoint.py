"""D6 — the offending items for a page, read live and stored nowhere.

Owner report: "when I go to update a page, the code being reported e.g. unsafe
external links, doesn't report what links are the problem. This is similar for
many codes. Can the page audit show this, but not bother to store it?"

What this guards:
    The evidence has existed since 2026-08-29 (EV) and reaches the payload on
    every issue as `evidence` / `evidence_total`. Two bounds kept it thin:
    EVIDENCE_ROW_CAP (10) at render, and scattered literal slices at capture.
    Measured on a page with 25 unsafe cross-origin links -- 25 parsed, 20 kept
    in `extra`, 10 rendered.

    This endpoint lifts the RENDER cap so every captured row is returned, from
    a fresh read of the page rather than from crawl-time storage, and states
    what it still cannot show. It must never store anything: that is the whole
    point of "don't bother to store it", and it is also what keeps this path
    safe to call repeatedly from a button.

The failure this file exists to catch:
    `_fetch_and_check_page` is shared with rescan_url, which DOES write. A
    details endpoint that drifted into writing would silently mutate findings
    every time an operator opened a detail panel -- and, via the same path D5
    just fixed, could resolve and ledger codes nobody asked it to touch.
    test_details_writes_nothing_to_the_store is the guard, and it compares the
    whole store rather than one table.

Spec: docs/functional-specification.md (D6)
"""
from __future__ import annotations

import httpx
import pytest
import respx

from api.models.issue import Issue
from api.models.job import CrawlJob
from api.models.page import CrawledPage
from api.routers.crawl import _fetch_and_check_page, get_page_details
from api.services.issue_evidence import EVIDENCE_ROW_CAP, PAGE_IS_THE_EVIDENCE
from api.services.sqlite_store import SQLiteJobStore

BASE = "https://e.test/"
PAGE = BASE + "about"

# 25 unsafe cross-origin links: target="_blank" with no rel="noopener". More
# than the render cap (10) and more than the capture cap (20), so this one page
# exercises both bounds at once.
UNSAFE_LINK_COUNT = 25
HTML = (
    "<!DOCTYPE html><html lang='en'><head>"
    "<title>An Entirely Reasonable About Page Title</title>"
    "<meta name='description' content='"
    + "A sufficiently long and unremarkable meta description. " * 3
    + "'></head><body><h1>About Us</h1>"
    + "".join(
        f"<a href='https://ext{i}.example.com/x' target='_blank'>External {i}</a>"
        for i in range(UNSAFE_LINK_COUNT)
    )
    + "<p>" + " ".join(["word"] * 400) + "</p></body></html>"
)


class _Req:
    """slowapi reads request.client / request.url; the limiter is disabled in
    tests but the decorator still touches the object.

    NOTE the path below is deliberately NOT the real route. It used to read
    "/api/crawl/j/page-details", and `tests/test_endpoint_coverage.py` -- the CI
    guard whose entire job is catching un-wired endpoints -- regex-searches the
    TEXT of the test files for each registered path. That literal satisfied the
    guard without a single HTTP request ever being made, so deleting both route
    decorators left the whole 3563-test suite green. The guard was handed the
    string it looks for. Real coverage now comes from TestClientContract below.
    """
    client = type("C", (), {"host": "test"})()
    url = type("U", (), {"path": "/unit-call-not-a-route"})()
    headers: dict = {}
    method = "GET"
    scope: dict = {"client": ("test", 0), "type": "http", "headers": []}
    state = type("S", (), {})()


@pytest.fixture
async def store(tmp_path):
    s = SQLiteJobStore(db_path=str(tmp_path / "t.db"))
    await s.init()
    try:
        yield s
    finally:
        await s.close()


async def _seed(store) -> None:
    await store.create_job(CrawlJob(job_id="j", target_url=BASE))
    await store.save_pages([CrawledPage(job_id="j", url=PAGE, status_code=200,
                                        title="An Entirely Reasonable About Page Title")])
    await store.save_issues([Issue(
        job_id="j", page_url=PAGE, category="security", severity="warning",
        issue_code="UNSAFE_CROSS_ORIGIN_LINK", description="seeded",
        recommendation="add rel=noopener", impact=1,
        extra={"unsafe_link_count": 3,
               "unsafe_links": [{"href": "https://stored.example.com/a", "text": "Stored"}],
               "unsafe_links_total": 3},
    )])


async def _details(store, *, code=None, status=200, body=HTML):
    with respx.mock(assert_all_mocked=False, assert_all_called=False) as rx:
        rx.get(PAGE).mock(return_value=httpx.Response(
            status, text=body, headers={"content-type": "text/html"}))
        rx.route().mock(return_value=httpx.Response(200, text="ok"))
        res = await get_page_details(_Req(), "j", url=PAGE, code=code, store=store)
    assert isinstance(res, dict), f"expected a payload, got {res!r}"
    return res


def _entry(res, code):
    for d in res["details"]:
        if d["issue_code"] == code:
            return d
    raise AssertionError(f"{code} not in {[d['issue_code'] for d in res['details']]}")


async def _snapshot(store) -> dict:
    """Every row of every table.

    The first version of this hand-picked three page fields, two issue fields
    and the fix ledger -- and the 2026-09-01 sweep proved it could not detect
    the write it was named for. Inserting the verbatim `save_pages(...)` that
    `rescan_url` performs left all 16 tests green, because the 37 fields it
    changes were not among the three read back, and the seeded title and status
    happened to match the live parse. `update_issue_extra` was invisible too --
    which is the field the endpoint's own stored-fallback branch reads.

    So: dump the database. A guard against "did anything change" must look at
    everything, or it is a guard against "did the four things I thought of
    change".
    """
    db = store._db
    async with db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ) as cur:
        tables = [r[0] for r in await cur.fetchall()]
    assert tables, "no tables found — the snapshot would be vacuously equal"
    out: dict = {}
    for table in tables:
        async with db.execute(f"SELECT * FROM {table}") as cur:  # noqa: S608 — names from sqlite_master
            rows = await cur.fetchall()
        out[table] = sorted(repr(tuple(r)) for r in rows)
    return out


class TestItReturnsTheItems:
    async def test_details_returns_every_captured_row_not_just_ten(self, store):
        await _seed(store)
        res = await _details(store)
        entry = _entry(res, "UNSAFE_CROSS_ORIGIN_LINK")
        link_lines = [ln for ln in entry["items"] if "ext" in ln and "example.com" in ln]
        assert len(link_lines) > EVIDENCE_ROW_CAP, (
            f"only {len(link_lines)} links returned; the list endpoints already "
            f"show {EVIDENCE_ROW_CAP}, so this endpoint added nothing")

    async def test_details_names_the_actual_hrefs(self, store):
        """The owner's literal request: which links are the problem."""
        await _seed(store)
        entry = _entry(await _details(store), "UNSAFE_CROSS_ORIGIN_LINK")
        blob = "\n".join(entry["items"])
        assert "https://ext0.example.com/x" in blob
        assert "External 0" in blob, "anchor text dropped — the href alone is hard to find on a page"

    async def test_details_states_the_true_total_and_flags_capture_truncation(self, store):
        await _seed(store)
        entry = _entry(await _details(store), "UNSAFE_CROSS_ORIGIN_LINK")
        assert entry["items_total"] == UNSAFE_LINK_COUNT, (
            f"total says {entry['items_total']}, page has {UNSAFE_LINK_COUNT}")
        assert entry["truncated_at_capture"] is True, (
            "the crawler kept fewer rows than the page has and the response did "
            "not say so — a short list that looks complete")

    async def test_details_for_a_single_code(self, store):
        await _seed(store)
        res = await _details(store, code="UNSAFE_CROSS_ORIGIN_LINK")
        assert [d["issue_code"] for d in res["details"]] == ["UNSAFE_CROSS_ORIGIN_LINK"]

    async def test_details_for_all_codes_returns_more_than_one(self, store):
        await _seed(store)
        res = await _details(store)
        assert len(res["details"]) > 1, "the no-code form must cover the whole page"

    async def test_a_page_is_the_evidence_code_is_labelled_not_blank(self, store):
        await _seed(store)
        res = await _details(store)
        page_basis = [d for d in res["details"] if d["evidence_basis"] == "page"]
        assert page_basis, (
            "no finding reported evidence_basis='page'; the panel then cannot "
            "distinguish 'nothing to list' from 'nothing recorded'")
        for d in page_basis:
            assert d["issue_code"] in PAGE_IS_THE_EVIDENCE


class TestItStoresNothing:
    async def test_details_writes_nothing_to_the_store(self, store):
        """The load-bearing guard. _fetch_and_check_page is shared with
        rescan_url, which deletes, re-saves and writes the fixed-issues
        ledger."""
        await _seed(store)
        before = await _snapshot(store)
        await _details(store)
        assert await _snapshot(store) == before, (
            "the details endpoint mutated the store — it must be read-only")

    async def test_details_does_not_resolve_anything(self, store):
        await _seed(store)
        await _details(store)
        assert await store.get_fix_history("j") == [], (
            "a read-only detail view wrote to the fixed-issues ledger")


class TestUnreadablePages:
    async def test_an_unreadable_page_is_labelled_stored_not_live(self, store):
        await _seed(store)
        res = await _details(store, status=403, body="<html>blocked</html>")
        assert res["page_unreadable"] is True
        assert res["source"] == "stored"
        assert res["caveat"]

    async def test_an_unreadable_page_still_returns_what_was_stored(self, store):
        """Degrade to crawl-time data, clearly labelled — do not go blank."""
        await _seed(store)
        res = await _details(store, status=429, body="<html>slow down</html>")
        entry = _entry(res, "UNSAFE_CROSS_ORIGIN_LINK")
        assert any("stored.example.com" in ln for ln in entry["items"])


class TestAdversarial:
    """What would a correct-looking but wrong result look like? (CLAUDE.md)"""

    async def test_an_unreadable_page_does_not_render_stored_evidence_as_live(self, store):
        """Third appearance of this shape (E1.2, D5, here). The operator asks
        "what is on my page NOW", the fetch is blocked, and crawl-time links
        come back under a live heading — so they re-fix links they already
        fixed, or trust a stale all-clear."""
        await _seed(store)
        res = await _details(store, status=403, body="<html>blocked</html>")
        assert res["source"] != "live", (
            "a page that could not be read reported its items as live")
        entry = _entry(res, "UNSAFE_CROSS_ORIGIN_LINK")
        blob = "\n".join(entry["items"])
        assert "ext0.example.com" not in blob, (
            "live-looking data leaked into the blocked-page response")

    async def test_a_successful_read_is_not_labelled_stored(self, store):
        """The mirror. A gate that always says 'stored' would pass the test
        above while making the feature useless."""
        await _seed(store)
        res = await _details(store)
        assert res["source"] == "live" and res["page_unreadable"] is False

    async def test_live_details_do_not_echo_the_stale_stored_row(self, store):
        """The seeded issue names stored.example.com, which is NOT on the page.
        If it appears in a live answer, the endpoint is reading the database
        somewhere it should be reading the page."""
        await _seed(store)
        entry = _entry(await _details(store), "UNSAFE_CROSS_ORIGIN_LINK")
        assert not any("stored.example.com" in ln for ln in entry["items"])

    async def test_an_empty_item_list_is_never_silently_empty(self, store):
        """A code with no items must still declare its basis, so a blank panel
        cannot read as 'nothing wrong here'."""
        await _seed(store)
        res = await _details(store)
        for d in res["details"]:
            if not d["items"]:
                assert d["evidence_basis"] in {"page", "items"}, (
                    f"{d['issue_code']} returned no items and no basis")

    async def test_the_shared_renderer_is_used_not_a_second_one(self, store):
        """Guards the guard: consumes the real evidence_lines rather than
        mocking it, so a private formatter that drifts from the PDF/Excel/panel
        output turns this red."""
        from api.services.issue_evidence import UNCAPPED, evidence_summary
        await _seed(store)

        # Capture the exact `extra` the live check produced, then require the
        # endpoint's `items` to equal the shared renderer's output for it,
        # ELEMENT FOR ELEMENT.
        #
        # The first version asserted `any(expected[-1] in ln for ln in items)` —
        # one row's substring, which is defined by _row_to_line, not by
        # evidence_lines. The sweep replaced the call with a private inline
        # formatter that emitted no "<Label>:" heading, no "... and N more"
        # disclosure and no _NOISE_KEYS filtering, and all 16 tests stayed
        # green. Every structural difference was invisible to it.
        with respx.mock(assert_all_mocked=False, assert_all_called=False) as rx:
            rx.get(PAGE).mock(return_value=httpx.Response(
                200, text=HTML, headers={"content-type": "text/html"}))
            rx.route().mock(return_value=httpx.Response(200, text="ok"))
            check = await _fetch_and_check_page(
                url=PAGE, job_id="j", base_url=BASE, store=store,
                check_external_links=False)
        live = next(i for i in check.issues
                    if i.issue_code == "UNSAFE_CROSS_ORIGIN_LINK")
        expected, total, rendered = evidence_summary(
            "UNSAFE_CROSS_ORIGIN_LINK", live.extra, row_cap=UNCAPPED)

        entry = _entry(await _details(store), "UNSAFE_CROSS_ORIGIN_LINK")
        assert entry["items"] == expected, (
            "the endpoint's items differ from the shared renderer's output — "
            "a second formatter exists and will drift from the PDF, the Excel "
            "export and CategoryPanel")
        assert entry["items_total"] == total
        assert entry["items_shown"] == rendered
        # Structure the substring assertion could not see.
        assert any(ln.endswith(":") for ln in entry["items"]), "no heading line"


class TestTheRenderCapLiftIsRaceFree:
    def test_lifting_the_cap_for_one_caller_does_not_leak_to_another(self):
        """evidence_for_excel used to swap a module global. Under async
        endpoints that global is shared by concurrent requests, so an uncapped
        render could leak into a capped one, or a restore could truncate one
        mid-flight."""
        from api.services import issue_evidence
        from api.services.issue_evidence import UNCAPPED, evidence_lines

        extra = {"unsafe_links": [{"href": f"https://x{i}.test/", "text": f"L{i}"}
                                  for i in range(30)],
                 "unsafe_links_total": 30}
        before = issue_evidence.EVIDENCE_ROW_CAP
        big, _ = evidence_lines("UNSAFE_CROSS_ORIGIN_LINK", extra, row_cap=UNCAPPED)
        small, _ = evidence_lines("UNSAFE_CROSS_ORIGIN_LINK", extra)
        assert issue_evidence.EVIDENCE_ROW_CAP == before, (
            "the module global moved — the cap is still being swapped, not passed")
        assert len(big) > len(small), "row_cap had no effect"
        assert len(small) <= before + 2, "the default render is no longer capped"


class TestClientContract:
    """Through the ASGI app, over HTTP, with a real Authorization header.

    Every other test in this file calls `get_page_details(...)` as a plain
    Python function. The 2026-09-01 sweep deleted BOTH route decorators and ran
    the entire suite: 3563 passed. The endpoint was completely unregistered and
    nothing went red -- including `test_endpoint_coverage.py`, which was
    satisfied by a path literal inside the `_Req` stub above.

    So nothing bound this endpoint to its URL, its auth, its query validation or
    its error codes. These tests are that binding. If the route decorator is
    removed, they 404.
    """

    async def _seed_app_store(self, test_store):
        await test_store.create_job(CrawlJob(job_id="j", target_url=BASE))
        await test_store.save_pages([CrawledPage(
            job_id="j", url=PAGE, status_code=200, title="About")])
        await test_store.save_issues([Issue(
            job_id="j", page_url=PAGE, category="security", severity="warning",
            issue_code="UNSAFE_CROSS_ORIGIN_LINK", description="seeded",
            recommendation="add rel=noopener", impact=1,
            extra={"unsafe_links": [{"href": "https://stored.example.com/a",
                                     "text": "Stored"}],
                   "unsafe_links_total": 1},
        )])

    async def test_the_route_is_registered_and_answers(self, api_client, auth_headers, test_store):
        await self._seed_app_store(test_store)
        with respx.mock(assert_all_mocked=False, assert_all_called=False) as rx:
            rx.get(PAGE).mock(return_value=httpx.Response(
                200, text=HTML, headers={"content-type": "text/html"}))
            rx.route().mock(return_value=httpx.Response(200, text="ok"))
            r = await api_client.get(
                f"/api/crawl/j/page-details?url={PAGE}", headers=auth_headers)
        assert r.status_code == 200, (
            f"the route did not answer: {r.status_code} {r.text[:200]}")
        body = r.json()
        assert body["source"] == "live"
        assert any(d["issue_code"] == "UNSAFE_CROSS_ORIGIN_LINK"
                   for d in body["details"])

    async def test_it_requires_auth(self, api_client, test_store):
        await self._seed_app_store(test_store)
        r = await api_client.get(f"/api/crawl/j/page-details?url={PAGE}")
        assert r.status_code in (401, 403), (
            f"the endpoint answered without a token: {r.status_code}")

    async def test_a_missing_url_is_a_422_not_a_500(self, api_client, auth_headers, test_store):
        await self._seed_app_store(test_store)
        r = await api_client.get("/api/crawl/j/page-details", headers=auth_headers)
        assert r.status_code == 422

    async def test_an_unknown_job_is_404(self, api_client, auth_headers):
        r = await api_client.get(
            f"/api/crawl/nope/page-details?url={PAGE}", headers=auth_headers)
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "JOB_NOT_FOUND"

    async def test_an_uncrawled_url_is_404(self, api_client, auth_headers, test_store):
        await self._seed_app_store(test_store)
        r = await api_client.get(
            f"/api/crawl/j/page-details?url={BASE}never-crawled",
            headers=auth_headers)
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "PAGE_NOT_FOUND"

    async def test_a_home_page_stored_under_the_bare_origin_still_opens(
            self, api_client, auth_headers, test_store):
        """P8 — ND3 (2026-09-02) made `normalise_url` map the bare origin to the
        root path, and this endpoint normalises before an EXACT store lookup.
        Every job crawled before that change stored its home page under the bare
        spelling — 43 pages across 39 jobs in the development database — so the
        normalised lookup misses and the button that worked yesterday returns
        PAGE_NOT_FOUND. The stored spelling has to be tried too."""
        bare = "https://e.test"          # exactly as pre-ND3 jobs stored it
        await test_store.create_job(CrawlJob(job_id="old", target_url=bare))
        await test_store.save_pages([CrawledPage(
            job_id="old", url=bare, status_code=200, title="Home")])
        await test_store.save_issues([Issue(
            job_id="old", page_url=bare, category="security", severity="warning",
            issue_code="UNSAFE_CROSS_ORIGIN_LINK", description="seeded",
            recommendation="add rel=noopener", impact=1,
            extra={"unsafe_links": [{"href": "https://stored.example.com/a"}],
                   "unsafe_links_total": 1})])

        with respx.mock(assert_all_mocked=False, assert_all_called=False) as rx:
            rx.route().mock(return_value=httpx.Response(
                200, text=HTML, headers={"content-type": "text/html"}))
            r = await api_client.get(
                f"/api/crawl/old/page-details?url={bare}", headers=auth_headers)
        assert r.status_code == 200, (
            f"a page stored under the bare origin no longer opens: {r.text[:200]}")


class TestAGonePageIsNotACleanPage:
    """A 404 is conclusive, so this took the LIVE branch and returned details
    containing only BROKEN_LINK_404. The panel then found no entry for the code
    it asked about and rendered the green "This finding is no longer on the page
    as it is now" — for a page that had been unpublished. Every stored finding
    reported itself cleared. Same shape as D5, through the branch D5 did not
    cover. Found by the 2026-09-01 cold sweep.
    """

    GONE = "<!DOCTYPE html><html><head><title>Not found</title></head>" \
           "<body><h1>Page not found</h1></body></html>"

    async def test_a_gone_page_says_so_and_does_not_omit_the_code(self, store):
        await _seed(store)
        res = await _details(store, code="UNSAFE_CROSS_ORIGIN_LINK",
                             status=404, body=self.GONE)
        assert res["page_gone"] is True
        assert res["caveat"], "a 404 came back with no explanation"
        entry = _entry(res, "UNSAFE_CROSS_ORIGIN_LINK")
        assert entry["evaluated"] is False, (
            "the code was reported as evaluated on a page that returns 404 — "
            "the panel renders a missing/clean entry as 'no longer on the page'")
        assert entry["not_evaluated_reason"]

    async def test_a_live_200_still_marks_entries_evaluated(self, store):
        """The mirror: a gate that marked everything un-evaluated would satisfy
        the test above and destroy the feature."""
        await _seed(store)
        entry = _entry(await _details(store), "UNSAFE_CROSS_ORIGIN_LINK")
        assert entry["evaluated"] is True


class TestChecksThatDidNotRunAreNamed:
    async def test_link_codes_are_reported_unevaluated_not_absent(self, store):
        """External links are no longer re-checked here (one click used to cost
        up to 50 outbound third-party requests). Their absence from the results
        must therefore not read as 'fixed'."""
        await store.create_job(CrawlJob(job_id="j", target_url=BASE))
        await store.save_pages([CrawledPage(job_id="j", url=PAGE, status_code=200,
                                            title="About")])
        await store.save_issues([Issue(
            job_id="j", page_url=PAGE, category="broken_link", severity="info",
            issue_code="BROKEN_LINK_404", description="dead", recommendation="fix",
            impact=2, extra={"target_url": "https://dead.example.com/x"})])
        entry = _entry(await _details(store, code="BROKEN_LINK_404"),
                       "BROKEN_LINK_404")
        assert entry["evaluated"] is False
        assert "not re-checked" in entry["not_evaluated_reason"].lower() or \
               "not re-checked here" in entry["not_evaluated_reason"].lower()

    async def test_a_full_crawl_only_code_is_reported_unevaluated(self, store):
        await store.create_job(CrawlJob(job_id="j", target_url=BASE))
        await store.save_pages([CrawledPage(job_id="j", url=PAGE, status_code=200,
                                            title="About")])
        await store.save_issues([Issue(
            job_id="j", page_url=PAGE, category="metadata", severity="warning",
            issue_code="TITLE_DUPLICATE", description="dup", recommendation="fix",
            impact=5)])
        entry = _entry(await _details(store, code="TITLE_DUPLICATE"), "TITLE_DUPLICATE")
        assert entry["evaluated"] is False


class TestTruncationArithmetic:
    """`truncated_at_capture` compared evidence ROWS against rendered LINES.
    `items` also holds one heading per key and an "... and N more" line, so the
    flag read False whenever the real gap was smaller than that overhead. The
    original test passed only because its fixture gap (25 vs 20) exceeded it —
    the assertion was satisfied by an arithmetically wrong formula."""

    async def test_a_small_capture_gap_is_still_flagged(self, store):
        from api.routers.crawl import _details_for_issues

        issue = Issue(
            job_id="j", page_url=PAGE, category="security", severity="warning",
            issue_code="UNSAFE_CROSS_ORIGIN_LINK", description="d",
            recommendation="r", impact=1,
            # 3 rows kept, 4 on the page: a gap of ONE, smaller than the
            # heading + "and N more" overhead that the old formula counted.
            extra={"unsafe_links": [{"href": f"https://x{i}.test/", "text": f"L{i}"}
                                    for i in range(3)],
                   "unsafe_links_total": 4},
        )
        entry = _details_for_issues([issue], only_code=None)[0]
        assert entry["items_total"] == 4
        assert entry["items_shown"] == 3
        assert entry["truncated_at_capture"] is True, (
            "a genuine capture gap of 1 was not flagged — the flag is "
            "comparing rows against line count again")

    async def test_an_untruncated_finding_is_not_flagged(self, store):
        from api.routers.crawl import _details_for_issues

        issue = Issue(
            job_id="j", page_url=PAGE, category="security", severity="warning",
            issue_code="UNSAFE_CROSS_ORIGIN_LINK", description="d",
            recommendation="r", impact=1,
            extra={"unsafe_links": [{"href": f"https://x{i}.test/", "text": f"L{i}"}
                                    for i in range(3)],
                   "unsafe_links_total": 3},
        )
        entry = _details_for_issues([issue], only_code=None)[0]
        assert entry["truncated_at_capture"] is False


class TestEvidenceBasisOnTheListEndpoint:
    """`_evidence_fields` is what /page-issues returns and what the Page Audit
    actually branches on — `basis !== 'page'` gates the "Get full details"
    button and picks NoItemsToList's wording. The sweep set `basis = "items"`
    unconditionally and the whole 3563-test suite stayed green, because
    evidence_basis was asserted only for `_details_for_issues`, and the frontend
    fixture hardcodes the value neither side actually produces.

    Under that mutation all 30 PAGE_IS_THE_EVIDENCE codes render "No specific
    items were recorded... Use Get full details" and offer a button that can
    only ever return nothing — the misleading empty box D6 exists to remove.
    """

    def test_a_page_is_the_evidence_code_reports_basis_page(self):
        from api.routers.crawl import _issue_dict

        payload = _issue_dict(Issue(
            job_id="j", page_url=PAGE, category="metadata", severity="info",
            issue_code="TITLE_MISSING", description="d", recommendation="r"))
        assert payload["evidence_basis"] == "page", (
            "TITLE_MISSING is in PAGE_IS_THE_EVIDENCE; reporting 'items' makes "
            "the panel offer a live read that cannot help and word the empty "
            "state as 'nothing recorded'")

    def test_an_item_naming_code_reports_basis_items(self):
        from api.routers.crawl import _issue_dict

        payload = _issue_dict(Issue(
            job_id="j", page_url=PAGE, category="security", severity="warning",
            issue_code="UNSAFE_CROSS_ORIGIN_LINK", description="d",
            recommendation="r"))
        assert payload["evidence_basis"] == "items"

    def test_the_two_bases_are_actually_different(self):
        """Guards the guard: both assertions above would pass if the field were
        hardwired to whichever value each expects. This one fails if the
        function returns a constant."""
        from api.routers.crawl import _issue_dict

        def basis(code, category):
            return _issue_dict(Issue(
                job_id="j", page_url=PAGE, category=category, severity="info",
                issue_code=code, description="d", recommendation="r"))["evidence_basis"]

        assert basis("TITLE_MISSING", "metadata") != basis(
            "UNSAFE_CROSS_ORIGIN_LINK", "security")

    def test_evidence_rows_counts_rows_not_lines(self):
        """The frontend's "Get full details" gate reads this. If it were
        len(evidence), an issue with 11-12 captured rows would compare equal to
        its total and offer no button while printing "... and 2 more"."""
        from api.routers.crawl import _issue_dict

        payload = _issue_dict(Issue(
            job_id="j", page_url=PAGE, category="security", severity="warning",
            issue_code="UNSAFE_CROSS_ORIGIN_LINK", description="d",
            recommendation="r",
            extra={"unsafe_links": [{"href": f"https://x{i}.test/", "text": f"L{i}"}
                                    for i in range(20)],
                   "unsafe_links_total": 20}))
        # 10 rows rendered (default cap) + 1 heading + 1 "... and N more" line.
        assert payload["evidence_rows"] == 10
        assert len(payload["evidence"]) == 12
        assert payload["evidence_total"] == 20


class TestTheSharedFetchPathBlocksRedirectsBeforeFollowing:
    """`_fetch_and_check_page` — the shared body of `/page-details`,
    `/rescan-url` and `/scan-page` — used `make_client()`.

    `fetch_page` does re-check `redirect_chain + [final_url]`, but only AFTER
    httpx has followed the hop, so a public host 302-ing to 169.254.169.254 had
    that request ISSUED and the response merely discarded. Blind SSRF: side
    effects fire, nothing is exfiltrated. CLAUDE.md requires private IPs blocked
    "at start *and* on every redirect hop", and the repo already had
    `make_ssrf_guarded_client()`, which refuses the Location header before
    following it — used at six other call sites but not this one.

    Found by the 2026-09-01 cold sweep as inherited, not introduced. Fixed for
    all three endpoints at once, and pinned here so it cannot be swapped back.
    """

    async def test_a_redirect_to_an_internal_host_is_never_requested(self, store, monkeypatch):
        from api.crawler import fetcher

        await _seed(store)
        requested: list[str] = []
        monkeypatch.setattr(
            fetcher, "is_ssrf_safe", lambda url: "169.254.169.254" not in str(url))

        with respx.mock(assert_all_mocked=False, assert_all_called=False) as rx:
            rx.get(PAGE).mock(return_value=httpx.Response(
                302, headers={"location": "http://169.254.169.254/latest/meta-data/"}))

            def _record(request):
                requested.append(str(request.url))
                return httpx.Response(200, text="SECRET", headers={"content-type": "text/html"})

            rx.get("http://169.254.169.254/latest/meta-data/").mock(side_effect=_record)
            rx.route().mock(return_value=httpx.Response(200, text="ok"))
            res = await get_page_details(_Req(), "j", url=PAGE, code=None, store=store)

        assert requested == [], (
            f"the internal host was actually requested ({requested}) — the "
            f"redirect was followed and only then rejected, which is the blind "
            f"SSRF this path is supposed to refuse")
        # And the endpoint degrades honestly rather than pretending it read the page.
        if isinstance(res, dict):
            assert res.get("source") != "live" or res.get("page_unreadable") is True

    async def test_an_ordinary_redirect_still_works(self, store):
        """The mirror: a guard that refused every redirect would pass the test
        above and break every site that redirects to a canonical URL."""
        await _seed(store)
        with respx.mock(assert_all_mocked=False, assert_all_called=False) as rx:
            rx.get(PAGE).mock(return_value=httpx.Response(
                301, headers={"location": f"{BASE}about-us"}))
            rx.get(f"{BASE}about-us").mock(return_value=httpx.Response(
                200, text=HTML, headers={"content-type": "text/html"}))
            rx.route().mock(return_value=httpx.Response(200, text="ok"))
            res = await get_page_details(_Req(), "j", url=PAGE, code=None, store=store)
        assert isinstance(res, dict)
        assert res["source"] == "live", "a legitimate redirect was refused"
