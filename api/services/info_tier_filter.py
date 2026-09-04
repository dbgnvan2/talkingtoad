"""Info detail — the display side of a scan's ``info_detail`` setting.

Purpose: a scan's ``info_detail`` (all · notable · key · none) names which info
         tiers are part of the audit. The SCORE applies it in
         ``job_store_base.info_detail_rows``; this module applies the SAME
         predicate (``registry.info_row_excluded``) to the results list, the
         page drawer and the exports, so what is shown is what is scored.
Spec:    docs/pending/2026-09-01_info-tiers.md §5
Tests:   tests/test_info_tiers.py, tests/test_info_tiers_integration.py

Every filtered response declares what it left out. 123 of 170 catalogue codes
are info; a list that simply came back shorter would read as a cleaner site
(P31 / P24), and here the score really IS higher, so the disclosure is the
only thing separating "chosen scope" from "hidden findings".
"""

from __future__ import annotations

from api.crawler.checkers.registry import (
    INFO_DETAIL_MIN_IMPACT,
    INFO_TIER_LABELS,
    info_detail_rank,
    info_row_excluded,
    info_tier,
)


def resolve_info_detail(job_detail: str, requested: str | None) -> str:
    """The level a request is served at: reveal-only.

    A request may LOOSEN the job's level (``?info_detail=all`` shows the rows
    the scan excluded) but never tighten it — the score is a property of the
    scan, and a list narrower than the score would silently disagree with it.
    Unknown values fall back to the job's own level.
    """
    if requested is None or requested not in INFO_DETAIL_MIN_IMPACT:
        return job_detail
    return requested if info_detail_rank(requested) < info_detail_rank(job_detail) else job_detail


def _is_excluded(issue: dict, level: str) -> bool:
    return issue.get("severity") == "info" and info_row_excluded(int(issue.get("impact") or 0), level)


def annotate_scored(issue_dicts: list[dict], job_detail: str) -> list[dict]:
    """Stamp ``scored`` on every issue dict: is this row charged to the score?

    Always relative to the JOB's level, not the request's — a revealed row is
    visible but still ``scored: false``, and the UI dims it on that flag.
    """
    for d in issue_dicts:
        d["scored"] = not _is_excluded(d, job_detail)
    return issue_dicts


def apply_info_detail(issue_dicts: list[dict], level: str) -> tuple[list[dict], dict]:
    """Return ``(kept, report)`` for a list served at ``level``.

    ``report`` = ``{"hidden", "by_tier", "info_detail"}``; ``hidden`` is the
    count removed, ``by_tier`` the removed rows per tier (never the kept ones —
    the kept ones are in the list). Non-info rows are never removed.
    """
    kept: list[dict] = []
    by_tier: dict[str, int] = {}
    for d in issue_dicts:
        if _is_excluded(d, level):
            tier = info_tier(int(d.get("impact") or 0)) or "low"
            by_tier[tier] = by_tier.get(tier, 0) + 1
        else:
            kept.append(d)
    return kept, {"hidden": sum(by_tier.values()), "by_tier": by_tier, "info_detail": level}


def filter_issue_models(issues: list, level: str) -> tuple[list, dict]:
    """Same rule for Issue MODELS (the export paths)."""
    kept = []
    by_tier: dict[str, int] = {}
    for i in issues:
        if i.severity == "info" and info_row_excluded(int(i.impact or 0), level):
            tier = info_tier(int(i.impact or 0)) or "low"
            by_tier[tier] = by_tier.get(tier, 0) + 1
        else:
            kept.append(i)
    return kept, {"hidden": sum(by_tier.values()), "by_tier": by_tier, "info_detail": level}


def info_caveat_note(report: dict | None) -> str | None:
    """One sentence for an export that was scoped by ``info_detail``, or None.

    Unlike the domain filter's note this is not "hidden from the list but
    still scored" — these rows are OUT of the score too, and the reader of a
    PDF must be told the number they are looking at was earned that way.
    """
    if not report or not report.get("hidden"):
        return None
    level = report.get("info_detail", "all")
    parts = ", ".join(
        f"{INFO_TIER_LABELS.get(t, t)} {n}"
        for t, n in sorted(report.get("by_tier", {}).items(), key=lambda kv: -kv[1])
    )
    return (
        f"Scored at info detail '{level}': {report['hidden']} info notice"
        f"{'' if report['hidden'] == 1 else 's'} ({parts}) excluded from this audit "
        f"and from its health score by the scan setting."
    )


def scored_of_found(found: int, excluded: int) -> str:
    """``"5 (2 scored)"`` — a FOUND total that states how much the score charged."""
    return f"{found} ({found - excluded} scored)" if excluded else str(found)


def scored_with_excluded(scored: int, excluded: int) -> str:
    """``"0 (2 not scored)"`` — a SCORED count that states what the level dropped.

    The inverse of :func:`scored_of_found`, and the two are easy to mix up, which
    is why they live together. Both were written out as f-strings in three
    places (the PDF total, the PDF category rows, the Excel column); the QA gate
    on P5.2 flagged the triplication as the same drift shape that produced P5.2.
    """
    return f"{scored} ({excluded} not scored)" if excluded else str(scored)


def excluded_at_level(excluded: int, level: str) -> str | None:
    """``"2 not scored at info detail 'key'"`` — the per-category caveat, or None."""
    if not excluded:
        return None
    return f"{excluded} not scored at info detail '{level}'"


def combine_notes(*notes: str | None) -> str | None:
    """Join the caveat sentences that apply; None when none do."""
    kept = [n for n in notes if n]
    return " ".join(kept) if kept else None
