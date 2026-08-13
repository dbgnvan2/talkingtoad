"""Fix Focus — curated priority-fix checklist (SEO + AI/GEO).

Purpose: turn a job's stored issues into a finite, tickable worklist — the highest
         priority fixes, split into SEO and AI/GEO focuses, grouped by page, ordered
         by priority and capped, with per-item checked/verified state.
Spec:    docs/pending/2026-08-13_fix-focus-checklist.md  (FF2–FF5)
Tests:   tests/test_fix_focus.py

Pure functions only — no I/O, no clock. The caller (routers/crawl.py) supplies the
persisted issues and the timestamp, so the builder is deterministic and unit-testable
(a hard requirement for the ordering/cap/reconcile logic). Selection thresholds and
the SEO/GEO split are config in registry.py (P4), never re-literal'd here.
"""

from __future__ import annotations

from typing import Iterable

from api.crawler.checkers.registry import (
    FIX_FOCUS_MAX_PAGES,
    FIX_FOCUS_MIN_IMPACT,
    focus_bucket,
)
from api.models.issue import Issue

# Item lifecycle (FF5.A). A checklist item is one (page_url, issue_code).
STATUS_OPEN = "open"              # not yet touched
STATUS_CHECKED = "checked"        # user ticked it (says "done")
STATUS_VERIFIED = "verified"      # a re-scan confirmed it cleared
STATUS_STILL_PRESENT = "still_present"  # a re-scan found it NOT cleared

_TERMINAL_ON_REGEN = {STATUS_CHECKED, STATUS_VERIFIED, STATUS_STILL_PRESENT}


def _item_from_issue(issue: Issue) -> dict:
    """One checklist item from an Issue (FF2.B — reuses priority_rank/quick_win)."""
    return {
        "issue_code": issue.issue_code,
        "human_description": issue.human_description or issue.issue_code,
        "severity": issue.severity,
        "impact": issue.impact,
        "effort": issue.effort,
        "priority_rank": issue.priority_rank,
        "quick_win": issue.quick_win,
        "status": STATUS_OPEN,
        "checked_at": None,
    }


def _build_focus_list(items_by_page: dict[str, list[dict]], max_pages: int) -> dict:
    """Group→order→cap one focus (FF2.D/FF2.E), announcing the drop (P2/P9)."""
    pages = []
    for url, items in items_by_page.items():
        # Items within a page: priority_rank desc, then issue_code for stability.
        items.sort(key=lambda it: (-it["priority_rank"], it["issue_code"]))
        page_priority = sum(it["priority_rank"] for it in items)
        critical_count = sum(1 for it in items if it["severity"] == "critical")
        pages.append({
            "url": url,
            "page_priority": page_priority,
            "_critical_count": critical_count,
            "items": items,
        })
    # Pages: page_priority desc, then critical count, then item count, then URL.
    pages.sort(key=lambda p: (
        -p["page_priority"], -p["_critical_count"], -len(p["items"]), p["url"],
    ))
    pages_total = len(pages)
    shown = pages[:max_pages]
    items_hidden = sum(len(p["items"]) for p in pages[max_pages:])
    for p in shown:
        p.pop("_critical_count", None)  # internal sort key, not part of the contract
    return {
        "pages": shown,
        "pages_total": pages_total,
        "pages_shown": len(shown),
        "items_hidden": items_hidden,
    }


def build_snapshot(
    issues: Iterable[Issue],
    *,
    generated_at: str,
    scoring_model_version: str | None,
    min_impact: int = FIX_FOCUS_MIN_IMPACT,
    max_pages: int = FIX_FOCUS_MAX_PAGES,
) -> dict:
    """Build the full Fix Focus snapshot from a job's stored issues (FF2).

    - Only page-scoped issues at or above ``min_impact`` (warning+, FF2.C).
    - Deduped by (page_url, issue_code), keeping the highest-priority instance.
    - Split SEO vs GEO by ``focus_bucket`` (FF1), grouped by page, ordered, capped.
    """
    # Dedupe by (page_url, issue_code); keep the highest priority_rank instance so
    # a page can't list the same code twice.
    best: dict[tuple[str, str], Issue] = {}
    for iss in issues:
        if not iss.page_url:
            continue  # site-level issues are out of scope for a per-page checklist
        if iss.impact < min_impact:
            continue
        key = (iss.page_url, iss.issue_code)
        cur = best.get(key)
        if cur is None or iss.priority_rank > cur.priority_rank:
            best[key] = iss

    seo: dict[str, list[dict]] = {}
    geo: dict[str, list[dict]] = {}
    for (page_url, _code), iss in best.items():
        bucket = seo if focus_bucket(iss.category, iss.issue_code) == "seo" else geo
        bucket.setdefault(page_url, []).append(_item_from_issue(iss))

    return {
        "seo": _build_focus_list(seo, max_pages),
        "geo": _build_focus_list(geo, max_pages),
        "generated_at": generated_at,
        "scoring_model_version": scoring_model_version,
    }


