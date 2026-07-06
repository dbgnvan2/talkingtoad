"""R6 — real citation parser + source accessibility (audit remediation, 2026-07-04).

Spec: docs/pending/OLD/2026-07-04_r6-citation-parser.md
Adversarial (P7): a well-cited page must NOT be flagged; only genuinely uncited
pages fire CITATIONS_MISSING_SUBSTANTIAL_CONTENT.
"""

import socket
from unittest.mock import patch

import httpx
import pytest

from api.crawler.parser import ParsedLink
from api.crawler.issue_checker import build_page_citations, citation_source_issues, check_page
from api.services.citation_model import (
    Citation, PageCitations, assess_citation_readiness, check_source_accessibility,
)
from tests.test_issue_checker import _page

_PUBLIC = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]


# ── build_page_citations ──────────────────────────────────────────────────────
def test_external_source_is_citation():
    page = _page(url="https://mysite.org/blog", word_count=500,
                 links=[ParsedLink("https://ref.org/study", "the study", False)])
    pc = build_page_citations(page)
    assert pc.get_citation_count() == 1
    assert pc.citations[0].url == "https://ref.org/study"


def test_social_and_internal_not_citations():
    page = _page(url="https://mysite.org/blog", word_count=500, links=[
        ParsedLink("https://mysite.org/about", "About", True),
        ParsedLink("https://facebook.com/me", "fb", False),
        ParsedLink("https://twitter.com/me", "x", False),
    ])
    assert build_page_citations(page).get_citation_count() == 0


def test_bare_url_citation_is_orphan():
    page = _page(url="https://mysite.org/blog", word_count=500,
                 links=[ParsedLink("https://ref.org/bare", None, False)])
    pc = build_page_citations(page)
    assert pc.citations[0].context is None  # no anchor text ⇒ orphan


# ── assess + diagnose (via check_page) ────────────────────────────────────────
def _codes(page):
    return {i.code for i in check_page(page)}


def test_well_cited_page_not_flagged_missing():
    """AC1/AC3: a >200-word page with a real citation is NOT flagged."""
    page = _page(url="https://mysite.org/blog", word_count=500,
                 links=[ParsedLink("https://ref.org/study", "the study", False)])
    codes = _codes(page)
    assert "CITATIONS_MISSING_SUBSTANTIAL_CONTENT" not in codes
    assert "CITATIONS_ORPHANED" not in codes


def test_uncited_page_fires_missing():
    """A genuinely uncited >200-word page fires — the check now measures reality."""
    page = _page(url="https://mysite.org/blog", word_count=500, links=[])
    assert "CITATIONS_MISSING_SUBSTANTIAL_CONTENT" in _codes(page)


def test_orphan_citation_fires_orphaned():
    page = _page(url="https://mysite.org/blog", word_count=500,
                 links=[ParsedLink("https://ref.org/bare", None, False)])
    codes = _codes(page)
    assert "CITATIONS_MISSING_SUBSTANTIAL_CONTENT" not in codes  # it HAS a citation
    assert "CITATIONS_ORPHANED" in codes


# ── source accessibility ──────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_check_source_accessibility():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404 if "broken" in str(request.url) else 200)

    transport = httpx.MockTransport(handler)
    with patch("api.crawler.fetcher.socket.getaddrinfo", return_value=_PUBLIC):
        async with httpx.AsyncClient(transport=transport) as client:
            bad = await check_source_accessibility(
                {"https://ref.org/ok", "https://ref.org/broken"}, client)
    assert bad == {"https://ref.org/broken"}


def test_assess_marks_inaccessible():
    pc = PageCitations(url="https://p", citations=[Citation(text="s", url="https://ref.org/broken", context="s")])
    issue = assess_citation_readiness(pc, 500, inaccessible_urls={"https://ref.org/broken"})
    assert issue.has_inaccessible_sources is True


def test_broken_source_flagged():
    page = _page(url="https://mysite.org/blog", word_count=500,
                 links=[ParsedLink("https://ref.org/broken", "src", False)])
    issues = citation_source_issues([page], {"https://ref.org/broken"})
    assert [i.code for i in issues] == ["CITATIONS_SOURCES_INACCESSIBLE"]


def test_accessible_sources_not_flagged():
    page = _page(url="https://mysite.org/blog", word_count=500,
                 links=[ParsedLink("https://ref.org/ok", "src", False)])
    assert citation_source_issues([page], set()) == []
    assert citation_source_issues([page], {"https://other.org/x"}) == []
