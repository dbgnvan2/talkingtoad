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
from api.routers.crawl import get_page_details
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
    tests but the decorator still touches the object."""
    client = type("C", (), {"host": "test"})()
    url = type("U", (), {"path": "/api/crawl/j/page-details"})()
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
    """Everything the endpoint could plausibly disturb."""
    _, by_cat = await store.get_page_issues_by_url("j", PAGE)
    return {
        "issues": sorted((i.issue_code, i.description) for v in by_cat.values() for i in v),
        "fix_history": sorted((h["page_url"], h["issue_code"])
                              for h in await store.get_fix_history("j")),
        "page": (lambda p: (p.url, p.status_code, p.title))(
            (await store.get_page_issues_by_url("j", PAGE))[0]),
    }


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
        from api.services.issue_evidence import UNCAPPED, evidence_lines
        await _seed(store)
        entry = _entry(await _details(store), "UNSAFE_CROSS_ORIGIN_LINK")
        # Rebuild the same lines straight from the renderer on the same extra
        # shape the checker produces, and require identical formatting.
        sample = {"unsafe_links": [{"href": "https://ext0.example.com/x",
                                    "text": "External 0"}],
                  "unsafe_links_total": 1}
        expected, _ = evidence_lines("UNSAFE_CROSS_ORIGIN_LINK", sample, row_cap=UNCAPPED)
        assert any(expected[-1].strip() in ln for ln in entry["items"]), (
            "the endpoint's line format differs from the shared renderer's — "
            "two formatters now exist and will drift")


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
