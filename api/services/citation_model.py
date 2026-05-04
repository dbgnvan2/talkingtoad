"""Citation and attribution data model for AI readiness.

Tracks whether pages provide proper attribution/source data for AI systems
(e.g., citations in AI Overviews, source attribution in LLM outputs).

Spec: docs/specs/ai-readiness/v2-extended-module.md § 3.6
Tests: tests/test_citation_model.py
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Citation:
    """A single attribution or source citation on a page."""

    text: str  # The citation text (e.g., "Smith, 2020")
    url: Optional[str] = None  # Link to the source (optional)
    context: Optional[str] = None  # The sentence/paragraph containing the citation
    is_inline: bool = False  # True if inline (e.g., "(Smith, 2020)"), False if footnote
    source_type: str = "text"  # text | link | footnote | endnote | markdown


@dataclass
class PageCitations:
    """Citation metadata for a single page."""

    url: str  # The page URL
    citations: list[Citation] = field(default_factory=list)
    has_footnotes: bool = False  # Page uses footnote/endnote system
    has_links_to_sources: bool = False  # Page links to external sources
    attribution_style: str = "none"  # none | inline | footnote | mixed
    is_reference_page: bool = False  # True if page is itself a reference/sources/citations page

    def get_citation_count(self) -> int:
        """Total number of citations found."""
        return len(self.citations)

    def get_cited_domains(self) -> set[str]:
        """Set of domains cited on this page."""
        from urllib.parse import urlparse

        domains = set()
        for citation in self.citations:
            if citation.url:
                domain = urlparse(citation.url).netloc
                if domain:
                    domains.add(domain)
        return domains


@dataclass
class CitationIssue:
    """Assessment of citation-related issues on a page."""

    page_url: str
    is_citation_heavy: bool  # True if >5% of text is citations
    lacks_citations: bool  # True if 200+ words with no citations
    has_orphan_citations: bool  # Citations without context
    has_inaccessible_sources: bool  # Links are broken or blocked
    average_citation_recency_days: Optional[int] = None  # Age of cited sources


def assess_citation_readiness(page_citations: PageCitations, word_count: int) -> CitationIssue:
    """Assess how well-cited and attribution-friendly a page is.

    Purpose: Check page citation practices for AI Overviews compatibility
    Spec:    docs/specs/ai-readiness/v2-extended-module.md § 3.6
    Tests:   tests/test_citation_model.py::test_assess_citation_*

    Args:
        page_citations: Citation metadata for the page
        word_count: Total word count of the page

    Returns:
        CitationIssue with assessment of citation problems
    """
    citation_count = page_citations.get_citation_count()

    # Check if citation-heavy (unusual)
    is_citation_heavy = False
    if word_count > 0:
        citation_ratio = citation_count / word_count
        is_citation_heavy = citation_ratio > 0.05  # >5% is unusual

    # Check if lacks citations (problematic for long-form content)
    lacks_citations = (
        word_count > 200  # Substantial content
        and citation_count == 0  # No citations
        and page_citations.attribution_style == "none"  # No attribution system
    )

    # Check for orphan citations (citations without visible context)
    has_orphan_citations = any(c.context is None for c in page_citations.citations)

    # TODO: Check for inaccessible sources (requires HTTP requests)
    has_inaccessible_sources = False

    return CitationIssue(
        page_url=page_citations.url,
        is_citation_heavy=is_citation_heavy,
        lacks_citations=lacks_citations,
        has_orphan_citations=has_orphan_citations,
        has_inaccessible_sources=has_inaccessible_sources,
    )


def diagnose_citation_issue(issue: CitationIssue) -> Optional[str]:
    """Get a single citation-related issue code if critical problem exists.

    Returns issue code or None if citations are adequate.
    """
    if issue.lacks_citations:
        return "CITATIONS_MISSING_SUBSTANTIAL_CONTENT"
    if issue.has_orphan_citations and issue.page_url:
        return "CITATIONS_ORPHANED"
    if issue.has_inaccessible_sources:
        return "CITATIONS_SOURCES_INACCESSIBLE"

    return None
