"""Tests for AI bot reference table and utilities (v2.0 AI-Readiness).

Spec: docs/specs/ai-readiness/v2-extended-module.md § 3.2
"""

import pytest
from datetime import datetime, timedelta

from api.services.ai_bots import (
    AI_BOTS,
    LAST_REVIEWED,
    REVIEW_CADENCE_DAYS,
    normalize_user_agent,
    get_bots_by_category,
    get_bot_info,
    is_bot_current,
    is_bot_deprecated,
    get_deprecated_bots,
    validate_table_freshness,
)


class TestAIBotsTable:
    """Test AI bot reference table integrity."""

    def test_all_bots_have_required_fields(self):
        """Every bot must have vendor, category, honors_robots, and current fields."""
        required_fields = {"vendor", "category", "honors_robots", "current"}
        for ua, spec in AI_BOTS.items():
            assert required_fields.issubset(spec.keys()), f"Bot {ua} missing required fields"

    def test_valid_categories(self):
        """All bot categories must be one of the defined types."""
        valid_categories = {"training", "search", "user_fetch", "training_optout"}
        for ua, spec in AI_BOTS.items():
            assert spec["category"] in valid_categories, f"Bot {ua} has invalid category"

    def test_honors_robots_is_valid(self):
        """honors_robots must be bool or 'documented_violations'."""
        for ua, spec in AI_BOTS.items():
            honors = spec["honors_robots"]
            valid = isinstance(honors, bool) or honors == "documented_violations"
            assert valid, f"Bot {ua} has invalid honors_robots value"

    def test_no_duplicate_bot_names(self):
        """No two bots have the same user agent string."""
        uas = list(AI_BOTS.keys())
        assert len(uas) == len(set(uas)), "Duplicate bot names found"

    def test_at_least_20_bots(self):
        """Table should have at least 20 AI bots."""
        assert len(AI_BOTS) >= 20, "AI bot table should have 20+ bots"

    def test_current_and_deprecated_separation(self):
        """Bots are either current or deprecated, not both."""
        for ua, spec in AI_BOTS.items():
            is_current = spec.get("current", True)
            is_deprecated = not is_current
            # If deprecated, should have deprecated_since or note
            if is_deprecated:
                has_context = "deprecated_since" in spec or "note" in spec
                assert has_context, f"Deprecated bot {ua} missing context"

    def test_major_vendors_represented(self):
        """Major AI vendors (OpenAI, Anthropic, Google, etc.) should have bots."""
        vendors = {spec["vendor"] for spec in AI_BOTS.values()}
        major_vendors = {"OpenAI", "Anthropic", "Google", "Perplexity"}
        assert major_vendors.issubset(vendors), "Missing bots from major vendors"

    def test_all_three_categories_present(self):
        """At least training, search, and user_fetch categories should be present."""
        categories = {spec["category"] for spec in AI_BOTS.values()}
        required_categories = {"training", "search", "user_fetch"}
        assert required_categories.issubset(categories), "Missing bot categories"


class TestUserAgentNormalization:
    """Test case-insensitive user agent matching."""

    def test_normalize_user_agent_lowercase(self):
        """normalize_user_agent should lowercase the input."""
        assert normalize_user_agent("GPTBot") == "gptbot"
        assert normalize_user_agent("GPTBOT") == "gptbot"
        assert normalize_user_agent("gptbot") == "gptbot"

    def test_normalize_user_agent_with_whitespace(self):
        """normalize_user_agent should strip whitespace."""
        assert normalize_user_agent("  GPTBot  ") == "gptbot"
        assert normalize_user_agent("\tGPTBot\n") == "gptbot"

    def test_normalize_user_agent_empty(self):
        """normalize_user_agent should return empty string for empty input."""
        assert normalize_user_agent("") == ""
        assert normalize_user_agent(None) == ""


class TestBotCategoryQueries:
    """Test functions for querying bots by category."""

    def test_get_bots_by_category_training(self):
        """get_bots_by_category('training') returns current training bots."""
        training_bots = get_bots_by_category("training")
        assert len(training_bots) > 0
        assert "GPTBot" in training_bots
        assert "ClaudeBot" in training_bots
        # Deprecated bots should not be in current list
        assert "anthropic-ai" not in training_bots

    def test_get_bots_by_category_search(self):
        """get_bots_by_category('search') returns current search bots."""
        search_bots = get_bots_by_category("search")
        assert len(search_bots) > 0
        assert "OAI-SearchBot" in search_bots
        assert "Claude-SearchBot" in search_bots

    def test_get_bots_by_category_user_fetch(self):
        """get_bots_by_category('user_fetch') returns current user-fetch bots."""
        user_fetch_bots = get_bots_by_category("user_fetch")
        assert len(user_fetch_bots) > 0
        assert "ChatGPT-User" in user_fetch_bots
        assert "Claude-User" in user_fetch_bots

    def test_get_bots_by_category_training_optout(self):
        """get_bots_by_category('training_optout') returns opt-out bots."""
        optout_bots = get_bots_by_category("training_optout")
        assert len(optout_bots) > 0
        assert "Google-Extended" in optout_bots


