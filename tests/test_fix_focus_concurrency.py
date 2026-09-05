"""P8.1 — a second writer must not silently un-do the first one's ticks.

Every Fix Focus mutation was `load snapshot -> mutate in memory -> update_job(
fix_focus=whole_snapshot)`. One JSON column, no version, no transaction.
Measured before the fix, two panels each un-ticking a DIFFERENT item:

    sequential HTTP (each re-reads before writing)
      {'H1_MISSING': 'checked', 'TITLE_MISSING': 'checked'}      correct

    two tabs (BOTH read, then BOTH write)
      {'H1_MISSING': 'checked', 'TITLE_MISSING': 'open'}

Tab A un-ticked H1_MISSING and wrote; tab B, holding a snapshot fetched before
that write, restored it to `checked`. No error, nothing on screen.

The likelier trigger is not two tabs. `verify-page` read the snapshot, then held
it across a live single-page re-crawl — seconds of network — and wrote it
afterwards, so anything the operator ticked meanwhile was discarded. That needs
one person, not two.
"""

from __future__ import annotations

import asyncio
import copy
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from api.models.issue import Issue
from api.models.job import CrawlJob, CrawlSettings
from api.models.page import CrawledPage

BASE = "https://e.com"
P1, P2 = f"{BASE}/p1", f"{BASE}/p2"


async def _seeded(store, job_id="j"):
    await store.create_job(CrawlJob(
        job_id=job_id, target_url=BASE, status="complete", pages_crawled=2,
        settings=CrawlSettings(), started_at=datetime.now(timezone.utc)))
    await store.save_pages([CrawledPage(
        job_id=job_id, url=u, status_code=200, title="t",
        crawled_at=datetime.now(timezone.utc)) for u in (P1, P2)])
    await store.save_issues([
        Issue(job_id=job_id, page_url=P1, category="heading", severity="warning",
              issue_code="H1_MISSING", description="d", recommendation="r", impact=6),
        Issue(job_id=job_id, page_url=P2, category="metadata", severity="warning",
              issue_code="TITLE_MISSING", description="d", recommendation="r", impact=6),
    ])


def _ticks(snapshot) -> dict[str, str]:
    return {it["issue_code"]: it["status"]
            for field in ("seo", "geo") if snapshot and snapshot.get(field)
            for page in snapshot[field]["pages"] for it in page["items"]}


async def _check(api_client, headers, page_url, code, checked, job_id="j"):
    return await api_client.post(
        f"/api/crawl/{job_id}/fix-focus/check", headers=headers,
        json={"page_url": page_url, "issue_code": code, "checked": checked})


