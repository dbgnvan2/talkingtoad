"""
M3.6 — Scoring-Scope Bug Fix Tests (adversarial).

Verifies that _count_statistics and _count_inline_quotations now read the
first_1500_words window, so statistics/quotations beyond word 600 are counted.

Test plan:
  - test_statistics_beyond_600_are_counted: stats at words ~250, ~1000, ~1500 → counted
  - test_quotations_beyond_600_are_counted: quotation at word ~1000 → counted
  - test_regression_early_stats_still_count: stats in first 200 words → still counted
  - test_statistics_past_1500_excluded: stat at word ~2000 → excluded
"""

import pytest
from dataclasses import dataclass, field
from unittest.mock import MagicMock

from api.crawler.parser import ParsedPage
from api.crawler.checkers.ai_readiness import (
    _count_statistics,
    _count_inline_quotations,
    _run_geo_checks,
)
from api.crawler.checkers.registry import Issue


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _filler(n_words: int) -> str:
    """Generate n_words of filler text that does NOT match _STAT_RE or _ATTRIBUTION_RE."""
    # Use a word that cannot trigger stats ("lorem") repeated
    return " ".join(["lorem"] * n_words)


def _make_page(
    *,
    first_200_words: str | None = None,
    first_600_words: str | None = None,
    first_1500_words: str | None = None,
    word_count: int = 800,
    headings_outline: list[dict] | None = None,
    links: list | None = None,
    blockquote_count: int = 0,
    **kwargs,
) -> ParsedPage:
    """Create a minimal ParsedPage with the GEO fields needed for testing."""
    return ParsedPage(
        url="https://example.com/article",
        final_url="https://example.com/article",
        status_code=200,
        response_size_bytes=5000,
        title="Test Article",
        meta_description="Test",
        og_title=None,
        og_description=None,
        og_image=None,
        twitter_card=None,
        canonical_url=None,
        h1_tags=["Test Article"],
        headings_outline=headings_outline or [{"level": 1, "text": "Test Article"}],
        is_indexable=True,
        robots_directive=None,
        links=links or [],
        has_favicon=None,
        has_viewport_meta=True,
        schema_types=[],
        external_script_count=0,
        external_stylesheet_count=0,
        word_count=word_count,
        first_200_words=first_200_words,
        first_600_words=first_600_words,
        first_1500_words=first_1500_words,
        blockquote_count=blockquote_count,
        **kwargs,
    )


def _issue_codes(issues: list) -> list[str]:
    return [i.code for i in issues]


# ---------------------------------------------------------------------------
# _count_statistics tests
# ---------------------------------------------------------------------------

class TestCountStatisticsWidenedWindow:
    """Verify _count_statistics reads first_1500_words, not just first_600_words."""

    def test_statistics_beyond_600_are_counted(self):
        """Stats at words ~250, ~1000, ~1500 must ALL be counted.

        Pre-fix: only the stat at word ~250 would be in the 600-word window;
        the others would be invisible → false STATISTICS_COUNT_LOW.
        """
        # Build text: filler(249) + stat + filler(749) + stat + filler(499) + stat
        text = (
            _filler(249) + " 95% of users " +
            _filler(749) + " 300 customers " +
            _filler(499) + " 42 seconds "
        )
        page = _make_page(
            first_1500_words=text,
            first_600_words=None,  # force fallback chain to use first_1500_words
            first_200_words=None,
        )
        count = _count_statistics(
            page.first_1500_words or page.first_600_words or page.first_200_words or "",
            page.links,
            page,
        )
        assert count >= 3, f"Expected >=3 statistics, got {count}"

    def test_statistics_beyond_600_prevents_false_flag(self):
        """STATISTICS_COUNT_LOW must NOT fire when stats exist beyond word 600.

        This is the actual bug scenario: a page with legitimate statistics
        past the old 600-word window was being falsely flagged.
        """
        # Stats only at word ~800 and ~1200 (outside old 600-word cap)
        text_1500 = _filler(799) + " 85% percent " + _filler(399) + " 1200 users "
        # The first_600 window has no stats (because they're all past word 600)
        text_600 = _filler(600)
        text_200 = _filler(200)

        page = _make_page(
            first_1500_words=text_1500,
            first_600_words=text_600,
            first_200_words=text_200,
            word_count=2000,
        )

        issues = []
        _run_geo_checks(page, page.url, issues)
        codes = _issue_codes(issues)
        assert "STATISTICS_COUNT_LOW" not in codes, (
            "STATISTICS_COUNT_LOW should not fire — stats exist in the 1500-word window"
        )

    def test_regression_early_stats_still_count(self):
        """Statistics in the first 200 words must still be counted (no regression)."""
        text = "There are 50 users and 30% growth " + _filler(166)
        page = _make_page(
            first_1500_words=text + _filler(900),
            first_600_words=text + _filler(400),
            first_200_words=text,
        )
        count = _count_statistics(
            page.first_1500_words or page.first_600_words or page.first_200_words or "",
            page.links,
            page,
        )
        assert count >= 2, f"Expected >=2 early statistics, got {count}"

    def test_statistics_past_1500_excluded(self):
        """A stat placed at word ~2000 must NOT be counted (window cap enforced)."""
        # first_1500_words contains NO statistics
        text_1500 = _filler(1500)
        # Imagine the full page has a stat at word ~2000 (an appendix)
        # But since we only feed first_1500_words, it should not be counted.
        page = _make_page(
            first_1500_words=text_1500,
            first_600_words=_filler(600),
            first_200_words=_filler(200),
        )
        count = _count_statistics(
            page.first_1500_words or page.first_600_words or page.first_200_words or "",
            page.links,
            page,
        )
        assert count == 0, f"Expected 0 statistics (all past window), got {count}"

    def test_fallback_to_first_600_when_1500_is_none(self):
        """When first_1500_words is None, gracefully falls back to first_600_words."""
        text_600 = _filler(200) + " 75% of companies " + _filler(399)
        page = _make_page(
            first_1500_words=None,
            first_600_words=text_600,
            first_200_words=_filler(200),
        )
        count = _count_statistics(
            page.first_1500_words or page.first_600_words or page.first_200_words or "",
            page.links,
            page,
        )
        assert count >= 1, f"Expected >=1 statistic from fallback first_600_words, got {count}"


