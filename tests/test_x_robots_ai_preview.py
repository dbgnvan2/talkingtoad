"""Tests for X-Robots-Tag AI-preview issue detection (M3.3)."""

import pytest
from api.crawler.parser import _parse_x_robots_ai_directives, ParsedPage
from api.crawler.checkers.registry import _CATALOGUE, _ISSUE_SCORING, _AI_READINESS_CONFIDENCE


class TestParseXRobotsAiDirectives:
    """Unit tests for _parse_x_robots_ai_directives helper."""

    def test_nosnippet_suppresses_preview(self):
        suppressed, blocked, directive, _ = _parse_x_robots_ai_directives({"x-robots-tag": "nosnippet"})
        assert suppressed is True
        assert blocked is False
        assert directive == "nosnippet"

    def test_max_snippet_zero_suppresses_preview(self):
        suppressed, blocked, directive, _ = _parse_x_robots_ai_directives({"x-robots-tag": "max-snippet:0"})
        assert suppressed is True
        assert blocked is False
        assert directive == "max-snippet:0"

    def test_gptbot_noindex_blocks_ai_bot(self):
        suppressed, blocked, _, directive = _parse_x_robots_ai_directives({"x-robots-tag": "GPTBot: noindex"})
        assert suppressed is False
        assert blocked is True
        assert "GPTBot: noindex" in directive

    def test_google_extended_noindex_blocks_ai_bot(self):
        suppressed, blocked, _, directive = _parse_x_robots_ai_directives({"x-robots-tag": "Google-Extended: noindex"})
        assert suppressed is False
        assert blocked is True
        assert "Google-Extended: noindex" in directive

    def test_no_header_returns_false(self):
        suppressed, blocked, _, _ = _parse_x_robots_ai_directives({})
        assert suppressed is False
        assert blocked is False

    def test_index_follow_does_not_trigger(self):
        suppressed, blocked, _, _ = _parse_x_robots_ai_directives({"x-robots-tag": "index, follow"})
        assert suppressed is False
        assert blocked is False

    def test_max_snippet_negative_one_not_suppressed(self):
        suppressed, blocked, _, _ = _parse_x_robots_ai_directives({"x-robots-tag": "max-snippet:-1"})
        assert suppressed is False
        assert blocked is False

    def test_googlebot_noindex_not_ai_bot_blocked(self):
        """googlebot is a general search bot, not an AI crawler."""
        suppressed, blocked, _, _ = _parse_x_robots_ai_directives({"x-robots-tag": "googlebot: noindex"})
        assert suppressed is False
        assert blocked is False

    def test_case_insensitive_header_key(self):
        """Header key lookup must be case-insensitive."""
        suppressed, blocked, _, _ = _parse_x_robots_ai_directives({"X-Robots-Tag": "NOSNIPPET"})
        assert suppressed is True
        assert blocked is False

    def test_case_insensitive_directive_value(self):
        """Directive matching must be case-insensitive."""
        suppressed, blocked, _, _ = _parse_x_robots_ai_directives({"x-robots-tag": "NOSNIPPET"})
        assert suppressed is True

    def test_comma_joined_multi_directive(self):
        suppressed, blocked, directive, _ = _parse_x_robots_ai_directives(
            {"x-robots-tag": "nosnippet, max-snippet:0"}
        )
        assert suppressed is True
        assert blocked is False
        # directive could be either token — both are valid
        assert directive in ("nosnippet", "max-snippet:0")

    def test_both_suppressed_and_bot_blocked(self):
        """A header can trigger both codes simultaneously."""
        suppressed, blocked, s_dir, b_dir = _parse_x_robots_ai_directives(
            {"x-robots-tag": "nosnippet, GPTBot: noindex"}
        )
        assert suppressed is True
        assert blocked is True
        assert s_dir == "nosnippet"
        assert "GPTBot: noindex" in b_dir

    def test_claudebot_nosnippet_blocks_ai_bot(self):
        suppressed, blocked, _, directive = _parse_x_robots_ai_directives(
            {"x-robots-tag": "ClaudeBot: nosnippet"}
        )
        assert suppressed is False
        assert blocked is True

    def test_empty_header_value(self):
        suppressed, blocked, _, _ = _parse_x_robots_ai_directives({"x-robots-tag": ""})
        assert suppressed is False
        assert blocked is False

    def test_max_snippet_positive_not_suppressed(self):
        """max-snippet with a positive value should not suppress."""
        suppressed, blocked, _, _ = _parse_x_robots_ai_directives({"x-robots-tag": "max-snippet:200"})
        assert suppressed is False
        assert blocked is False


