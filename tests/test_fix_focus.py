"""Fix Focus — curated priority-fix checklist.

Spec: docs/pending/2026-08-13_fix-focus-checklist.md  (FF1–FF5)

Covers: bucket totality (FF1.B), min-impact floor (FF2.C), ordering (FF2.D),
cap-announces-drop (FF2.E, real-scale), snapshot persistence + no-rebuild (FF3),
reversible check (FF3.D), regenerate-preserves-status (FF4.C), verify-page
reconcile (FF4.D) incl. an unfixed item staying visible (FF5.A) and the reuse of
the rescan path (FF5.B).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from api.crawler.checkers.registry import (
    _CATALOGUE,
    _ISSUE_SCORING,
    focus_bucket,
)
from api.models.issue import Issue
from api.models.job import CrawlJob
from api.services.fix_focus import (
    apply_verify,
    build_snapshot,
    merge_checked_state,
    set_checked,
    STATUS_CHECKED,
    STATUS_OPEN,
    STATUS_STILL_PRESENT,
    STATUS_VERIFIED,
)
from api.services.sqlite_store import SQLiteJobStore

NOW = "2026-08-13T00:00:00+00:00"


def _issue(page, code, *, category="metadata", impact=6, effort=2,
           severity="warning", priority_rank=None):
    return Issue(
        job_id="j1", page_url=page, category=category, severity=severity,
        issue_code=code, description="d", recommendation="r",
        impact=impact, effort=effort,
        priority_rank=(impact * 10 - effort * 6) if priority_rank is None else priority_rank,
        human_description=f"{code} label",
    )


# ── FF1.B — bucket totality ───────────────────────────────────────────────
def test_ff1b_every_code_buckets_exactly_once():
    """Every catalogue code resolves to exactly one bucket ('seo' or 'geo')."""
    for code, spec in _CATALOGUE.items():
        b = focus_bucket(spec.category, code)
        assert b in ("seo", "geo"), f"{code} → {b!r}"
    # sample membership
    assert focus_bucket("metadata", "TITLE_MISSING") == "seo"
    assert focus_bucket("ai_readiness", "GEO_SUMMARY_BURIED") == "geo"
    assert focus_bucket("broken_link", "PLACEHOLDER_LINK") == "geo"


# ── FF2.C — min-impact floor ──────────────────────────────────────────────
def test_ff2c_min_impact_floor():
    """Info-level issues (impact < floor) are excluded; warning+ included."""
    issues = [
        _issue("https://x.org/a", "TITLE_MISSING", impact=7, severity="warning"),
        _issue("https://x.org/a", "GEO_SUMMARY_BURIED", category="ai_readiness",
               impact=2, severity="info"),  # below floor → excluded
    ]
    snap = build_snapshot(issues, generated_at=NOW, scoring_model_version="v",
                          min_impact=4)
    seo_codes = [it["issue_code"] for p in snap["seo"]["pages"] for it in p["items"]]
    assert seo_codes == ["TITLE_MISSING"]
    assert snap["geo"]["pages"] == []  # the info geo issue was floored out


# ── FF2.D — deterministic ordering ────────────────────────────────────────
def test_ff2d_ordering_deterministic():
    """Pages by summed priority desc; items within a page by priority_rank desc."""
    issues = [
        # page /low: one mid item
        _issue("https://x.org/low", "META_DESC_MISSING", impact=5, effort=2),
        # page /high: two items, higher summed priority
        _issue("https://x.org/high", "TITLE_MISSING", impact=9, effort=1),
        _issue("https://x.org/high", "H1_MISSING", category="heading", impact=6, effort=2),
    ]
    snap = build_snapshot(issues, generated_at=NOW, scoring_model_version="v")
    pages = snap["seo"]["pages"]
    assert [p["url"] for p in pages] == ["https://x.org/high", "https://x.org/low"]
    high_items = [it["issue_code"] for it in pages[0]["items"]]
    assert high_items == ["TITLE_MISSING", "H1_MISSING"]  # 84 then 48
    assert pages[0]["page_priority"] == (9 * 10 - 6) + (6 * 10 - 12)


# ── FF2.E — cap announces the drop (real-scale, P9) ───────────────────────
def test_ff2e_cap_announces_drop():
    issues = [
        _issue(f"https://x.org/p{i}", "TITLE_MISSING", impact=6, effort=2)
        for i in range(12)
    ]
    snap = build_snapshot(issues, generated_at=NOW, scoring_model_version="v",
                          max_pages=10)
    seo = snap["seo"]
    assert seo["pages_total"] == 12
    assert seo["pages_shown"] == 10
    assert len(seo["pages"]) == 10
    assert seo["items_hidden"] == 2  # the two dropped pages, one item each


# ── FF3.D — reversible check ──────────────────────────────────────────────
def test_ff3d_check_toggle_reversible():
    snap = build_snapshot(
        [_issue("https://x.org/a", "TITLE_MISSING")],
        generated_at=NOW, scoring_model_version="v")
    it = set_checked(snap, "https://x.org/a", "TITLE_MISSING", checked=True, at=NOW)
    assert it["status"] == STATUS_CHECKED and it["checked_at"] == NOW
    it = set_checked(snap, "https://x.org/a", "TITLE_MISSING", checked=False, at=None)
    assert it["status"] == STATUS_OPEN and it["checked_at"] is None
    # unknown item → None
    assert set_checked(snap, "https://x.org/a", "NOPE", checked=True, at=NOW) is None


# ── FF4.C — regenerate preserves status for surviving items ───────────────
def test_ff4c_regenerate_preserves_status():
    old = build_snapshot(
        [_issue("https://x.org/a", "TITLE_MISSING"),
         _issue("https://x.org/a", "META_DESC_MISSING")],
        generated_at=NOW, scoring_model_version="v")
    set_checked(old, "https://x.org/a", "TITLE_MISSING", checked=True, at=NOW)
    # new scan: TITLE_MISSING persists, META_DESC_MISSING gone, H1 new
    new = build_snapshot(
        [_issue("https://x.org/a", "TITLE_MISSING"),
         _issue("https://x.org/a", "H1_MISSING", category="heading")],
        generated_at=NOW, scoring_model_version="v")
    merged = merge_checked_state(new, old)
    codes = {it["issue_code"]: it for p in merged["seo"]["pages"] for it in p["items"]}
    assert codes["TITLE_MISSING"]["status"] == STATUS_CHECKED  # preserved
    assert codes["H1_MISSING"]["status"] == STATUS_OPEN        # brand new
    assert "META_DESC_MISSING" not in codes                    # gone


# ── FF4.D / FF5.A — verify-page reconcile from the ABSOLUTE live set ───────
def test_ff4d_verify_page_reconciles_and_ff5a_unfixed_visible():
    """A snapshot item absent from the re-scan's live set is verified (this also
    covers the already-cleared case — the code is simply not present, with no
    reliance on a since-last-scan delta, sweep finding 1); a present one is
    still_present; a live code not in the snapshot is newly_found."""
    snap = build_snapshot(
        [_issue("https://x.org/a", "TITLE_MISSING"),
         _issue("https://x.org/a", "META_DESC_MISSING")],
        generated_at=NOW, scoring_model_version="v")
    # ABSOLUTE current set: META still there + a NEW code; TITLE no longer present.
    outcome = apply_verify(
        snap, "https://x.org/a",
        present_codes=["META_DESC_MISSING", "CANONICAL_MISSING"])
    assert outcome["verified"] == ["TITLE_MISSING"]          # not present → verified
    assert outcome["still_present"] == ["META_DESC_MISSING"]  # NOT silently dropped
    assert outcome["newly_found"] == ["CANONICAL_MISSING"]    # surfaced, not injected
    codes = {it["issue_code"]: it for p in snap["seo"]["pages"] for it in p["items"]}
    assert codes["TITLE_MISSING"]["status"] == STATUS_VERIFIED
    assert codes["META_DESC_MISSING"]["status"] == STATUS_STILL_PRESENT
    # newly_found did not enter the frozen list
    assert "CANONICAL_MISSING" not in codes


def test_ff4d_already_cleared_item_verifies_on_empty_rescan():
    """Sweep finding 1 (regression): if the page was already fixed (re-scan sees
    NOTHING), every snapshot item on it verifies — not left stuck 'open'."""
    snap = build_snapshot(
        [_issue("https://x.org/a", "TITLE_MISSING")],
        generated_at=NOW, scoring_model_version="v")
    outcome = apply_verify(snap, "https://x.org/a", present_codes=[])
    assert outcome["verified"] == ["TITLE_MISSING"]
    codes = {it["issue_code"]: it for p in snap["seo"]["pages"] for it in p["items"]}
    assert codes["TITLE_MISSING"]["status"] == STATUS_VERIFIED


# ── FF3 — persistence: snapshot saved on a job and survives reload ─────────
async def test_ff3_snapshot_persists_and_no_rebuild():
    async with SQLiteJobStore(db_path=":memory:") as store:
        await store.create_job(CrawlJob(
            job_id="j1", target_url="https://x.org", status="complete"))
        await store.save_issues([_issue("https://x.org/a", "TITLE_MISSING")])
        snap = build_snapshot(
            await store.get_all_issues("j1"),
            generated_at=NOW, scoring_model_version="v")
        await store.update_job("j1", fix_focus=snap)
        # reload from a fresh get_job — the blob round-trips through SQLite TEXT
        job = await store.get_job("j1")
        assert job.fix_focus == snap
        assert job.fix_focus["seo"]["pages"][0]["items"][0]["issue_code"] == "TITLE_MISSING"


# Guard: the scoring source-of-truth the snapshot relies on is intact.
def test_ff2b_priority_rank_source_exists():
    assert "TITLE_MISSING" in _ISSUE_SCORING


# ── Phase 4 U4.5 — the third state: not_checked ───────────────────────────
def test_u45_unchecked_codes_are_neither_verified_nor_still_present():
    """A code the single-page re-scan cannot evaluate (needs a full crawl) is
    reported as not checked — never as a pass, never as a fail (P31)."""
    from api.services.fix_focus import STATUS_NOT_CHECKED
    snap = build_snapshot(
        [_issue("https://x.org/a", "TITLE_MISSING"),
         _issue("https://x.org/a", "ORPHAN_PAGE")],
        generated_at=NOW, scoring_model_version="v")
    outcome = apply_verify(snap, "https://x.org/a", present_codes=["ORPHAN_PAGE"],
                           unchecked_codes=["ORPHAN_PAGE"])
    assert outcome["verified"] == ["TITLE_MISSING"]
    assert outcome["still_present"] == []
    assert outcome["not_checked"] == ["ORPHAN_PAGE"]
    assert outcome["newly_found"] == [], "an unchecked code carried over is not 'newly found'"
    codes = {it["issue_code"]: it for p in snap["seo"]["pages"] for it in p["items"]}
    assert codes["ORPHAN_PAGE"]["status"] == STATUS_NOT_CHECKED


def test_u45_absent_unchecked_still_not_verified():
    """The carried-over code is absent from the live set (it was never looked
    for). Without the third state it would have read as verified."""
    from api.services.fix_focus import STATUS_NOT_CHECKED
    snap = build_snapshot([_issue("https://x.org/a", "ORPHAN_PAGE")], generated_at=NOW, scoring_model_version="v")
    outcome = apply_verify(snap, "https://x.org/a", present_codes=[], unchecked_codes=["ORPHAN_PAGE"])
    assert outcome["verified"] == [] and outcome["not_checked"] == ["ORPHAN_PAGE"]
    codes = {it["issue_code"]: it for p in snap["seo"]["pages"] for it in p["items"]}
    assert codes["ORPHAN_PAGE"]["status"] == STATUS_NOT_CHECKED


def test_u45_default_is_the_old_behaviour():
    snap = build_snapshot([_issue("https://x.org/a", "TITLE_MISSING")], generated_at=NOW, scoring_model_version="v")
    outcome = apply_verify(snap, "https://x.org/a", present_codes=[])
    assert outcome["not_checked"] == [] and outcome["verified"] == ["TITLE_MISSING"]


def test_u45_checked_item_keeps_its_tick_when_not_checked():
    """Sweep finding: the user's tick is their claim, not the scan's. A code the
    re-scan could not evaluate must not erase it, and Regenerate must not reset it."""
    from api.services.fix_focus import STATUS_CHECKED, merge_checked_state, set_checked
    snap = build_snapshot([_issue("https://x.org/a", "ORPHAN_PAGE")], generated_at=NOW, scoring_model_version="v")
    set_checked(snap, "https://x.org/a", "ORPHAN_PAGE", checked=True, at=NOW)
    outcome = apply_verify(snap, "https://x.org/a", present_codes=[], unchecked_codes=["ORPHAN_PAGE"])
    item = next(it for p in snap["seo"]["pages"] for it in p["items"])
    assert item["status"] == STATUS_CHECKED and item["rechecked"] == "not_checked"
    assert outcome["not_checked"] == ["ORPHAN_PAGE"]
    fresh = build_snapshot([_issue("https://x.org/a", "ORPHAN_PAGE")], generated_at=NOW, scoring_model_version="v")
    merged = merge_checked_state(fresh, snap)
    assert next(it for p in merged["seo"]["pages"] for it in p["items"])["status"] == STATUS_CHECKED
