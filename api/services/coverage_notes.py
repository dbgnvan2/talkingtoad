"""Coverage disclosures shared by the export surfaces (PDF, Excel).

A check that was suppressed must never reach a client as a clean result —
the whole point of recording why it did not run (P31).
"""

from __future__ import annotations
# O2 — one wording for every export surface, so the PDF and the workbook cannot
# drift apart. `complete` is the only status that licenses reading zero orphans
# as "no orphans found" (P31); each other value says the check did not run.
_ORPHAN_SKIP_WHY = {
    "skipped_partial_scan": "this was a partial scan, so pages outside the selected content types were never fetched",
    "skipped_truncated": "the crawl stopped at its page limit, so the rest of the site was never fetched",
    "skipped_cancelled": "the crawl was cancelled before it finished",
    "skipped_single_page": "this was a single-page scan, which never builds a link graph",
    "skipped_failed": "the crawl failed before the site-wide checks ran",
    "not_run": "coverage was not recorded for this crawl",
}


def orphan_coverage_note(job) -> str | None:
    """Return the disclosure line for ORPHAN_PAGE coverage, or None when the
    crawl genuinely covered the whole site and nothing needs saying.

    Purpose: stop a suppressed absence-proof reaching a client as a clean result.
    Spec:    docs/functional-specification.md §4.4 (ORPHAN_PAGE)
    Tests:   tests/test_orphan_detection_disclosure.py::TestExportSurfaces
    """
    detection = getattr(job, "orphan_detection", None)
    if not isinstance(detection, dict):
        return None  # legacy audit — no claim either way
    status = detection.get("status")
    if status == "complete":
        caveats = []
        if detection.get("archives_skipped"):
            caveats.append("WordPress archive pages were skipped")
        unread = detection.get("pages_links_unread") or 0
        if unread:
            caveats.append(f"{unread} page(s) could not be read (timeout, login wall or parse error)")
        if not caveats:
            return None
        return ("Orphaned pages: checked. " + "; ".join(caveats).capitalize() +
                " — a page linked only from one of those may still be listed here.")
    why = _ORPHAN_SKIP_WHY.get(status, "this crawl did not cover the whole site")
    analysed = detection.get("pages_analysed") or 0
    missed = detection.get("pages_out_of_scope") or 0
    tail = f" ({analysed} analysed, {missed} not fetched)" if missed else f" ({analysed} analysed)"
    return ("Orphaned pages: NOT CHECKED — " + why + tail +
            ". A page linked only from an unfetched page cannot be told apart "
            "from an orphan, so no result is reported rather than a misleading one.")
