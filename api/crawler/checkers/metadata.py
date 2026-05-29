"""Metadata-related checks: canonical tag validation.

Extracted from api/crawler/issue_checker.py in v2.6 M9.1 (Cycle K).
Zero-logic move — function body is byte-identical to the original
_check_canonical().
"""

from urllib.parse import urlparse

from api.crawler.normaliser import is_same_domain
from api.crawler.parser import ParsedPage

from api.crawler.checkers.registry import Issue, make_issue


def _check_canonical(page: ParsedPage, issues: list[Issue]) -> None:
    url = page.url
    parsed_page = urlparse(url)

    # Defensive normalisation:
    #   V2: <link rel="canonical" href=""> yields canonical_url="". The
    #       pre-fix `is not None` guard let "" through to is_same_domain,
    #       which returned False, falsely emitting CANONICAL_EXTERNAL. An
    #       empty href is functionally equivalent to a missing tag and
    #       must fall through to the missing-canonical branch below.
    #   V3: sloppy CMSes / templaters can leave leading or trailing
    #       whitespace on the href. Python's stdlib urlparse happens to
    #       tolerate leading whitespace before the scheme, so the bug
    #       does not currently manifest — but stripping here makes the
    #       code robust against future urlparse changes and ensures the
    #       canonical_url stored in issue.extra is the clean form.
    clean_canonical = (page.canonical_url or "").strip()

    if clean_canonical:
        # Has a (non-empty, stripped) canonical tag
        if not is_same_domain(clean_canonical, url):
            issue = make_issue("CANONICAL_EXTERNAL", url)
            issue.extra = {"canonical_url": clean_canonical}
            issues.append(issue)
        # Self-referencing canonical → OK, no issue
    else:
        # No canonical tag (or empty/whitespace-only one) — check the
        # two scoping conditions.
        # Condition 1: has query string parameters
        if parsed_page.query:
            issues.append(make_issue("CANONICAL_MISSING", url))
        # Condition 2 (near-duplicate): handled in check_cross_page after all pages crawled
