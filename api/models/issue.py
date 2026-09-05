"""
Issue Pydantic model (spec §5.4).

page_url is denormalised directly onto the record to avoid join complexity
in the API layer. page_id FK is retained for future query optimisation.
"""

from __future__ import annotations

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, computed_field

from api.crawler.checkers.registry import _CATALOGUE


Severity = Literal["critical", "warning", "info"]

IssueCategory = Literal[
    "broken_link",
    "metadata",
    "heading",
    "redirect",
    "crawlability",
    "duplicate",
    "sitemap",
    "security",
    "url_structure",
    "ai_readiness",
    # Agent-readiness Phase 1 (task-side checks)
    "rendering",
    "semantic_html",
    # Analytics & Measurement (2026-08-06 spec) — GA4/GTM tag integrity + attribution
    "analytics",
    # Phase 2
    "image",
    "performance",
    "mobile",
    "schema",
]

# Every category some issue code actually emits, derived rather than hand-kept
# (2026-09-05 sweep §2). The hand list carried `duplicate` long after CLN1
# established that no checker emits it, so `get_summary` seeded a counter that
# could only ever report 0 and the CSV export offered a category the product
# does not have. Derivation deletes that class of drift instead of the one
# instance; `tests/test_architecture_constraints.py` asserts both directions.
#
# The name is older than the meaning. Phase 2 (performance, mobile, schema) is
# unbuilt, so every emitted category is a Phase 1 one and the CSV's `phase`
# column is constant "1" — true before this change and unchanged by it. Retiring
# that column is a contract change for anything parsing the export, so it is
# recorded in TODO rather than folded into a hygiene sweep.
PHASE_1_CATEGORIES: frozenset[str] = frozenset(
    spec.category for spec in _CATALOGUE.values()
)


class Issue(BaseModel):
    """A single SEO issue found on a crawled page (spec §5.4)."""

    issue_id: str = Field(default_factory=lambda: str(uuid4()))
    job_id: str
    page_id: str | None = None
    page_url: str | None = None
    link_id: str | None = None
    category: IssueCategory
    severity: Severity
    issue_code: str
    description: str
    recommendation: str
    impact: int = 0                # v1.5: how badly this issue hurts SEO/UX (0–10)
    effort: int = 0                # v1.5: how hard it is to fix (0–5)
    priority_rank: int = 0         # R3: (impact × 10) − (effort × 6)
    human_description: str = ""    # plain-English label for nonprofit staff
    what_it_is: str = ""           # detailed help text
    impact_desc: str = ""          # detailed impact help
    how_to_fix: str = ""           # detailed remediation help
    extra: dict | None = None      # supplementary data (e.g. source_url for broken links)
    fixability: str = "developer_needed"  # wp_fixable | content_edit | developer_needed
    # v2.3 (M0.2) — confidence label for AI-readiness category issues.
    # See _IssueSpec.confidence_label in api/crawler/issue_checker.py for the
    # taxonomy (Established / Reasonable proxy / Heuristic). None for issues
    # outside the ai_readiness category.
    confidence_label: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def quick_win(self) -> bool:
        """R3: an easy, worthwhile fix — surfaced in the UI's Quick-Wins list.

        Derived (not stored) so it is always consistent with impact/effort:
        ``impact >= 4 AND effort <= 1``.
        """
        return self.impact >= 4 and self.effort <= 1

    @computed_field  # type: ignore[prop-decorator]
    @property
    def info_tier(self) -> str | None:
        """Info sub-grade (``high`` | ``medium`` | ``low``), ``None`` unless info.

        Derived from the STORED impact, not from today's catalogue, so an
        audit crawled before a recalibration keeps the tier it was scored
        under (P8: dirty state must not shift underneath the reader).
        """
        if self.severity != "info":
            return None
        from api.crawler.checkers.registry import info_tier
        return info_tier(self.impact)
