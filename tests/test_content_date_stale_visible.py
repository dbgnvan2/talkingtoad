"""Tests for CONTENT_DATE_STALE_VISIBLE issue detection (M4.1).

Spec: docs/pending/2026-05-31_m4_1_content_date_stale_visible.md

Unit tests for check_content_date_stale_visible() and integration with
check_page() via the existing infer_page_type() classifier.
"""

from datetime import date

import pytest

from api.crawler.checkers.ai_readiness import check_content_date_stale_visible
from api.crawler.issue_checker import check_page
from api.crawler.parser import ParsedPage

TODAY = date(2026, 5, 31)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_page(url="https://example.com/page", *, date_modified=None,
               is_indexable=True, **kw):
    """Construct a minimal ParsedPage for testing."""
    return ParsedPage(
        url=url,
        final_url=url,
        status_code=200,
        response_size_bytes=5000,
        title="Test Page",
        meta_description="A test page",
        og_title="Test Page",
        og_description="A test page",
        og_image="https://example.com/og.jpg",
        twitter_card="summary",
        canonical_url=url,
        h1_tags=["Test Page"],
        headings_outline=[{"level": 1, "text": "Test Page"}],
        is_indexable=is_indexable,
        robots_directive=None,
        links=[],
        has_favicon=None,
        has_viewport_meta=True,
        schema_types=[],
        external_script_count=0,
        external_stylesheet_count=0,
        word_count=500,
        lang_attr="en",
        date_modified=date_modified,
        **kw,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Unit tests — check_content_date_stale_visible
# ═══════════════════════════════════════════════════════════════════════════


class TestContentDateStaleVisible:
    def test_article_old_date_flagged(self):
        """Article with date 28 months ago should be flagged (cadence 12mo)."""
        page = _make_page("https://example.com/blog/old-post",
                          date_modified="2023-01-01")
        result = check_content_date_stale_visible(page, today=TODAY)
        assert result is not None
        assert result["age_months"] == 41  # (2026-05-31 - 2023-01-01) = 1246 days // 30
        assert result["page_type"] == "article"
        assert result["recommended_refresh_months"] == 12
        assert result["visible_date"] == "2023-01-01"

    def test_service_recent_date_not_flagged(self):
        """Service with date 16 months ago should NOT be flagged (cadence 24mo)."""
        page = _make_page("https://example.com/services/web-design",
                          date_modified="2025-01-01")
        result = check_content_date_stale_visible(page, today=TODAY)
        assert result is None

    def test_team_member_never_flagged(self):
        """Team member page should never be flagged regardless of date."""
        page = _make_page("https://example.com/team/john-doe",
                          date_modified="2019-01-01")
        result = check_content_date_stale_visible(page, today=TODAY)
        assert result is None

    def test_absent_date_not_flagged(self):
        """No double-flag when date_modified is absent."""
        page = _make_page("https://example.com/page", date_modified=None)
        result = check_content_date_stale_visible(page, today=TODAY)
        assert result is None

    def test_unparseable_date_not_flagged(self):
        """Unparseable date should not crash and return None."""
        page = _make_page("https://example.com/page",
                          date_modified="not-a-date")
        result = check_content_date_stale_visible(page, today=TODAY)
        assert result is None

    def test_article_exactly_12mo_not_flagged(self):
        """Article exactly at cadence boundary should NOT be flagged (strict >)."""
        # 2025-05-31 -> 2026-05-31 = 365 days = 12 months (12*30=360 days)
        page = _make_page("https://example.com/blog/exact",
                          date_modified="2025-05-31")
        result = check_content_date_stale_visible(page, today=TODAY)
        assert result is None

    def test_article_13mo_flagged(self):
        """Article 13 months old should be flagged."""
        page = _make_page("https://example.com/blog/13mo",
                          date_modified="2025-04-30")
        result = check_content_date_stale_visible(page, today=TODAY)
        assert result is not None
        assert result["age_months"] == 13

    def test_non_indexable_checker_still_returns(self):
        """The checker itself doesn't check indexability — issue_checker gates it."""
        page = _make_page("https://example.com/blog/noindex",
                          date_modified="2023-01-01", is_indexable=False)
        # Checker returns result; issue_checker.py guards emission with is_indexable
        result = check_content_date_stale_visible(page, today=TODAY)
        assert result is not None

    def test_iso_datetime_format_parsed(self):
        """ISO datetime strings (with time component) should be parsed."""
        page = _make_page("https://example.com/blog/datetime",
                          date_modified="2023-01-15T10:30:00")
        result = check_content_date_stale_visible(page, today=TODAY)
        assert result is not None
        assert result["visible_date"] == "2023-01-15"

    def test_home_page_stale(self):
        """Home page 30 months old should be flagged (cadence 24mo)."""
        page = _make_page("https://example.com/",
                          date_modified="2023-11-01")
        result = check_content_date_stale_visible(page, today=TODAY)
        assert result is not None
        assert result["page_type"] == "home"
        assert result["recommended_refresh_months"] == 24

    def test_about_page_within_cadence(self):
        """About page 20 months old should NOT be flagged (cadence 24mo)."""
        page = _make_page("https://example.com/about",
                          date_modified="2024-09-01")
        result = check_content_date_stale_visible(page, today=TODAY)
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════
# Integration tests — check_page emits the issue
# ═══════════════════════════════════════════════════════════════════════════


class TestContentDateStaleVisibleIntegration:
    def test_check_page_emits_for_stale_article(self):
        """check_page should emit CONTENT_DATE_STALE_VISIBLE for stale article."""
        page = _make_page("https://example.com/blog/old-post",
                          date_modified="2023-01-01")
        issues = check_page(page)
        codes = [i.code for i in issues]
        assert "CONTENT_DATE_STALE_VISIBLE" in codes
        stale_issue = next(i for i in issues if i.code == "CONTENT_DATE_STALE_VISIBLE")
        assert stale_issue.extra["visible_date"] == "2023-01-01"
        assert stale_issue.extra["page_type"] == "article"

    def test_check_page_not_emitted_for_non_indexable(self):
        """check_page should NOT emit CONTENT_DATE_STALE_VISIBLE for noindex pages."""
        page = _make_page("https://example.com/blog/noindex",
                          date_modified="2023-01-01", is_indexable=False)
        issues = check_page(page)
        codes = [i.code for i in issues]
        assert "CONTENT_DATE_STALE_VISIBLE" not in codes

    def test_check_page_not_emitted_absent_date(self):
        """check_page should NOT emit when date_modified is absent (no double-flag)."""
        page = _make_page("https://example.com/blog/no-date",
                          date_modified=None)
        issues = check_page(page)
        codes = [i.code for i in issues]
        assert "CONTENT_DATE_STALE_VISIBLE" not in codes
