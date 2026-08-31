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


_SITEMAP_SKIP_WHY = {
    "wordpress_archive": "WordPress archive pages are skipped by default",
    "admin_path": "admin paths are never crawled",
    "robots_blocked": "robots.txt disallows them",
    "robots_expected_disallow": "robots.txt disallows them (cart/search/account)",
    "query_variant_cap": "the per-path query-variant cap was reached",
    "not_reached": "the crawl did not reach them",
}


def sitemap_coverage_note(job) -> str | None:
    """Return a disclosure line when the sitemap declares URLs we did not fetch.

    Purpose: a URL the site itself declares, silently absent from the audit, is
             indistinguishable from one that was checked and clean (P31).
    Spec:    docs/pending/2026-08-30_audit-fixes.md#AF10
    Tests:   tests/test_sitemap_coverage.py::TestExportSurfaces
    """
    cov = getattr(job, "sitemap_coverage", None)
    if not isinstance(cov, dict):
        return None                      # legacy audit — no claim either way
    declared = cov.get("declared") or 0
    missed = cov.get("not_crawled") or 0
    if not declared or not missed:
        return None
    reasons = cov.get("reasons") or {}
    counts: dict[str, int] = {}
    for why in reasons.values():
        counts[why] = counts.get(why, 0) + 1
    detail = "; ".join(
        f"{n} because {_SITEMAP_SKIP_WHY.get(why, why)}"
        for why, n in sorted(counts.items(), key=lambda kv: -kv[1]))
    return (f"Sitemap: {cov.get('crawled', 0)} of {declared} declared URLs were fetched. "
            f"{missed} were not"
            + (f" — {detail}." if detail else ".")
            + " Findings say nothing about the pages that were not fetched.")


def analysis_coverage_note(job) -> str | None:
    """Return a disclosure line when analysis groups were switched off.

    Purpose: a category that never ran contributes zero findings, and zero
             findings render exactly like a clean category (P31).
    Spec:    docs/pending/2026-08-30_analysis-coverage-disclosure.md#C2
    Tests:   tests/test_analysis_coverage.py
    """
    cov = getattr(job, "analysis_coverage", None)
    if not isinstance(cov, dict) or cov.get("mode") != "partial":
        return None
    unchecked = cov.get("categories_unchecked") or []
    if not unchecked:
        return None
    pretty = ", ".join(c.replace("_", " ") for c in unchecked)
    checked = cov.get("categories_checked") or []
    total = len(checked) + len(unchecked)
    return ("Analyses: this was a PARTIAL scan. These categories were not checked and "
            f"report nothing: {pretty}. A category that did not run shows no findings, "
            "which is not the same as having none. "
            # S2: the score must not be read as a whole-site number.
            f"The health score therefore covers {len(checked)} of {total} categories and is "
            "not comparable with a full scan of the same site.")
