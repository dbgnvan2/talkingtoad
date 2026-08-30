"""AI crawler reference table and utilities for v2.0 AI-Readiness checks.

This module maintains a versioned table of AI user agents by category
(training, search, user-fetch, training-optout) and honor-robots behavior.
The table requires review on the cadence in REVIEW_CADENCE_DAYS (below).

Spec: docs/specs/ai-readiness/v2-extended-module.md § 3.2
Tests: tests/test_ai_bots.py
"""

import os
from datetime import datetime

# AF7a: the docstring promised 6 months while the constant enforced 365 days,
# so the "next review due" date advertised in this file (Nov 3) was not the date
# the code checked (May 3 the following year). One source of truth now, and
# overridable so the cadence is config rather than a literal (rule 8).
# Spec:  docs/pending/2026-08-30_audit-fixes.md#AF7
# Tests: tests/test_ai_bot_table_stale.py
LAST_REVIEWED = datetime(2026, 5, 3)
REVIEW_CADENCE_DAYS = int(os.getenv("TT_AI_BOT_REVIEW_CADENCE_DAYS", "180"))

AI_BOTS = {
    # OpenAI bots (3-bot architecture: training, search, user-fetch)
    "GPTBot": {
        "vendor": "OpenAI",
        "category": "training",
        "honors_robots": True,
        "current": True,
    },
    "OAI-SearchBot": {
        "vendor": "OpenAI",
        "category": "search",
        "honors_robots": True,
        "current": True,
    },
    "ChatGPT-User": {
        "vendor": "OpenAI",
        "category": "user_fetch",
        "honors_robots": False,
        "current": True,
    },
    # Anthropic bots (3-bot architecture: training, search, user-fetch)
    "ClaudeBot": {
        "vendor": "Anthropic",
        "category": "training",
        "honors_robots": True,
        "current": True,
    },
    "Claude-SearchBot": {
        "vendor": "Anthropic",
        "category": "search",
        "honors_robots": True,
        "current": True,
    },
    "Claude-User": {
        "vendor": "Anthropic",
        "category": "user_fetch",
        # Anthropic states ALL three of its bots — ClaudeBot, Claude-User,
        # Claude-SearchBot — honor robots.txt (vendor docs; verified 2026-07).
        # This is vendor-specific: OpenAI's ChatGPT-User says robots.txt "may
        # not apply", and Perplexity-User does not honor it.
        "honors_robots": True,
        "current": True,
    },
    # Anthropic deprecated bots (flagged for user awareness)
    "anthropic-ai": {
        "vendor": "Anthropic",
        "category": "training",
        "honors_robots": True,
        "current": False,
        "deprecated_since": "2024-07",
    },
    "claude-web": {
        "vendor": "Anthropic",
        "category": "training",
        "honors_robots": True,
        "current": False,
        "deprecated_since": "2024-07",
    },
    # Perplexity bots (search-focused, user-fetch)
    "PerplexityBot": {
        "vendor": "Perplexity",
        "category": "search",
        "honors_robots": "documented_violations",
        "current": True,
    },
    "Perplexity-User": {
        "vendor": "Perplexity",
        "category": "user_fetch",
        "honors_robots": False,
        "current": True,
    },
    # Google (training opt-out variant, user-fetch bots for AI features)
    "Google-Extended": {
        "vendor": "Google",
        "category": "training_optout",
        "honors_robots": True,
        "current": True,
        "note": "Opted out of Gemini training; users can set this in Search Console",
    },
    "Google-Agent": {
        "vendor": "Google",
        "category": "user_fetch",
        "honors_robots": False,
        "current": True,
    },
    "Google-NotebookLM": {
        "vendor": "Google",
        "category": "user_fetch",
        "honors_robots": False,
        "current": True,
    },
    # Apple (training opt-out, search bot)
    "Applebot-Extended": {
        "vendor": "Apple",
        "category": "training_optout",
        "honors_robots": True,
        "current": True,
    },
    "Applebot": {
        "vendor": "Apple",
        "category": "search",
        "honors_robots": True,
        "current": True,
    },
    # Common Crawl (training corpus)
    "CCBot": {
        "vendor": "CommonCrawl",
        "category": "training",
        "honors_robots": True,
        "current": True,
    },
    # ByteDance (training)
    "Bytespider": {
        "vendor": "ByteDance",
        "category": "training",
        "honors_robots": "documented_violations",
        "current": True,
        "note": "Documented history of ignoring robots.txt",
    },
    # Amazon (training)
    "Amazonbot": {
        "vendor": "Amazon",
        "category": "training",
        "honors_robots": True,
        "current": True,
    },
    # Meta (training)
    "Meta-ExternalAgent": {
        "vendor": "Meta",
        "category": "training",
        "honors_robots": True,
        "current": True,
    },
    # Mistral (user-fetch)
    "MistralAI-User": {
        "vendor": "Mistral",
        "category": "user_fetch",
        "honors_robots": False,
        "current": True,
    },
    # DuckDuckGo (search)
    "DuckAssistBot": {
        "vendor": "DuckDuckGo",
        "category": "search",
        "honors_robots": True,
        "current": True,
    },
}


def normalize_user_agent(ua: str) -> str:
    """Normalize user agent for case-insensitive matching (RFC 9309)."""
    return ua.strip().lower() if ua else ""


def get_bots_by_category(category: str) -> list[str]:
    """Return list of current bot user agents in a given category.

    Args:
        category: One of 'training', 'search', 'user_fetch', 'training_optout'

    Returns:
        List of bot user agent strings (original case)
    """
    return [
        ua for ua, spec in AI_BOTS.items()
        if spec.get("current") and spec.get("category") == category
    ]


def get_bot_info(ua: str) -> dict | None:
    """Get bot metadata for a user agent (case-insensitive lookup)."""
    normalized = normalize_user_agent(ua)
    for bot_ua, spec in AI_BOTS.items():
        if normalize_user_agent(bot_ua) == normalized:
            return spec
    return None


def is_bot_current(ua: str) -> bool:
    """Check if a user agent is current (not deprecated)."""
    info = get_bot_info(ua)
    return info.get("current", False) if info else False


def is_bot_deprecated(ua: str) -> bool:
    """Check if a user agent is deprecated."""
    info = get_bot_info(ua)
    return info is not None and not info.get("current", True)


def get_deprecated_bots() -> list[str]:
    """Return list of deprecated AI bot user agents."""
    return [
        ua for ua, spec in AI_BOTS.items()
        if not spec.get("current", True)
    ]


def validate_table_freshness() -> tuple[bool, str | None]:
    """Check if AI bot table is current.

    Returns:
        (is_current, warning_message_if_stale)
    """
    from datetime import timedelta
    days_since_review = (datetime.now() - LAST_REVIEWED).days
    if days_since_review > REVIEW_CADENCE_DAYS:
        warning = (
            f"AI bot reference table last reviewed {days_since_review} days ago "
            f"(cadence: {REVIEW_CADENCE_DAYS} days). Update recommended."
        )
        return False, warning
    return True, None
