"""Tests for citation data model and assessment (v2.0).

Spec: docs/specs/ai-readiness/v2-extended-module.md § 3.6
"""

import pytest
from api.services.citation_model import (
    Citation,
    PageCitations,
    CitationIssue,
    assess_citation_readiness,
    diagnose_citation_issue,
)


class TestCitationDataModel:
    """Test Citation and PageCitations data structures."""

    def test_citation_creation(self):
        """Citation objects can be created with text and optional metadata."""
        citation = Citation(
            text="Smith, 2020",
            url="https://example.com/paper",
            context="Research shows...",
            is_inline=True,
        )
        assert citation.text == "Smith, 2020"
        assert citation.url == "https://example.com/paper"
        assert citation.is_inline is True

    def test_page_citations_creation(self):
        """PageCitations object stores citations and metadata."""
        citations = [
            Citation(text="Smith, 2020", url="https://example.com/1"),
            Citation(text="Jones, 2021", url="https://example.com/2"),
        ]
        page_cites = PageCitations(
            url="https://example.com/article",
            citations=citations,
            attribution_style="inline",
        )
        assert page_cites.url == "https://example.com/article"
        assert page_cites.get_citation_count() == 2
        assert len(page_cites.citations) == 2

    def test_citation_count(self):
        """get_citation_count returns correct count."""
        page_cites = PageCitations(
            url="https://example.com/page",
            citations=[
                Citation(text="A"),
                Citation(text="B"),
                Citation(text="C"),
            ],
        )
        assert page_cites.get_citation_count() == 3

    def test_cited_domains(self):
        """get_cited_domains extracts unique domains from citations."""
        page_cites = PageCitations(
            url="https://example.com/article",
            citations=[
                Citation(text="Source 1", url="https://domain-a.com/paper"),
                Citation(text="Source 2", url="https://domain-b.com/study"),
                Citation(text="Source 3", url="https://domain-a.com/other"),
            ],
        )
        domains = page_cites.get_cited_domains()
        assert "domain-a.com" in domains
        assert "domain-b.com" in domains
        assert len(domains) == 2

    def test_cited_domains_with_no_urls(self):
        """get_cited_domains handles citations without URLs."""
        page_cites = PageCitations(
            url="https://example.com/page",
            citations=[
                Citation(text="Citation A", url=None),
                Citation(text="Citation B", url="https://example.com/source"),
            ],
        )
        domains = page_cites.get_cited_domains()
        assert "example.com" in domains
        assert len(domains) == 1


class TestCitationAssessment:
    """Test citation readiness assessment."""

    def test_well_cited_page(self):
        """Well-cited article has no critical issues."""
        page_cites = PageCitations(
            url="https://example.com/article",
            citations=[
                Citation(text="Smith, 2020", context="Research shows...", is_inline=True),
                Citation(text="Jones, 2021", context="Studies confirm...", is_inline=True),
            ],
            attribution_style="inline",
        )
        issue = assess_citation_readiness(page_cites, word_count=1000)
        assert issue.lacks_citations is False
        assert issue.has_orphan_citations is False

    def test_substantial_content_no_citations(self):
        """Long page with no citations flagged as problematic."""
        page_cites = PageCitations(
            url="https://example.com/article",
            citations=[],
            attribution_style="none",
        )
        issue = assess_citation_readiness(page_cites, word_count=500)
        assert issue.lacks_citations is True

    def test_short_page_no_citations_ok(self):
        """Short pages without citations are acceptable."""
        page_cites = PageCitations(
            url="https://example.com/short",
            citations=[],
            attribution_style="none",
        )
        issue = assess_citation_readiness(page_cites, word_count=100)
        assert issue.lacks_citations is False

    def test_orphan_citations_detected(self):
        """Citations without context are flagged."""
        page_cites = PageCitations(
            url="https://example.com/page",
            citations=[
                Citation(text="Smith, 2020", context=None),  # No context
            ],
        )
        issue = assess_citation_readiness(page_cites, word_count=500)
        assert issue.has_orphan_citations is True

    def test_citation_heavy_page(self):
        """Pages with >5% citations are flagged as unusual."""
        # 100 citations in 1000 words = 10%
        citations = [Citation(text=f"Ref {i}") for i in range(100)]
        page_cites = PageCitations(
            url="https://example.com/page",
            citations=citations,
        )
        issue = assess_citation_readiness(page_cites, word_count=1000)
        assert issue.is_citation_heavy is True

    def test_citation_ratio_threshold(self):
        """5% citation ratio is the threshold."""
        # Exactly 5% = 50 citations in 1000 words
        citations = [Citation(text=f"Ref {i}") for i in range(50)]
        page_cites = PageCitations(
            url="https://example.com/page",
            citations=citations,
        )
        issue = assess_citation_readiness(page_cites, word_count=1000)
        # 50/1000 = 0.05 = 5%, should not be "heavy"
        assert issue.is_citation_heavy is False


