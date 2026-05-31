"""Tests for M3.5 AI_MAIN_CONTENT_LOW_RATIO issue detection.

Covers:
- _main_content_ratio helper logic (unit tests)
- Integration with issue_checker (indexable-only guard, extra.ratio)
- Adversarial: no-main-region, empty body, exact threshold, barely below
"""

import pytest
from bs4 import BeautifulSoup
from api.crawler.parser import _main_content_ratio, _MAIN_CONTENT_LOW_RATIO


# ---------------------------------------------------------------------------
# Unit tests for _main_content_ratio helper
# ---------------------------------------------------------------------------


def test_main_content_low_ratio_flagged():
    """<main> with 100 chars inside body of 1000 chars -> ratio 0.1, flagged."""
    html = '<html><body><nav>' + 'x' * 500 + '</nav><main>' + 'x' * 100 + '</main><footer>' + 'x' * 400 + '</footer></body></html>'
    soup = BeautifulSoup(html, 'lxml')
    ratio = _main_content_ratio(soup)
    assert ratio is not None
    assert ratio < _MAIN_CONTENT_LOW_RATIO
    assert round(ratio, 2) == 0.1


def test_main_content_high_ratio_not_flagged():
    """<main> that is 80% of body text -> not flagged."""
    html = '<html><body><nav>' + 'x' * 100 + '</nav><main>' + 'x' * 800 + '</main><footer>' + 'x' * 100 + '</footer></body></html>'
    soup = BeautifulSoup(html, 'lxml')
    ratio = _main_content_ratio(soup)
    assert ratio is not None
    assert ratio >= _MAIN_CONTENT_LOW_RATIO


def test_no_main_region_returns_none():
    """No <main>/<article>/[role=main] -> None, not flagged."""
    html = '<html><body><div>content</div></body></html>'
    soup = BeautifulSoup(html, 'lxml')
    assert _main_content_ratio(soup) is None


def test_empty_body_returns_none():
    """Empty body (total 0) -> None, not flagged."""
    html = '<html><body><main></main></body></html>'
    soup = BeautifulSoup(html, 'lxml')
    assert _main_content_ratio(soup) is None


def test_exactly_threshold_not_flagged():
    """Ratio exactly 0.40 -> NOT flagged (strictly < 0.40)."""
    html = '<html><body><nav>' + 'x' * 600 + '</nav><main>' + 'x' * 400 + '</main></body></html>'
    soup = BeautifulSoup(html, 'lxml')
    ratio = _main_content_ratio(soup)
    assert ratio is not None
    assert ratio == 0.40
    assert not (ratio < _MAIN_CONTENT_LOW_RATIO)


def test_barely_below_threshold_flagged():
    """Ratio 0.39 -> flagged."""
    html = '<html><body><nav>' + 'x' * 610 + '</nav><main>' + 'x' * 390 + '</main></body></html>'
    soup = BeautifulSoup(html, 'lxml')
    ratio = _main_content_ratio(soup)
    assert ratio is not None
    assert ratio < _MAIN_CONTENT_LOW_RATIO
    assert round(ratio, 2) == 0.39


def test_article_tag_works():
    """<article> should be recognized as main region."""
    html = '<html><body><nav>' + 'x' * 500 + '</nav><article>' + 'x' * 100 + '</article><footer>' + 'x' * 400 + '</footer></body></html>'
    soup = BeautifulSoup(html, 'lxml')
    ratio = _main_content_ratio(soup)
    assert ratio is not None
    assert ratio < _MAIN_CONTENT_LOW_RATIO


def test_role_main_works():
    """[role=main] should be recognized as main region."""
    html = '<html><body><nav>' + 'x' * 500 + '</nav><div role="main">' + 'x' * 100 + '</div><footer>' + 'x' * 400 + '</footer></body></html>'
    soup = BeautifulSoup(html, 'lxml')
    ratio = _main_content_ratio(soup)
    assert ratio is not None
    assert ratio < _MAIN_CONTENT_LOW_RATIO


def test_parse_error_returns_none():
    """Malformed HTML should return None gracefully."""
    soup = BeautifulSoup('<html', 'lxml')  # intentionally malformed
    assert _main_content_ratio(soup) is None


