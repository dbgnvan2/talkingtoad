"""E7 — turn findings into a roadmap: owner, phase, effort, and a done-when.

Purpose: answer the three questions a findings list leaves open — who does this,
         when, and how do we know it is finished.
Spec:    docs/pending/2026-08-29_E7-report-roadmap-and-caveats.md
Tests:   tests/test_report_roadmap.py

Nothing here is invented. TalkingToad already holds `impact`, `effort`,
`priority_rank`, `fixability` and `category` on every issue, prevalence tiers
from E4 and the traffic-ranked queue from E3. This module only assembles them.

The "done when" wording is deliberately countable and re-crawlable — "a re-crawl
reports 0 pages with META_DESC_MISSING", not "descriptions improved". Being
verifiable by re-running the tool is the one thing TalkingToad can offer that a
consultant's PDF cannot, and a criterion nobody can check is not a criterion.
"""

from __future__ import annotations

from dataclasses import dataclass

from api.config import load_config
from api.crawler.checkers.registry import _CATALOGUE

_CFG_KEYS = ("by_category", "default", "phases")

# A handful of codes where a sharper exit condition exists than the generic
# re-crawl assertion. Everything else uses the fallback, which is countable by
# construction — so a partial rollout of these is safe rather than misleading.
_DONE_WHEN_OVERRIDES: dict[str, str] = {
    "BROKEN_LINK_404": (
        "every broken target has an approved restore / remove / redirect decision "
        "and a re-crawl reports no internal 4xx links"
    ),
    "BROKEN_LINK_410": (
        "every gone target has an approved removal or redirect decision and a "
        "re-crawl reports no internal 4xx links"
    ),
    "META_DESC_MISSING": (
        "a re-crawl reports 0 indexable pages with a missing description"
    ),
    "META_DESC_DUPLICATE": (
        "a re-crawl reports 0 pages sharing a description with another page"
    ),
    "H1_MISSING": "a re-crawl reports 0 indexable pages with no H1",
    "H1_MULTIPLE": "a re-crawl reports 0 pages with more than one H1",
    "ORPHAN_PAGE": (
        "every orphan has either an intentional internal link or a "
        "keep / noindex / remove decision, and a re-crawl reports none"
    ),
    "ENTITY_HOURS_DEFAULT": (
        "a re-crawl reports verified opening hours in the rendered Organization "
        "graph, or no openingHoursSpecification at all"
    ),
    "ENTITY_NAP_INCOMPLETE": (
        "a re-crawl reports no missing identity fields — the rendered graph "
        "carries the verified name, address, phone, email and logo"
    ),
    "CONSENT_MODE_MISSING": (
        "a re-crawl detects a consent signal on every page carrying an analytics tag"
    ),
    "IMG_ALT_MISSING": "a re-crawl reports 0 non-decorative images without alt text",
}


def _cfg() -> dict:
    return load_config("remediation_owners", required_keys=_CFG_KEYS)


def owner_for(category: str) -> str:
    cfg = _cfg()
    return cfg["by_category"].get(category) or cfg["default"]


def done_when_for(code: str) -> str:
    """A countable, re-crawlable exit condition for *code*."""
    if code in _DONE_WHEN_OVERRIDES:
        return _DONE_WHEN_OVERRIDES[code]
    spec = _CATALOGUE.get(code)
    label = (spec.human_description if spec else None) or code
    return f'a re-crawl no longer reports "{label}" on the affected pages'


def effort_label(effort: int) -> str:
    return {0: "Trivial", 1: "Low", 2: "Medium"}.get(int(effort or 0), "High")


@dataclass(frozen=True)
class RoadmapItem:
    code: str
    title: str
    category: str
    owner: str
    impact: int
    effort: int
    effort_label: str
    pages_affected: int
    done_when: str
    phase: str
    phase_title: str
    tier: str
    fixability: str