class TestTwoWritersDoNotLoseEachOther:
    async def test_two_tabs_ticking_different_items_both_survive(
        self, api_client, auth_headers, test_store
    ):
        """3.1 — the measurement above, as a test.

        BOTH read before EITHER writes. A test using sequential HTTP calls passes
        today and proves nothing — that is precisely the fixture that would have
        let this ship.
        """
        from api.services.fix_focus import set_checked

        await _seeded(test_store)
        await api_client.get("/api/crawl/j/fix-focus", headers=auth_headers)
        await _check(api_client, auth_headers, P1, "H1_MISSING", True)
        await _check(api_client, auth_headers, P2, "TITLE_MISSING", True)

        job = await test_store.get_job("j")
        tab_a = copy.deepcopy(job.fix_focus)
        tab_b = copy.deepcopy(job.fix_focus)      # both tabs hold the same snapshot

        await test_store.mutate_fix_focus(
            "j", lambda s: set_checked(s, P1, "H1_MISSING", checked=False, at=None))
        await test_store.mutate_fix_focus(
            "j", lambda s: set_checked(s, P2, "TITLE_MISSING", checked=False, at=None))
        assert tab_a is not tab_b   # the stale copies exist; neither may be written whole

        ticks = _ticks((await test_store.get_job("j")).fix_focus)
        assert ticks == {"H1_MISSING": "open", "TITLE_MISSING": "open"}, (
            f"one writer's un-tick was overwritten by the other: {ticks}"
        )

    async def test_same_item_from_two_tabs_is_last_write_wins(
        self, api_client, auth_headers, test_store
    ):
        """3.3 — the other direction, and the over-correction guard.

        The tempting fix is to reject any write against a stale snapshot with a
        409. That fixes 3.1 and turns two people ticking the SAME checkbox into
        an error the panel has no handling for. Two writers asserting the same
        fact about the same item is not a conflict.
        """
        from api.services.fix_focus import set_checked

        await _seeded(test_store)
        await api_client.get("/api/crawl/j/fix-focus", headers=auth_headers)

        await test_store.mutate_fix_focus(
            "j", lambda s: set_checked(s, P1, "H1_MISSING", checked=True, at="t1"))
        r = await _check(api_client, auth_headers, P1, "H1_MISSING", False)
        assert r.status_code == 200, r.text
        assert _ticks((await test_store.get_job("j")).fix_focus)["H1_MISSING"] == "open"

    async def test_the_mutation_re_reads_inside_the_lock(
        self, api_client, auth_headers, test_store
    ):
        """3.4 — the helper must hand `mutate` the CURRENT snapshot.

        A helper that merely wraps the caller's already-loaded snapshot in a
        transaction changes nothing: the staleness happened before the lock.
        """
        from api.services.fix_focus import set_checked

        await _seeded(test_store)
        await api_client.get("/api/crawl/j/fix-focus", headers=auth_headers)
        await test_store.mutate_fix_focus(
            "j", lambda s: set_checked(s, P1, "H1_MISSING", checked=True, at="t1"))

        seen: list[str] = []

        def _observe(snapshot):
            seen.append(_ticks(snapshot)["H1_MISSING"])
            return set_checked(snapshot, P2, "TITLE_MISSING", checked=True, at="t2")

        await test_store.mutate_fix_focus("j", _observe)
        assert seen == ["checked"], (
            f"the mutation was handed a snapshot without the earlier write: {seen}"
        )

    async def test_a_failing_mutation_leaves_the_snapshot_unchanged(
        self, api_client, auth_headers, test_store
    ):
        """3.6 — a half-applied mutation is never persisted.

        Honest about what this proves. The property holds by ORDERING — the
        UPDATE runs only after `mutate` returns — not by the rollback, and a
        mutation testing pass confirmed it: replacing `rollback()` with
        `commit()` in the except branch leaves this test green, because the
        failure happens before anything was written. The rollback is defensive
        cover for a failure between the UPDATE and the COMMIT, which the current
        code cannot produce; it is not what this test exercises.

        What it does pin is the thing an operator would feel: a mutation that
        modifies the snapshot and then raises must not leave that half-change in
        the database.
        """
        from api.services.fix_focus import set_checked

        await _seeded(test_store)
        await api_client.get("/api/crawl/j/fix-focus", headers=auth_headers)
        await test_store.mutate_fix_focus(
            "j", lambda s: set_checked(s, P1, "H1_MISSING", checked=True, at="t1"))
        before = _ticks((await test_store.get_job("j")).fix_focus)

        def _explodes(snapshot):
            set_checked(snapshot, P2, "TITLE_MISSING", checked=True, at="t2")
            raise RuntimeError("mutation failed halfway")

        with pytest.raises(RuntimeError):
            await test_store.mutate_fix_focus("j", _explodes)

        assert _ticks((await test_store.get_job("j")).fix_focus) == before, (
            "a half-applied mutation was committed"
        )