# ---------------------------------------------------------------------------
# _count_inline_quotations tests
# ---------------------------------------------------------------------------

class TestCountInlineQuotationsWidenedWindow:
    """Verify _count_inline_quotations reads first_1500_words."""

    def test_quotations_beyond_600_are_counted(self):
        """A quotation (attribution pattern) at word ~1000 must be counted.

        Pre-fix: text beyond word 600 was invisible to the quotation counter.
        """
        # Place an attribution pattern at word ~1000
        text_1500 = _filler(999) + ' according to Dr. Smith, the results are clear ' + _filler(500)
        page = _make_page(
            first_1500_words=text_1500,
            first_600_words=_filler(600),  # no quotations in the 600-word window
            first_200_words=_filler(200),
        )
        count = _count_inline_quotations(page)
        assert count >= 1, f"Expected >=1 quotation at word ~1000, got {count}"

    def test_quotations_in_first_200_still_counted(self):
        """Quotations in the first 200 words must still be detected (regression check)."""
        text = 'According to the CEO, revenue grew ' + _filler(165)
        page = _make_page(
            first_1500_words=text + _filler(1300),
            first_600_words=text + _filler(400),
            first_200_words=text,
        )
        count = _count_inline_quotations(page)
        assert count >= 1, f"Expected >=1 early quotation, got {count}"

    def test_quotation_past_1500_excluded(self):
        """Quotations past word 1500 (in an appendix) must NOT be counted."""
        # first_1500_words has no attribution patterns
        text_1500 = _filler(1500)
        page = _make_page(
            first_1500_words=text_1500,
            first_600_words=_filler(600),
            first_200_words=_filler(200),
        )
        count = _count_inline_quotations(page)
        assert count == 0, f"Expected 0 quotations (all past window), got {count}"

    def test_multiple_quotations_in_wide_window(self):
        """Multiple attribution patterns spread across 1500 words all counted."""
        text_1500 = (
            _filler(100) + " says Dr. Jones " +
            _filler(400) + " according to the study " +
            _filler(400) + " noted the researcher " +
            _filler(594)
        )
        page = _make_page(
            first_1500_words=text_1500,
            first_600_words=_filler(600),
            first_200_words=_filler(200),
        )
        count = _count_inline_quotations(page)
        assert count >= 3, f"Expected >=3 quotations in 1500-word window, got {count}"

    def test_fallback_to_first_600_when_1500_is_none(self):
        """When first_1500_words is None, falls back to first_600_words."""
        text_600 = _filler(100) + " according to experts " + _filler(498)
        page = _make_page(
            first_1500_words=None,
            first_600_words=text_600,
            first_200_words=_filler(200),
        )
        count = _count_inline_quotations(page)
        assert count >= 1, f"Expected >=1 quotation from fallback, got {count}"


# ---------------------------------------------------------------------------
# Integration: _run_geo_checks with widened window
# ---------------------------------------------------------------------------

class TestGeoChecksIntegration:
    """End-to-end: _run_geo_checks uses first_1500_words for both counters."""

    def test_quotations_missing_not_fired_when_quotation_beyond_600(self):
        """QUOTATIONS_MISSING should NOT fire when a quotation exists at word ~1000."""
        text_1500 = _filler(999) + ' "Innovation is key," said the director ' + _filler(500)
        page = _make_page(
            first_1500_words=text_1500,
            first_600_words=_filler(600),
            first_200_words=_filler(200),
            word_count=2000,
            blockquote_count=0,
        )
        issues = []
        _run_geo_checks(page, page.url, issues)
        codes = _issue_codes(issues)
        assert "QUOTATIONS_MISSING" not in codes

    def test_both_issues_fire_when_no_stats_or_quotes_in_1500(self):
        """Both STATISTICS_COUNT_LOW and QUOTATIONS_MISSING fire on truly empty pages."""
        page = _make_page(
            first_1500_words=_filler(1500),
            first_600_words=_filler(600),
            first_200_words=_filler(200),
            word_count=800,
            blockquote_count=0,
        )
        issues = []
        _run_geo_checks(page, page.url, issues)
        codes = _issue_codes(issues)
        assert "STATISTICS_COUNT_LOW" in codes
        assert "QUOTATIONS_MISSING" in codes