class TestRegistryRegistration:
    """Verify both codes are registered in all 3 registries."""

    def test_codes_in_catalogue(self):
        assert "AI_PREVIEW_SUPPRESSED" in _CATALOGUE
        assert "AI_PREVIEW_BLOCKED_AT_BOT" in _CATALOGUE

    def test_catalogue_category(self):
        assert _CATALOGUE["AI_PREVIEW_SUPPRESSED"].category == "ai_readiness"
        assert _CATALOGUE["AI_PREVIEW_BLOCKED_AT_BOT"].category == "ai_readiness"

    def test_catalogue_severity(self):
        # R3: raised to impact 4 (GEO-relevant AI-answer suppression) → warning
        assert _CATALOGUE["AI_PREVIEW_SUPPRESSED"].severity == "warning"
        assert _CATALOGUE["AI_PREVIEW_BLOCKED_AT_BOT"].severity == "warning"

    def test_codes_in_scoring(self):
        assert "AI_PREVIEW_SUPPRESSED" in _ISSUE_SCORING
        assert "AI_PREVIEW_BLOCKED_AT_BOT" in _ISSUE_SCORING

    def test_scoring_values(self):
        assert _ISSUE_SCORING["AI_PREVIEW_SUPPRESSED"] == (4, 1)  # R3 override (GEO)
        assert _ISSUE_SCORING["AI_PREVIEW_BLOCKED_AT_BOT"] == (4, 1)

    def test_codes_in_confidence(self):
        assert "AI_PREVIEW_SUPPRESSED" in _AI_READINESS_CONFIDENCE
        assert "AI_PREVIEW_BLOCKED_AT_BOT" in _AI_READINESS_CONFIDENCE

    def test_confidence_values(self):
        assert _AI_READINESS_CONFIDENCE["AI_PREVIEW_SUPPRESSED"] == "Established"
        assert _AI_READINESS_CONFIDENCE["AI_PREVIEW_BLOCKED_AT_BOT"] == "Established"


class TestIssueEmission:
    """Integration tests: check_page emits these codes correctly."""

    def _make_page(self, **overrides) -> ParsedPage:
        """Build a minimal indexable ParsedPage with sensible defaults."""
        defaults = dict(
            url="https://example.com/page",
            final_url="https://example.com/page",
            status_code=200,
            response_size_bytes=5000,
            title="Test Page",
            meta_description="A test page description for testing.",
            og_title="Test Page",
            og_description="A test page description.",
            og_image="https://example.com/image.jpg",
            twitter_card="summary",
            canonical_url="https://example.com/page",
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
            has_json_ld=True,
        )
        defaults.update(overrides)
        return ParsedPage(**defaults)

    def test_suppressed_emits_on_indexable_page(self):
        from api.crawler.issue_checker import check_page
        page = self._make_page(
            ai_preview_suppressed=True,
            ai_preview_directive="nosnippet",
        )
        issues = check_page(page)
        codes = [i.code for i in issues]
        assert "AI_PREVIEW_SUPPRESSED" in codes
        suppressed_issue = next(i for i in issues if i.code == "AI_PREVIEW_SUPPRESSED")
        assert suppressed_issue.extra["directive"] == "nosnippet"

    def test_bot_blocked_emits_on_indexable_page(self):
        from api.crawler.issue_checker import check_page
        page = self._make_page(
            ai_bot_blocked=True,
            ai_bot_blocked_directive="GPTBot: noindex",
        )
        issues = check_page(page)
        codes = [i.code for i in issues]
        assert "AI_PREVIEW_BLOCKED_AT_BOT" in codes
        blocked_issue = next(i for i in issues if i.code == "AI_PREVIEW_BLOCKED_AT_BOT")
        assert blocked_issue.extra["directive"] == "GPTBot: noindex"

    def test_not_emitted_on_non_indexable_page(self):
        """Non-indexable pages should not emit these codes."""
        from api.crawler.issue_checker import check_page
        page = self._make_page(
            is_indexable=False,
            ai_preview_suppressed=True,
            ai_preview_directive="nosnippet",
            ai_bot_blocked=True,
            ai_bot_blocked_directive="GPTBot: noindex",
        )
        issues = check_page(page)
        codes = [i.code for i in issues]
        assert "AI_PREVIEW_SUPPRESSED" not in codes
        assert "AI_PREVIEW_BLOCKED_AT_BOT" not in codes

    def test_not_emitted_when_not_set(self):
        """Default (no directives) should not emit."""
        from api.crawler.issue_checker import check_page
        page = self._make_page()
        issues = check_page(page)
        codes = [i.code for i in issues]
        assert "AI_PREVIEW_SUPPRESSED" not in codes
        assert "AI_PREVIEW_BLOCKED_AT_BOT" not in codes
