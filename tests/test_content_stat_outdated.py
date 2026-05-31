"""Tests for CONTENT_STAT_OUTDATED issue detection (M4.2).

Spec: docs/pending/2026-05-31_m4_2_content_stat_outdated.md

Unit tests for detect_outdated_stat() and integration with check_page().
"""

import pytest

from api.crawler.checkers.ai_readiness import detect_outdated_stat
from api.crawler.issue_checker import check_page
from api.crawler.parser import ParsedPage

CURRENT_YEAR = 2026


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_page(url="https://example.com/page", *, first_1500_words=None,
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
        first_1500_words=first_1500_words,
        **kw,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Unit tests — detect_outdated_stat
# ═══════════════════════════════════════════════════════════════════════════


class TestDetectOutdatedStat:
    def test_old_year_flagged(self):
        """A year >=24mo old without current year -> flagged."""
        result = detect_outdated_stat("the best options in 2021", current_year=CURRENT_YEAR)
        assert result is not None
        assert result["year"] == 2021
        assert "2021" in result["sentence"]

    def test_current_year_present_skips(self):
        """If current year appears in the window, skip entirely."""
        result = detect_outdated_stat(
            "In 2023 things changed. As of 2026 it still holds.",
            current_year=CURRENT_YEAR,
        )
        assert result is None

    def test_copyright_excluded(self):
        """Year preceded by © should not be flagged."""
        result = detect_outdated_stat("© 2021 Living Systems", current_year=CURRENT_YEAR)
        assert result is None

    def test_copyright_word_excluded(self):
        """Year preceded by 'copyright' should not be flagged."""
        result = detect_outdated_stat("Copyright 2021 All rights reserved", current_year=CURRENT_YEAR)
        assert result is None

    def test_date_range_excluded(self):
        """Date ranges like 2019–2024 should not be flagged."""
        result = detect_outdated_stat("from 2019–2024", current_year=CURRENT_YEAR)
        assert result is None

    def test_date_range_hyphen_excluded(self):
        """Date ranges like 2019-2024 should not be flagged."""
        result = detect_outdated_stat("from 2019-2024 report", current_year=CURRENT_YEAR)
        assert result is None

    def test_pre_2000_not_flagged(self):
        """Years before 2000 don't match the 20xx pattern."""
        result = detect_outdated_stat("In 1900, the field began", current_year=CURRENT_YEAR)
        assert result is None

    def test_off_by_one_not_flagged(self):
        """Year == current_year - 1 (2025) should NOT be flagged (only <=2024)."""
        result = detect_outdated_stat("as of 2025 the data shows", current_year=CURRENT_YEAR)
        assert result is None

    def test_boundary_year_flagged(self):
        """Year == current_year - 2 (2024) IS flagged."""
        result = detect_outdated_stat("the 2024 survey results show", current_year=CURRENT_YEAR)
        assert result is not None
        assert result["year"] == 2024

    def test_empty_text_no_crash(self):
        """Empty string should return None without error."""
        result = detect_outdated_stat("", current_year=CURRENT_YEAR)
        assert result is None

    def test_none_text_no_crash(self):
        """None value should return None without error."""
        result = detect_outdated_stat(None, current_year=CURRENT_YEAR)
        assert result is None

    def test_no_year_text_no_crash(self):
        """Text with no year references should return None."""
        result = detect_outdated_stat("This page has no years at all.", current_year=CURRENT_YEAR)
        assert result is None

    def test_snippet_truncated(self):
        """Snippet should be truncated to <=160 chars."""
        long_text = "In 2021 " + "x" * 200
        result = detect_outdated_stat(long_text, current_year=CURRENT_YEAR)
        assert result is not None
        assert len(result["sentence"]) <= 160

    def test_oldest_year_selected(self):
        """When multiple old years present, the oldest is reported."""
        result = detect_outdated_stat(
            "In 2022 we updated from 2019 data",
            current_year=CURRENT_YEAR,
        )
        assert result is not None
        assert result["year"] == 2019


# ═══════════════════════════════════════════════════════════════════════════
# Integration tests — check_page emits CONTENT_STAT_OUTDATED
# ═══════════════════════════════════════════════════════════════════════════


class TestCheckPageIntegration:
    def test_non_indexable_not_emitted(self):
        """Non-indexable pages should NOT emit CONTENT_STAT_OUTDATED."""
        page = _make_page(
            is_indexable=False,
            first_1500_words="the best options in 2021",
        )
        issues = check_page(page)
        codes = [i.code for i in issues]
        assert "CONTENT_STAT_OUTDATED" not in codes

    def test_indexable_emitted(self, monkeypatch):
        """Indexable page with old year -> CONTENT_STAT_OUTDATED emitted."""
        # Pin datetime.now().year to 2026 for determinism
        import datetime as dt_module

        class _FakeNow:
            def __init__(self, *a, **kw):
                pass
            @classmethod
            def now(cls, *a, **kw):
                return dt_module.datetime(2026, 5, 31, 12, 0, 0)
            year = 2026

        monkeypatch.setattr(dt_module, "datetime", type(
            "FakeDatetime", (dt_module.datetime,), {"now": staticmethod(lambda *a, **kw: dt_module.datetime.__new__(dt_module.datetime, 2026, 5, 31, 12, 0, 0))}
        ))

        page = _make_page(
            first_1500_words="the best options in 2021 are documented here",
        )
        issues = check_page(page)
        codes = [i.code for i in issues]
        assert "CONTENT_STAT_OUTDATED" in codes
        issue = next(i for i in issues if i.code == "CONTENT_STAT_OUTDATED")
        assert issue.extra["year"] == 2021
        assert "2021" in issue.extra["sentence"]

    def test_no_text_window_no_crash(self):
        """Page with no text windows should not crash."""
        page = _make_page(
            first_1500_words=None,
        )
        issues = check_page(page)
        codes = [i.code for i in issues]
        assert "CONTENT_STAT_OUTDATED" not in codes
