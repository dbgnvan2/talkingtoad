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
    # P5.4: impact and severity are the values STORED on the job's rows, not
    # today's `derive_impact`/`spec.severity`. Every other surface reads the
    # stored value, and re-deriving made an old job's prevalence table disagree
    # with its own issue list after any recalibration (P8).
    impact: int
    pages_affected: int
    indexable_pages: int
    share: float
    tier: str
    tier_label: str
    tier_weight: int
    # The pages this code was found on. Kept off `as_dicts` — it is only needed
    # to union across codes for the Hygiene coverage measure, and shipping a
    # per-code URL list in every API response would bloat the payload.
    affected_urls: frozenset = frozenset()

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
        row[1].rstrip("/") for row in issue_rows
        if row[0] in _NON_INDEXABLE_CODES and row[1]
    }
    return max(0, len(urls) - len(urls & hidden))


def compute_prevalence(
    issue_rows: Iterable[tuple[str, str]],
    indexable_pages: int,
) -> list[Prevalence]:
    """Per-code site prevalence, most-prevalent first. Pure; no I/O.

    ``issue_rows`` is ``(issue_code, page_url, impact, severity)`` — the last two
    read from the STORED finding, not re-derived (P5.4). Codes that fire once by
    design — site-scoped codes and job-level codes — get no entry: a "share" for
    them is meaningless and would read as a 0.4% problem.

    A code the catalogue no longer knows still gets a row. Its findings are in
    the lists and charge the health score, so dropping it here made the two
    tables disagree on live data: six §7-deleted codes hold 4,559 rows.
    """
    if indexable_pages <= 0:
        return []
    cfg = _cfg()
    never = set(cfg["never_escalate"])
    always = set(cfg["always_systemic"])
    job_level = set(cfg["job_level_codes"])
    tiers = sorted(cfg["tiers"], key=lambda t: -float(t["min_share"]))

    pages_by_code: dict[str, set[str]] = {}
    # The stored judgement per code. Where a job holds more than one impact for a
    # code — a rescan under a new model — the MAXIMUM wins: prevalence exists to
    # escalate, and taking the max can never demote a code below a value some row
    # in this job actually carries. Deterministic, so iteration order is not a
    # hidden input.
    stored: dict[str, tuple[int, str, str]] = {}
    for row in issue_rows:
        code, url = row[0], row[1]
        impact = int(row[2] or 0) if len(row) > 2 else 0
        severity = (row[3] if len(row) > 3 else None) or "info"
        if not code or not url:
            continue
        spec = _CATALOGUE.get(code)
        # An unknown code has page URLs, which is what page-scoped means; only a
        # code the catalogue KNOWS can be declared site-scoped.
        if spec is not None and spec.scope == "site":
            continue
        if code in job_level:
            continue
        pages_by_code.setdefault(code, set()).add(url.rstrip("/"))
        prev = stored.get(code)
        if prev is None or impact > prev[0]:
            stored[code] = (impact, severity, row[4] if len(row) > 4 else "")

    out: list[Prevalence] = []
    for code, urls in pages_by_code.items():
        spec = _CATALOGUE.get(code)
        impact, severity, stored_category = stored[code]
        affected = len(urls)
        share = affected / indexable_pages
        tier = _classify(code, affected, share, tiers, never, always)
        out.append(Prevalence(
            # Description and category are LABELS and stay with the catalogue, so
            # improved wording reaches an old report. Impact and severity are
            # judgements and come from the row. Where the catalogue has forgotten
            # the code it can supply neither, and the stored values are the only
            # honest source.
            code=code,
            human_description=(spec.human_description or code) if spec else code,
            category=spec.category if spec else (stored_category or "metadata"),
            severity=severity,
            impact=impact,
            pages_affected=affected,
            indexable_pages=indexable_pages,
            share=share,
            tier=tier["name"],
            tier_label=tier["label"],
            tier_weight=int(tier["weight"]),
            affected_urls=frozenset(urls),
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
    """0-100: the share of indexable pages carrying NO systemic defect.

    Deliberately NOT a replacement for Health. Health is per-page quality
    averaged; Hygiene is breadth — how much of the estate one or more template
    defects reach. Two numbers with stated meanings beat one asked to carry both.

    ``100 × (indexable pages with no systemic defect ÷ indexable pages)``.

    This is a **coverage** measure, not a weighted penalty sum. The weighted
    version was tried first and was useless on real data: on livingsystems.ca,
    nine systemic defects produced a penalty of 135 and the score clamped to 0,
    which distinguishes nothing from a site with twenty. Coverage is bounded by
    construction, needs no arbitrary per-tier weight, is monotonic (adding an
    affected page can only shrink the clean set), and states itself in one
    sentence the report can print: "N% of your indexable pages carry at least
    one systemic defect."
    """
    systemic_rows = [p for p in prevalences if p.is_systemic]
    if not systemic_rows:
        return 100
    indexable = max(p.indexable_pages for p in systemic_rows)
    if indexable <= 0:
        return 100
    affected: set = set()
    for p in systemic_rows:
        affected |= p.affected_urls
    clean = max(0, indexable - len(affected))
    return max(0, min(100, round(100 * clean / indexable)))


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
        (i.issue_code, i.page_url, i.impact or 0, i.severity, i.category or "")
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
            "impact": p.impact,
            "pages_affected": p.pages_affected,
            "indexable_pages": p.indexable_pages,
            "share": round(p.share, 4),
            "tier": p.tier,
            "tier_label": p.tier_label,
        }
        for p in prevalences
    ]