class TestCitationDiagnosis:
    """Test citation issue diagnosis."""

    def test_diagnose_missing_citations(self):
        """Lacks citations → CITATIONS_MISSING_SUBSTANTIAL_CONTENT."""
        page_cites = PageCitations(
            url="https://example.com/article",
            citations=[],
            attribution_style="none",
        )
        issue = assess_citation_readiness(page_cites, word_count=500)
        diagnosis = diagnose_citation_issue(issue)
        assert diagnosis == "CITATIONS_MISSING_SUBSTANTIAL_CONTENT"

    def test_diagnose_orphan_citations(self):
        """Orphan citations → CITATIONS_ORPHANED."""
        page_cites = PageCitations(
            url="https://example.com/page",
            citations=[Citation(text="Orphaned", context=None)],
        )
        issue = assess_citation_readiness(page_cites, word_count=500)
        diagnosis = diagnose_citation_issue(issue)
        assert diagnosis == "CITATIONS_ORPHANED"

    def test_diagnose_well_cited(self):
        """Well-cited page → None."""
        page_cites = PageCitations(
            url="https://example.com/article",
            citations=[
                Citation(text="A", context="Context A", is_inline=True),
                Citation(text="B", context="Context B", is_inline=True),
            ],
            attribution_style="inline",
        )
        issue = assess_citation_readiness(page_cites, word_count=1000)
        diagnosis = diagnose_citation_issue(issue)
        assert diagnosis is None

    def test_diagnose_inaccessible_sources(self):
        """Inaccessible sources → CITATIONS_SOURCES_INACCESSIBLE."""
        page_cites = PageCitations(
            url="https://example.com/page",
            citations=[Citation(text="Dead Link", context="Reference from this study...")],
        )
        issue = assess_citation_readiness(page_cites, word_count=500)
        # Manually set the flag (actual detection requires HTTP checking)
        issue.has_inaccessible_sources = True
        diagnosis = diagnose_citation_issue(issue)
        assert diagnosis == "CITATIONS_SOURCES_INACCESSIBLE"


class TestCitationEdgeCases:
    """Test edge cases."""

    def test_empty_citations(self):
        """Empty citation list is valid."""
        page_cites = PageCitations(
            url="https://example.com/page",
            citations=[],
        )
        assert page_cites.get_citation_count() == 0
        assert page_cites.get_cited_domains() == set()

    def test_word_count_zero(self):
        """Zero word count doesn't trigger citation issues."""
        page_cites = PageCitations(
            url="https://example.com/page",
            citations=[],
            attribution_style="none",
        )
        issue = assess_citation_readiness(page_cites, word_count=0)
        assert issue.lacks_citations is False

    def test_footnote_style(self):
        """Footnote-style citations are recognized."""
        page_cites = PageCitations(
            url="https://example.com/page",
            citations=[Citation(text="[1]", is_inline=False)],
            has_footnotes=True,
            attribution_style="footnote",
        )
        assert page_cites.has_footnotes is True
        assert page_cites.attribution_style == "footnote"
