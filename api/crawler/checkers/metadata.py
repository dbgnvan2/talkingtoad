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

    if page.canonical_url is not None:
        # Has a canonical tag
        if not is_same_domain(page.canonical_url, url):
            issue = make_issue("CANONICAL_EXTERNAL", url)
            issue.extra = {"canonical_url": page.canonical_url}
            issues.append(issue)
        # Self-referencing canonical → OK, no issue
    else:
        # No canonical tag — check the two scoping conditions
        # Condition 1: has query string parameters
        if parsed_page.query:
            issues.append(make_issue("CANONICAL_MISSING", url))
        # Condition 2 (near-duplicate): handled in check_cross_page after all pages crawled
