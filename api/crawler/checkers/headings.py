"""Heading-related checks: H1 presence, multiple H1s, empty headings,
heading-level skips.

Extracted from api/crawler/issue_checker.py in v2.6 M9.1 (Cycle K).
Zero-logic move — function body is byte-identical to the original
_check_headings().
"""

from api.crawler.parser import ParsedPage

from api.crawler.checkers.registry import Issue, make_issue


def _check_headings(
    page: ParsedPage,
    issues: list[Issue],
    *,
    effective_h1s: list[str] | None = None,
    effective_outline: list[dict] | None = None,
) -> None:
    url = page.url
    h1s = effective_h1s if effective_h1s is not None else page.h1_tags
    outline = effective_outline if effective_outline is not None else page.headings_outline

    h1_count = len(h1s)
    if h1_count == 0:
        # Include first few headings so user can see what exists.
        # Defensive: use .get('text') with `or ''` fallback. Strict
        # h['text'] bracket access would raise KeyError when the parser
        # omits the key for a malformed heading tag; the author already
        # knew this (the empty-headings check below uses .get()) — these
        # diagnostic formatters silently disagreed.
        top_headings = [f"H{h['level']}: {h.get('text') or ''}" for h in outline[:5]]
        issues.append(make_issue("H1_MISSING", url,
                                 extra={"headings_found": top_headings} if top_headings else None))
    elif h1_count > 1:
        issue = make_issue("H1_MULTIPLE", url)
        issue.extra = {"h1_tags": h1s, "count": h1_count}
        issues.append(issue)

    # Empty headings.
    # Defensive: `.get("text", "")` returns None when the key is present
    # with an explicit None value (parser artifact for malformed tags).
    # None.strip() raises AttributeError and crashes the comprehension.
    # The `or ""` coalesces both "missing key" and "key with None value".
    empty_headings = [h for h in outline if not (h.get("text") or "").strip()]
    if empty_headings:
        issues.append(make_issue("HEADING_EMPTY", url,
            extra={"empty_levels": [f"H{h['level']}" for h in empty_headings]}))

    # Detect skipped heading levels
    levels = [h["level"] for h in outline]
    for i in range(1, len(levels)):
        if levels[i] > levels[i - 1] + 1:
            issue = make_issue("HEADING_SKIP", url)
            # Include the heading outline so user can see the skip.
            # Same defensive pattern as the H1_MISSING formatter above:
            # h.get('text') with `or ''` fallback so a missing or None
            # text key does not raise KeyError / AttributeError mid-emission.
            issue.extra = {
                "outline": [f"H{h['level']}: {h.get('text') or ''}" for h in outline],
                "skip_at": i,  # Index where skip occurred
            }
            issues.append(issue)
            break  # Report once per page