def build_roadmap(
    issues: list,
    *,
    prevalence: list | None = None,
    priority_pages: list[dict] | None = None,
    limit_per_phase: int = 12,
) -> tuple[list[RoadmapItem], bool, dict[str, int]]:
    """Group deduplicated findings into three phases.

    Returns ``(items, weighted, totals)``.

    ``weighted`` is False when neither prevalence nor priority data was available
    — the caller must then say so rather than implying a phasing it did not apply
    (E7.1c). ``totals`` is the PRE-CAP item count per phase, so the caller can
    print "showing 12 of 40" (rule 6). Returning only the capped list made that
    disclosure impossible: no caller could know what had been dropped.
    """
    cfg = _cfg()
    phases = {p["name"]: p for p in cfg["phases"]}
    prevalence = prevalence or []
    priority_pages = priority_pages or []
    weighted = bool(prevalence or priority_pages)

    prev_by_code = {p.code: p for p in prevalence}

    # Top-quartile URLs by the E3 work queue — "already earns traffic".
    top_urls: set[str] = set()
    if priority_pages:
        cut = max(1, len(priority_pages) // 4)
        top_urls = {
            (p.get("url") or "").rstrip("/") for p in priority_pages[:cut]
        }

    # One row per code, keeping the highest-priority instance.
    by_code: dict[str, object] = {}
    urls_by_code: dict[str, set[str]] = {}
    for iss in issues:
        code = getattr(iss, "issue_code", None)
        if not code:
            continue
        url = (getattr(iss, "page_url", None) or "").rstrip("/")
        if url:
            urls_by_code.setdefault(code, set()).add(url)
        best = by_code.get(code)
        if best is None or (getattr(iss, "priority_rank", 0) or 0) > (
            getattr(best, "priority_rank", 0) or 0
        ):
            by_code[code] = iss

    items: list[RoadmapItem] = []
    for code, iss in by_code.items():
        spec = _CATALOGUE.get(code)
        category = getattr(iss, "category", None) or (spec.category if spec else "")
        prev = prev_by_code.get(code)
        pages_affected = prev.pages_affected if prev else len(urls_by_code.get(code, ()))
        fixability = getattr(iss, "fixability", None) or (
            spec.fixability if spec else "developer_needed"
        )

        # Phase 1 — systemic, or a single template edit.
        if (prev and prev.tier == "systemic") or fixability == "wp_fixable" and prev and prev.tier == "widespread":
            phase = "phase_1"
        # Phase 2 — lands on a page that already earns traffic.
        elif top_urls and (urls_by_code.get(code, set()) & top_urls):
            phase = "phase_2"
        else:
            phase = "phase_3"

        items.append(RoadmapItem(
            code=code,
            title=getattr(iss, "human_description", None) or (
                spec.human_description if spec else code
            ) or code,
            category=category,
            owner=owner_for(category),
            impact=int(getattr(iss, "impact", 0) or 0),
            effort=int(getattr(iss, "effort", 0) or 0),
            effort_label=effort_label(getattr(iss, "effort", 0)),
            pages_affected=pages_affected,
            done_when=done_when_for(code),
            phase=phase,
            phase_title=phases[phase]["title"],
            tier=prev.tier if prev else "scattered",
            fixability=fixability,
        ))

    order = {"phase_1": 0, "phase_2": 1, "phase_3": 2}
    items.sort(key=lambda i: (
        order[i.phase], -i.pages_affected, -i.impact, i.code
    ))

    # Cap per phase, and hand the caller the pre-cap totals so it can disclose
    # what was dropped (rule 6).
    totals: dict[str, int] = {}
    for item in items:
        totals[item.phase] = totals.get(item.phase, 0) + 1

    capped: list[RoadmapItem] = []
    counts: dict[str, int] = {}
    for item in items:
        n = counts.get(item.phase, 0)
        if n < limit_per_phase:
            capped.append(item)
            counts[item.phase] = n + 1
    return capped, weighted, totals


def phase_blurb(phase: str) -> str:
    for p in _cfg()["phases"]:
        if p["name"] == phase:
            return p["blurb"]
    return ""


def phase_titles() -> list[tuple[str, str]]:
    return [(p["name"], p["title"]) for p in _cfg()["phases"]]
