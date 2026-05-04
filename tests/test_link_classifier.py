"""
Tests for api/services/link_classifier.py.

Spec: docs/implementation_plan_geo_analyzer_2026-05-03.md#GEO.4.1
"""

import pytest
from api.services.link_classifier import classify_link, classify_body_links
from api.crawler.parser import ParsedLink


PAGE_URL = "https://example.com/article"


def _link(url: str, text: str = "link") -> ParsedLink:
    return ParsedLink(url=url, text=text, is_internal=False)


# ---------------------------------------------------------------------------
# classify_link
# ---------------------------------------------------------------------------

class TestClassifyLink:
    def test_classifies_authority_domains(self):
        assert classify_link("https://nih.gov/study", PAGE_URL) == "authority"
        assert classify_link("https://w3.org/TR/html5", PAGE_URL) == "authority"
        assert classify_link("https://developer.mozilla.org/docs", PAGE_URL) == "authority"
        assert classify_link("https://github.com/user/repo", PAGE_URL) == "authority"

    def test_classifies_gov_tld(self):
        assert classify_link("https://cdc.gov/health", PAGE_URL) == "authority"
        assert classify_link("https://fbi.gov/report", PAGE_URL) == "authority"

    def test_classifies_edu_tld(self):
        assert classify_link("https://mit.edu/research", PAGE_URL) == "authority"
        assert classify_link("https://stanford.edu/paper", PAGE_URL) == "authority"

    def test_classifies_reference_domains(self):
        assert classify_link("https://en.wikipedia.org/wiki/X", PAGE_URL) == "reference"
        assert classify_link("https://britannica.com/topic", PAGE_URL) == "reference"

    def test_classifies_promotional_with_affiliate_params(self):
        assert classify_link("https://store.com/product?ref=mysite", PAGE_URL) == "promotional"
        assert classify_link("https://store.com/go/item", PAGE_URL) == "promotional"

    def test_classifies_internal_link(self):
        assert classify_link("https://example.com/about", PAGE_URL) == "internal"
        assert classify_link("https://www.example.com/blog", PAGE_URL) == "internal"

    def test_classifies_unknown_as_other(self):
        assert classify_link("https://randomsite.com/page", PAGE_URL) == "other"

    def test_handles_relative_url(self):
        # Relative URLs have no scheme — should return "other"
        result = classify_link("/about", PAGE_URL)
        assert result == "other"

    def test_handles_arxiv(self):
        assert classify_link("https://arxiv.org/abs/2309.12345", PAGE_URL) == "authority"

    def test_handles_doi(self):
        assert classify_link("https://doi.org/10.1000/xyz", PAGE_URL) == "authority"


# ---------------------------------------------------------------------------
# classify_body_links
# ---------------------------------------------------------------------------

class TestClassifyBodyLinks:
    def test_counts_authority_links(self):
        links = [
            _link("https://nih.gov/study"),
            _link("https://arxiv.org/abs/1234"),
        ]
        result = classify_body_links(links, PAGE_URL)
        assert result["authority"] == 2
        assert result["external_body_total"] == 2

    def test_counts_internal_separately(self):
        links = [
            _link("https://example.com/about"),
            _link("https://nih.gov/study"),
        ]
        result = classify_body_links(links, PAGE_URL)
        assert result["internal"] == 1
        assert result["authority"] == 1

    def test_empty_links(self):
        result = classify_body_links([], PAGE_URL)
        assert result["external_body_total"] == 0

    def test_all_promotional(self):
        links = [
            _link("https://shop.com/product?aff=1"),
            _link("https://store.com/go/item"),
        ]
        result = classify_body_links(links, PAGE_URL)
        assert result["promotional"] == 2
        assert result["external_body_total"] == 2

    def test_external_citations_low_fires_correctly(self):
        """GEO.A.2 fires when external_body_total == 0 on 500+ word page."""
        links = [_link("https://example.com/other")]  # internal
        result = classify_body_links(links, PAGE_URL)
        external = result["external_body_total"]
        assert external == 0  # only internal link, no external citations
