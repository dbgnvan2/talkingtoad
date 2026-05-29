"""URL-structure checks: length, casing, embedded spaces, underscores.

Pure string operations — no fetch required.

Extracted from api/crawler/issue_checker.py in v2.6 M9.1 (Cycle K).
Zero-logic move — function body is byte-identical to the original
check_url_structure().

NOTE: The spec did not enumerate a url_structure module by name; this file
was created because check_url_structure is a standalone check whose issue
codes (URL_TOO_LONG, URL_UPPERCASE, etc.) form their own category.
Logically, "URL hygiene" is distinct from "security" and "crawlability".
"""

from urllib.parse import urlparse

from api.crawler.checkers.registry import Issue, make_issue


def check_url_structure(url: str) -> list[Issue]:
    """Return URL structure issues for *url* (spec §E2).

    These checks are pure string operations — no fetching required.
    Called by the engine before fetching each URL.
    """
    issues: list[Issue] = []
    path = urlparse(url).path

    if len(url) > 200:
        issues.append(make_issue("URL_TOO_LONG", url,
                                 extra={"length": len(url), "limit": 200}))
    if any(c.isupper() for c in path):
        issues.append(make_issue("URL_UPPERCASE", url,
                                 extra={"path": path}))
    # Catch both URL-encoded (%20) and literal-space (" ") variants.
    # urlparse preserves literal spaces in the path component, so a raw
    # HTML href like <a href="/about us"> survives intact. The original
    # `"%20" in ...` check only matched the encoded form, silently letting
    # malformed literal-space URLs evade URL_HAS_SPACES. Re-use the `path`
    # variable computed at the top of the function so we only call urlparse
    # once. (QA Cycle R V2.)
    if "%20" in path or " " in path:
        issues.append(make_issue("URL_HAS_SPACES", url,
                                 extra={"path": path}))
    if "_" in path:
        issues.append(make_issue("URL_HAS_UNDERSCORES", url,
                                 extra={"path": path}))

    return issues
