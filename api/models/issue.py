"""
Issue Pydantic model (spec §5.4).

page_url is denormalised directly onto the record to avoid join complexity
in the API layer. page_id FK is retained for future query optimisation.
"""

from __future__ import annotations

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


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
    # Phase 2
    "image",
    "performance",
    "mobile",
    "schema",
]

PHASE_1_CATEGORIES: frozenset[str] = frozenset(
    [
        "broken_link", "metadata", "heading", "redirect",
        "crawlability", "duplicate", "sitemap", "security", "url_structure",
        "image", "ai_readiness",
    ]
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
    priority_rank: int = 0         # v1.5: (impact × 10) − (effort × 2)
    human_description: str = ""    # plain-English label for nonprofit staff
    what_it_is: str = ""           # detailed help text
    impact_desc: str = ""          # detailed impact help
    how_to_fix: str = ""           # detailed remediation help
    extra: dict | None = None      # supplementary data (e.g. source_url for broken links)
    fixability: str = "developer_needed"  # wp_fixable | content_edit | developer_needed