# ---------------------------------------------------------------------------
# Integration tests with issue_checker
# ---------------------------------------------------------------------------


def _make_parsed_page(*, is_indexable=True, main_content_ratio=None):
    """Create a minimal ParsedPage-like object for issue_checker tests."""
    from unittest.mock import MagicMock
    page = MagicMock()
    page.url = "https://example.com/test"
    page.final_url = "https://example.com/test"
    page.is_indexable = is_indexable
    page.main_content_ratio = main_content_ratio
    return page


def test_issue_emitted_for_indexable_low_ratio():
    """Indexable page with ratio below threshold emits AI_MAIN_CONTENT_LOW_RATIO."""
    from api.crawler.issue_checker import check_page
    from api.crawler.parser import ParsedPage

    # Build a minimal ParsedPage with low ratio
    page = ParsedPage(
        url="https://example.com/test",
        final_url="https://example.com/test",
        status_code=200,
        response_size_bytes=1000,
        title="Test Page",
        meta_description="Test description that is long enough to pass",
        og_title="Test",
        og_description="Test",
        og_image="https://example.com/img.jpg",
        twitter_card="summary",
        canonical_url="https://example.com/test",
        h1_tags=["Test Page"],
        headings_outline=[{"level": 1, "text": "Test Page"}],
        is_indexable=True,
        robots_directive=None,
        links=[],
        has_favicon=None,
        has_viewport_meta=True,
        schema_types=["WebPage"],
        external_script_count=0,
        external_stylesheet_count=0,
        word_count=500,
        lang_attr="en",
        main_content_ratio=0.25,
    )

    issues = check_page(page)
    codes = [i.code for i in issues]
    assert "AI_MAIN_CONTENT_LOW_RATIO" in codes

    # Verify extra.ratio is present
    ratio_issue = next(i for i in issues if i.code == "AI_MAIN_CONTENT_LOW_RATIO")
    assert ratio_issue.extra["ratio"] == 0.25


def test_issue_not_emitted_for_noindex_page():
    """Non-indexable page should NOT emit AI_MAIN_CONTENT_LOW_RATIO."""
    from api.crawler.issue_checker import check_page
    from api.crawler.parser import ParsedPage

    page = ParsedPage(
        url="https://example.com/test",
        final_url="https://example.com/test",
        status_code=200,
        response_size_bytes=1000,
        title="Test Page",
        meta_description="A description",
        og_title=None,
        og_description=None,
        og_image=None,
        twitter_card=None,
        canonical_url=None,
        h1_tags=["Test"],
        headings_outline=[{"level": 1, "text": "Test"}],
        is_indexable=False,
        robots_directive="noindex",
        links=[],
        has_favicon=None,
        has_viewport_meta=True,
        schema_types=[],
        external_script_count=0,
        external_stylesheet_count=0,
        word_count=500,
        lang_attr="en",
        main_content_ratio=0.10,  # Low ratio but noindex
    )

    issues = check_page(page)
    codes = [i.code for i in issues]
    assert "AI_MAIN_CONTENT_LOW_RATIO" not in codes


def test_issue_not_emitted_when_ratio_is_none():
    """Pages with no main region (ratio=None) should NOT emit."""
    from api.crawler.issue_checker import check_page
    from api.crawler.parser import ParsedPage

    page = ParsedPage(
        url="https://example.com/test",
        final_url="https://example.com/test",
        status_code=200,
        response_size_bytes=1000,
        title="Test Page",
        meta_description="Test description that is long enough",
        og_title="Test",
        og_description="Test",
        og_image="https://example.com/img.jpg",
        twitter_card="summary",
        canonical_url="https://example.com/test",
        h1_tags=["Test Page"],
        headings_outline=[{"level": 1, "text": "Test Page"}],
        is_indexable=True,
        robots_directive=None,
        links=[],
        has_favicon=None,
        has_viewport_meta=True,
        schema_types=["WebPage"],
        external_script_count=0,
        external_stylesheet_count=0,
        word_count=500,
        lang_attr="en",
        main_content_ratio=None,  # No main region detected
    )

    issues = check_page(page)
    codes = [i.code for i in issues]
    assert "AI_MAIN_CONTENT_LOW_RATIO" not in codes