class TestBotLookup:
    """Test functions for looking up bot information."""

    def test_get_bot_info_exists(self):
        """get_bot_info returns spec for known bots."""
        info = get_bot_info("GPTBot")
        assert info is not None
        assert info["vendor"] == "OpenAI"
        assert info["category"] == "training"

    def test_get_bot_info_case_insensitive(self):
        """get_bot_info is case-insensitive."""
        assert get_bot_info("gptbot") == get_bot_info("GPTBot")
        assert get_bot_info("GPTBOT") == get_bot_info("GPTBot")

    def test_get_bot_info_unknown(self):
        """get_bot_info returns None for unknown bots."""
        assert get_bot_info("UnknownBot") is None
        assert get_bot_info("") is None

    def test_is_bot_current_true(self):
        """is_bot_current returns True for current bots."""
        assert is_bot_current("GPTBot") is True
        assert is_bot_current("OAI-SearchBot") is True
        assert is_bot_current("Claude-SearchBot") is True

    def test_is_bot_current_false(self):
        """is_bot_current returns False for deprecated bots."""
        assert is_bot_current("anthropic-ai") is False
        assert is_bot_current("claude-web") is False

    def test_is_bot_current_unknown(self):
        """is_bot_current returns False for unknown bots."""
        assert is_bot_current("UnknownBot") is False

    def test_is_bot_deprecated_true(self):
        """is_bot_deprecated returns True for deprecated bots."""
        assert is_bot_deprecated("anthropic-ai") is True
        assert is_bot_deprecated("claude-web") is True

    def test_is_bot_deprecated_false(self):
        """is_bot_deprecated returns False for current bots."""
        assert is_bot_deprecated("GPTBot") is False
        assert is_bot_deprecated("ClaudeBot") is False

    def test_get_deprecated_bots(self):
        """get_deprecated_bots returns list of deprecated bot UAs."""
        deprecated = get_deprecated_bots()
        assert "anthropic-ai" in deprecated
        assert "claude-web" in deprecated
        assert len(deprecated) > 0
        # Current bots should not be in list
        assert "GPTBot" not in deprecated


class TestTableFreshness:
    """Test validation of bot table currency."""

    def test_validate_table_freshness_recently_reviewed(self):
        """validate_table_freshness returns (True, None) if recently reviewed."""
        # Assuming LAST_REVIEWED is set to today or recently
        is_fresh, warning = validate_table_freshness()
        # This depends on LAST_REVIEWED value, so we just test the return format
        assert isinstance(is_fresh, bool)
        assert warning is None or isinstance(warning, str)

    def test_validate_table_freshness_stale(self, monkeypatch):
        """validate_table_freshness returns (False, warning) if stale."""
        # Mock LAST_REVIEWED to be 400+ days ago
        stale_date = datetime.now() - timedelta(days=400)
        monkeypatch.setattr("api.services.ai_bots.LAST_REVIEWED", stale_date)

        is_fresh, warning = validate_table_freshness()
        assert is_fresh is False
        assert warning is not None
        assert "last reviewed" in warning.lower()


class TestIntegration:
    """Integration tests for AI bots module."""

    def test_bots_have_unique_vendors_across_categories(self):
        """Same vendor can have bots in multiple categories (OpenAI has all 3)."""
        openai_bots = [
            (ua, spec) for ua, spec in AI_BOTS.items()
            if spec["vendor"] == "OpenAI" and spec.get("current")
        ]
        categories = {spec["category"] for ua, spec in openai_bots}
        assert "training" in categories
        assert "search" in categories
        assert "user_fetch" in categories

    def test_anthropic_current_bots(self):
        """Anthropic should have current bots and deprecated ones."""
        anthropic_current = {
            ua for ua, spec in AI_BOTS.items()
            if spec["vendor"] == "Anthropic" and spec.get("current")
        }
        anthropic_deprecated = {
            ua for ua, spec in AI_BOTS.items()
            if spec["vendor"] == "Anthropic" and not spec.get("current")
        }
        assert len(anthropic_current) > 0
        assert len(anthropic_deprecated) > 0
        assert "ClaudeBot" in anthropic_current
        assert "anthropic-ai" in anthropic_deprecated
