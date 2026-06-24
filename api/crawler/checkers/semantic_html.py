"""Semantic-HTML & interactive-element checks (Agent-readiness Phase 1, WP3).

Emits the codes that describe how operable a page is to an agent reading the
accessibility tree / DOM structure:

    NON_SEMANTIC_BUTTON           — <div>/<span> used as a clickable control
    INTERACTIVE_NO_ACCESSIBLE_NAME — button/field with no accessible name
    LANDMARK_MAIN_MISSING         — no <main> landmark (per page)
    LANDMARK_NAV_MISSING          — no <nav> landmark (homepage only)

All signals are pre-computed on the ParsedPage at parse time (where soup is in
scope); this checker only reads those flags, consistent with the rest of the
``checkers/`` package.
"""

from api.crawler.parser import ParsedPage

from api.crawler.checkers.registry import Issue, make_issue


def check_semantic_html(page: ParsedPage, issues: list[Issue]) -> None:
    """Append semantic-HTML / interactive-element issues for *page*."""
    url = page.url

    # Only meaningful for pages that returned real HTML content.
    if page.status_code >= 400:
        return

    # ── Non-semantic buttons (div/span used as controls) ────────────────────
    nsb = page.non_semantic_buttons or []
    if nsb:
        issues.append(make_issue(
            "NON_SEMANTIC_BUTTON", url,
            extra={"count": len(nsb), "examples": nsb[:5]},
        ))

    # ── Interactive elements with no accessible name ────────────────────────
    unnamed = page.unnamed_interactive or []
    if unnamed:
        issues.append(make_issue(
            "INTERACTIVE_NO_ACCESSIBLE_NAME", url,
            extra={"count": len(unnamed), "examples": unnamed[:5]},
        ))

    # ── Landmarks ───────────────────────────────────────────────────────────
    # <main> landmark — checked on every indexable page.
    if page.is_indexable and not page.has_main_landmark:
        issues.append(make_issue("LANDMARK_MAIN_MISSING", url))

    # <nav> landmark — checked on the homepage only (navigation is site-wide;
    # one representative check avoids per-page noise).
    if page.is_homepage and not page.has_nav_landmark:
        issues.append(make_issue("LANDMARK_NAV_MISSING", url))