def _iter_items(snapshot: dict):
    """Yield (focus, page, item) across both focuses of a snapshot."""
    for focus in ("seo", "geo"):
        for page in snapshot.get(focus, {}).get("pages", []):
            for item in page["items"]:
                yield focus, page, item


def find_item(snapshot: dict, page_url: str, issue_code: str) -> dict | None:
    for _focus, page, item in _iter_items(snapshot):
        if page["url"] == page_url and item["issue_code"] == issue_code:
            return item
    return None


def set_checked(
    snapshot: dict, page_url: str, issue_code: str, *, checked: bool, at: str | None,
) -> dict | None:
    """Toggle an item's checked state (FF4.B / FF3.D). Reversible.

    Returns the updated item, or None if it isn't in the snapshot. A verified /
    still_present item stays as-is on un-check only for its timestamp; the check
    flag maps to open⇄checked and never overwrites a re-scan verdict.
    """
    item = find_item(snapshot, page_url, issue_code)
    if item is None:
        return None
    if checked:
        item["status"] = STATUS_CHECKED
        item["checked_at"] = at
    else:
        item["status"] = STATUS_OPEN
        item["checked_at"] = None
    return item


def merge_checked_state(new_snapshot: dict, old_snapshot: dict | None) -> dict:
    """Regenerate (FF4.C): carry checked/verified/still_present state onto the new
    snapshot for items that persist by (page_url, issue_code). Items that are gone
    simply don't reappear; brand-new items start ``open``."""
    if not old_snapshot:
        return new_snapshot
    prior: dict[tuple[str, str], dict] = {}
    for _focus, page, item in _iter_items(old_snapshot):
        if item["status"] in _TERMINAL_ON_REGEN:
            prior[(page["url"], item["issue_code"])] = item
    for _focus, page, item in _iter_items(new_snapshot):
        keep = prior.get((page["url"], item["issue_code"]))
        if keep is not None:
            item["status"] = keep["status"]
            item["checked_at"] = keep.get("checked_at")
    return new_snapshot


def apply_verify(
    snapshot: dict,
    page_url: str,
    *,
    resolved_codes: Iterable[str],
    present_codes: Iterable[str],
) -> dict:
    """Reconcile one page against a re-scan (FF4.D/FF5).

    ``resolved_codes`` = codes the re-scan says cleared → ``verified``.
    ``present_codes``  = codes the re-scan still sees → ``still_present`` (an
    unfixed item is made visible, never silently dropped — honesty rule / P2).
    Returns ``{verified, still_present, newly_found}`` for the page. ``newly_found``
    = codes the re-scan raised that aren't in the frozen snapshot (surfaced so the
    user can regenerate; they do NOT silently enter the frozen list).
    """
    resolved = set(resolved_codes)
    present = set(present_codes)
    verified: list[str] = []
    still_present: list[str] = []
    snap_codes_on_page: set[str] = set()
    for _focus, page, item in _iter_items(snapshot):
        if page["url"] != page_url:
            continue
        snap_codes_on_page.add(item["issue_code"])
        if item["issue_code"] in resolved:
            item["status"] = STATUS_VERIFIED
            verified.append(item["issue_code"])
        elif item["issue_code"] in present:
            item["status"] = STATUS_STILL_PRESENT
            still_present.append(item["issue_code"])
    newly_found = sorted(present - snap_codes_on_page)
    return {
        "verified": sorted(verified),
        "still_present": sorted(still_present),
        "newly_found": newly_found,
    }