class TestRegenerateAlsoKeepsTicks:
    async def test_a_tick_during_a_regenerate_is_not_discarded(
        self, api_client, auth_headers, test_store
    ):
        """3.8 — the gate's finding 2, as a test.

        `regenerate` rebuilds from current issues and merges the operator's ticks
        forward. My structural guard could not see it: the write lexically lived
        inside `_load_or_build_fix_focus`, exempt because "a first build has
        nothing to lose" — true of a build, false of a REBUILD that merges state.

        The staleness is made exact rather than raced: the route is handed a job
        whose `fix_focus` is the pre-tick copy (which is what reading it before a
        concurrent write means), while the store holds the tick. Merging the
        stale copy loses it; merging inside the transaction keeps it.
        """
        import copy as _copy

        from api.services.fix_focus import set_checked

        await _seeded(test_store)
        await api_client.get("/api/crawl/j/fix-focus", headers=auth_headers)

        stale_job = await test_store.get_job("j")
        stale_job.fix_focus = _copy.deepcopy(stale_job.fix_focus)   # the pre-tick read

        # The concurrent tick, applied through the store after that read.
        await test_store.mutate_fix_focus(
            "j", lambda s: set_checked(s, P1, "H1_MISSING", checked=True, at="t1"))

        real_get_job = test_store.get_job

        async def _stale_get_job(job_id):
            return stale_job if job_id == "j" else await real_get_job(job_id)

        with patch.object(test_store, "get_job", _stale_get_job):
            r = await api_client.post("/api/crawl/j/fix-focus/regenerate",
                                      headers=auth_headers)
        assert r.status_code == 200, r.text

        ticks = _ticks((await real_get_job("j")).fix_focus)
        assert ticks["H1_MISSING"] == "checked", (
            f"regenerate merged the copy it read at request start, discarding a "
            f"tick that had landed since: {ticks}"
        )


class TestTheOperatorAndTheBackgroundJob:
    async def test_a_tick_made_during_a_verify_is_not_discarded(
        self, api_client, auth_headers, test_store
    ):
        """3.2 — the likelier case, and the one 3.1 cannot reach.

        `verify-page` used to read the snapshot, then hold it across a live
        re-crawl, then write it. Anything ticked during the fetch was discarded.
        That is about ORDERING, not locking: a correct lock around a stale read
        still loses the tick. The rescan is patched to be slow, and a tick lands
        while it is in flight.
        """
        await _seeded(test_store)
        await api_client.get("/api/crawl/j/fix-focus", headers=auth_headers)

        async def _slow_rescan(job_id, *, url, store):
            await asyncio.sleep(0.15)
            return {"url": url, "status_code": 200, "by_category": {},
                    "checks_not_run": [], "checks_not_run_reason": "r"}

        with patch("api.routers.crawl.rescan_url", AsyncMock(side_effect=_slow_rescan)):
            verify = asyncio.create_task(api_client.post(
                f"/api/crawl/j/fix-focus/verify-page?url={P2}", headers=auth_headers))
            await asyncio.sleep(0.05)          # the operator ticks mid-crawl
            tick = await _check(api_client, auth_headers, P1, "H1_MISSING", True)
            assert tick.status_code == 200, tick.text
            r = await verify
            assert r.status_code == 200, r.text

        ticks = _ticks((await test_store.get_job("j")).fix_focus)
        assert ticks["H1_MISSING"] == "checked", (
            "a tick made while the verify's re-crawl was in flight was discarded "
            f"when the verify wrote its pre-fetch snapshot: {ticks}"
        )


def test_no_mutating_route_writes_a_whole_snapshot():
    """3.5 — structural. The next mutating route is where this comes back.

    A behavioural test covers the two routes that exist; only this covers the
    third. `_load_or_build_fix_focus` is exempt: building a snapshot that did not
    exist has nothing to lose.
    """
    import re
    from pathlib import Path

    src = (Path(__file__).resolve().parent.parent / "api" / "routers" / "crawl.py").read_text()
    def _enclosing_def(pos: int) -> str:
        """The nearest preceding `def`/`async def` — a fixed-size window is not
        enough: the builder's own write sits ~700 chars below its signature, and
        a 400-char lookback silently exempted nothing and flagged it instead."""
        starts = [m for m in re.finditer(r"^(?:async )?def (\w+)", src, re.M)
                  if m.start() < pos]
        return starts[-1].group(1) if starts else ""

    offenders = []
    for m in re.finditer(r"update_job\([^)]*fix_focus\s*=", src, re.S):
        if _enclosing_def(m.start()) == "_load_or_build_fix_focus":
            continue
        offenders.append(f"crawl.py:{src[:m.start()].count(chr(10)) + 1}")
    assert not offenders, (
        "a route writes a whole fix_focus snapshot outside the store's "
        f"transaction — use store.mutate_fix_focus: {offenders}"
    )
