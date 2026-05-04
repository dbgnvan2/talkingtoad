"""AI-Readiness v2.0 site-level checks for AI crawler access.

This module checks robots.txt directives for AI bot accessibility,
detecting misconfiguration, deprecated directives, and access blocks
for search/training/user-fetch bots.

Spec: docs/specs/ai-readiness/v2-extended-module.md § 3.3
Tests: tests/test_ai_readiness.py
"""

from api.crawler.issue_checker import make_issue, Issue
from api.crawler.robots import RobotsData
from api.services.ai_bots import (
    AI_BOTS,
    get_bots_by_category,
    get_bot_info,
    is_bot_deprecated,
    normalize_user_agent,
)


def check_ai_bot_access(robots_data: RobotsData, start_url: str) -> list[Issue]:
    """Check if AI bots are permitted by robots.txt.

    Validates robots.txt for 20+ AI training/search/user-fetch bots,
    detecting blocks, misconfiguration, and deprecated directives.

    Args:
        robots_data: Parsed robots.txt with allow/disallow rules
        start_url: Crawl start URL (used for context in issue reporting)

    Returns:
        List of Issue objects for AI bot access violations
    """
    issues: list[Issue] = []

    # If robots.txt unreachable, no checks possible
    if robots_data.raw_text is None:
        return issues

    # Parse ALL agent rules (allow and disallow) for comprehensive checking
    all_agents_mentioned = _extract_all_agents(robots_data)
    disallowed_by_agent = _extract_disallowed_paths(robots_data)

    # Check blanket disallow first (highest severity)
    if _is_blanket_disallow(disallowed_by_agent):
        return [make_issue("AI_BOT_BLANKET_DISALLOW", start_url)]

    # Check for deprecated directives in any rules
    if _check_deprecated_directives(all_agents_mentioned):
        issues.append(make_issue("AI_BOT_DEPRECATED_DIRECTIVE", start_url))

    # Check each AI bot category for explicit blocks
    search_bots = get_bots_by_category("search")
    training_bots = get_bots_by_category("training")
    user_fetch_bots = get_bots_by_category("user_fetch")

    for bot_ua in search_bots:
        if _is_bot_blocked(bot_ua, disallowed_by_agent):
            issues.append(make_issue(
                "AI_BOT_SEARCH_BLOCKED", start_url, extra={"blocked_bot": bot_ua}
            ))
            break

    for bot_ua in training_bots:
        if _is_bot_blocked(bot_ua, disallowed_by_agent):
            issues.append(make_issue(
                "AI_BOT_TRAINING_DISALLOWED", start_url, extra={"blocked_bot": bot_ua}
            ))
            break

    for bot_ua in user_fetch_bots:
        if _is_bot_blocked(bot_ua, disallowed_by_agent):
            issues.append(make_issue(
                "AI_BOT_USER_FETCH_BLOCKED", start_url, extra={"blocked_bot": bot_ua}
            ))
            break

    # Flag if no explicit AI bot directives at all (informational)
    if not _has_ai_directives(all_agents_mentioned):
        issues.append(make_issue("AI_BOT_NO_AI_DIRECTIVES", start_url))

    return issues


def _extract_all_agents(robots_data: RobotsData) -> set[str]:
    """Extract all user-agent names mentioned in robots.txt (any directive)."""
    agents = set()
    if not robots_data.raw_text:
        return agents
    for line in robots_data.raw_text.split("\n"):
        line = line.strip()
        if line.lower().startswith("user-agent:"):
            agent = line.split(":", 1)[1].strip().lower()
            if agent:
                agents.add(agent)
    return agents


def _extract_disallowed_paths(robots_data: RobotsData) -> dict[str, list[str]]:
    """Extract Disallow rules grouped by User-agent.

    Returns:
        Dict mapping user agent -> list of disallowed path patterns
    """
    if not robots_data.raw_text:
        return {}

    disallowed = {}
    current_agent = None

    for line in robots_data.raw_text.split("\n"):
        line = line.strip()

        # Skip comments and empty lines
        if not line or line.startswith("#"):
            continue

        # Parse User-agent line
        if line.lower().startswith("user-agent:"):
            current_agent = line.split(":", 1)[1].strip().lower()
            if current_agent not in disallowed:
                disallowed[current_agent] = []
            continue

        # Parse Disallow lines
        if line.lower().startswith("disallow:"):
            if current_agent:
                path = line.split(":", 1)[1].strip()
                if path:  # Ignore empty disallow
                    disallowed[current_agent].append(path)

    return disallowed


def _is_blanket_disallow(disallowed_by_agent: dict[str, list[str]]) -> bool:
    """Check if robots.txt has User-agent: * with Disallow: /"""
    if "*" in disallowed_by_agent:
        paths = disallowed_by_agent["*"]
        return "/" in paths or (len(paths) > 0 and any(p == "/" for p in paths))
    return False


def _is_bot_blocked(ua: str, disallowed_by_agent: dict[str, list[str]]) -> bool:
    """Check if a specific bot is blocked by robots.txt.

    Uses RFC 9309 case-insensitive matching. Checks specific bot UA first,
    then wildcard rules.

    Args:
        ua: User agent string (e.g., "GPTBot")
        disallowed_by_agent: Dict of disallowed paths by user agent

    Returns:
        True if bot is blocked
    """
    ua_lower = normalize_user_agent(ua)

    # Check specific user agent
    for agent_key, paths in disallowed_by_agent.items():
        if normalize_user_agent(agent_key) == ua_lower:
            return "/" in paths or (len(paths) > 0 and any(p == "/" for p in paths))

    # Check wildcard rules
    if "*" in disallowed_by_agent:
        paths = disallowed_by_agent["*"]
        return "/" in paths or (len(paths) > 0 and any(p == "/" for p in paths))

    return False


def _check_deprecated_directives(all_agents: set[str]) -> bool:
    """Check if robots.txt references deprecated AI bot user agents."""
    deprecated_uas = {
        normalize_user_agent(ua)
        for ua, info in AI_BOTS.items()
        if not info.get("current", True)
    }
    return any(normalize_user_agent(a) in deprecated_uas for a in all_agents)


def _has_ai_directives(all_agents: set[str]) -> bool:
    """Check if robots.txt has any explicit directives for known AI bots."""
    known_uas = {normalize_user_agent(ua) for ua in AI_BOTS.keys()}
    return any(normalize_user_agent(a) in known_uas for a in all_agents)
