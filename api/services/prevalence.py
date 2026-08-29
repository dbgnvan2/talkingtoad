"""E4 — site-wide prevalence: how much of the estate one defect touches.

Purpose: give the report a second, honest lens alongside per-page severity, so
         56 pages missing a description reads as one template defect rather
         than 56 pieces of trivia.
Spec:    docs/pending/2026-08-29_E4-site-prevalence-escalation.md
Tests:   tests/test_prevalence.py

**This module does not change scoring.** ``_ISSUE_SCORING``,
``_CATEGORY_IMPACT_CAP``, ``compute_page_health``, ``compute_impact_health``, the
R3/R5 calibration and every ``_IssueSpec.severity`` are untouched, and a test
asserts the health score is byte-identical to its pre-E4 value. Re-rating codes
to fix a *reporting* problem would invalidate three calibration suites for
something they were never about.

Why it exists. On job 05cd2496 TalkingToad reported health 89 with 0 critical
findings and 1,964 of 2,137 findings informational; an independent audit of the
same site the same week scored the SEO foundation 58/100. Both are defensible
per finding. Nothing escalated when the same minor defect was on 63% of pages.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from api.config import load_config
from api.crawler.checkers.registry import _CATALOGUE

_CFG_KEYS = ("tiers", "never_escalate", "always_systemic", "job_level_codes")


def _cfg() -> dict:
    return load_config("prevalence", required_keys=_CFG_KEYS)


@dataclass(frozen=True)
class Prevalence:
    """One code's footprint across the indexable estate."""
    code: str
    human_description: str
    category: str
    severity: str
    pages_affected: int
    indexable_pages: int
    share: float
    tier: str
    tier_label: str
    tier_weight: int

    @property
    def is_systemic(self) -> bool:
        return self.tier == "systemic"


# Codes that mark a page as deliberately hidden from search. A large noindex'd
# archive would otherwise dilute every share — the denominator question from the
# self-review checklist.
_NON_INDEXABLE_CODES = frozenset({"NOINDEX_META", "NOINDEX_HEADER", "ROBOTS_BLOCKED"})


def count_indexable_pages(
    page_urls: Iterable[str],
    issue_rows: Iterable[tuple[str, str]],
) -> int:
    """Indexable HTML pages = crawled pages minus those marked non-indexable.

    ``issue_rows`` is ``(issue_code, page_url)``. Never returns a negative or a
    zero denominator when pages exist — a share of "56 of 0" would be worse than
    no number at all.
    """
    urls = {u.rstrip("/") for u in page_urls if u}
    hidden = {
        u.rstrip("/") for code, u in issue_rows
        if code in _NON_INDEXABLE_CODES and u
    }
    return max(0, len(urls) - len(urls & hidden))


def compute_prevalence(
    issue_rows: Iterable[tuple[str, str]],
    indexable_pages: int,
) -> list[Prevalence]:
    """Per-code site prevalence, most-prevalent first. Pure; no I/O.

    ``issue_rows`` is ``(issue_code, page_url)``. Codes that fire once by design
    — site-scoped codes and job-level codes — get no entry: a "share" for them
    is meaningless and would read as a 0.4% problem.
    """
    if indexable_pages <= 0:
        return []
    cfg = _cfg()
    never = set(cfg["never_escalate"])
    always = set(cfg["always_systemic"])
    job_level = set(cfg["job_level_codes"])
    tiers = sorted(cfg["tiers"], key=lambda t: -float(t["min_share"]))

    pages_by_code: dict[str, set[str]] = {}
    for code, url in issue_rows:
        if not code or not url:
            continue
        spec = _CATALOGUE.get(code)
        if spec is None or spec.scope == "site":
            continue
        if code in job_level:
            continue
        pages_by_code.setdefault(code, set()).add(url.rstrip("/"))

    out: list[Prevalence] = []
    for code, urls in pages_by_code.items():
        spec = _CATALOGUE[code]
        affected = len(urls)
        share = affected / indexable_pages
        tier = _classify(code, affected, share, tiers, never, always)
        out.append(Prevalence(
            code=code,
            human_description=spec.human_description or code,
            category=spec.category,
            severity=spec.severity,
            pages_affected=affected,
            indexable_pages=indexable_pages,
            share=share,
            tier=tier["name"],
            tier_label=tier["label"],
            tier_weight=int(tier["weight"]),
        ))

    out.sort(key=lambda p: (-p.tier_weight, -p.pages_affected, p.code))
    return out


def _classify(code, affected, share, tiers, never, always) -> dict:
    scattered = tiers[-1]
    if code in never:
        return scattered
    if code in always:
        return next(t for t in tiers if t["name"] == "systemic")
    for tier in tiers:
        # BOTH gates must pass. A share alone would call 3-of-8 pages on a tiny
        # site "systemic"; a count alone would call 20-of-5,000 the same.
        if share >= float(tier["min_share"]) and affected >= int(tier["min_pages"]):
            return tier
    return scattered


def site_hygiene_score(prevalences: list[Prevalence]) -> int:
    """0-100: how much of the estate is touched by escalated defects.

    Deliberately NOT a replacement for Health. Health is per-page quality
    averaged; Hygiene is breadth. Two numbers with stated meanings beat one
    number asked to carry both jobs — and the report prints this formula.

    ``100 - Σ(tier weight × share)``, clamped. Monotonic by construction: a code
    affecting more pages has a larger share and can only lower the result.
    """
    penalty = sum(p.tier_weight * p.share for p in prevalences if p.tier_weight > 0)
    return max(0, min(100, round(100 - penalty)))


def systemic(prevalences: list[Prevalence]) -> list[Prevalence]:
    return [p for p in prevalences if p.is_systemic]


async def build_prevalence(store, job_id: str) -> list[Prevalence]:
    """Load a job's issues and pages and compute prevalence.

    One assembly for every surface (P25) — the results endpoint, the PDF and the
    Excel export all call this, so a systemic defect cannot be visible in one
    place and absent from another. User-suppressed codes are dropped first so
    prevalence reconciles with site health.
    """
    pages = await store.get_pages(job_id)
    issues = await store.get_all_issues(job_id)

    _gs = getattr(store, "get_suppressed_codes", None)
    suppressed = set(await _gs()) if _gs else set()

    rows = [
        (i.issue_code, i.page_url)
        for i in issues
        if i.page_url and i.issue_code not in suppressed
    ]
    indexable = count_indexable_pages([p.url for p in pages], rows)
    return compute_prevalence(rows, indexable)


def as_dicts(prevalences: list[Prevalence]) -> list[dict]:
    """JSON-safe rows for the API contract and the Excel export."""
    return [
        {
            "code": p.code,
            "human_description": p.human_description,
            "category": p.category,
            "severity": p.severity,
            "pages_affected": p.pages_affected,
            "indexable_pages": p.indexable_pages,
            "share": round(p.share, 4),
            "tier": p.tier,
            "tier_label": p.tier_label,
        }
        for p in prevalences
    ]
