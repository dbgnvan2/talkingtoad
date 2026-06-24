"""Crawlability-related checks: noindex (meta vs header), long-paragraph signal,
and the post-crawl AMP HEAD result mapping.

Extracted from api/crawler/issue_checker.py in v2.6 M9.1 (Cycle K).
Zero-logic move — function bodies are byte-identical to the originals.
"""

from api.crawler.parser import ParsedPage

from api.crawler.checkers.registry import Issue, make_issue


def _check_crawlability(page: ParsedPage, issues: list[Issue]) -> None:
    url = page.url
    if not page.is_indexable:
        # Defensive case/whitespace handling: parsers may surface "HEADER",
        # "Header", or " header " for the same X-Robots-Tag source. A strict
        # `== "header"` lets every non-lowercase variant fall through to the
        # NOINDEX_META branch, which is the wrong diagnosis — it sends users
        # looking at HTML meta tags when the actual cause is in the server's
        # response headers.
        robots_source = page.robots_source
        is_header_source = (
            robots_source is not None
            and str(robots_source).strip().lower() == "header"
        )
        if is_header_source:
            issues.append(make_issue("NOINDEX_HEADER", url,
                                     extra={"source": "X-Robots-Tag HTTP header",
                                            "directive": page.robots_directive}))
        else:
            issues.append(make_issue("NOINDEX_META", url,
                                     extra={"source": "meta robots tag",
                                            "directive": page.robots_directive}))

    # ── Tier 1 §4.6: Long paragraphs ────────────────────────────────────────
    # Defensive: `getattr(page, "long_paragraph_count", 0)` returns None when
    # the attribute is present with an explicit None value (parser artifact
    # for malformed pages where the counter was never populated). `None > 0`
    # raises TypeError and crashes the crawl for that page. The `or 0`
    # coalesces both "missing attribute" and "attribute is None" to 0.
    long_para = getattr(page, "long_paragraph_count", 0) or 0
    if long_para > 0:
        issues.append(make_issue("PARA_TOO_LONG", url, extra={
            "long_paragraph_count": long_para,
        }))

    # ── Agent-readiness WP2: JS-dependent navigation ─────────────────────────
    # The parser sets this flag when navigation regions exist but contain no
    # usable links in the raw HTML (menu built client-side by JavaScript).
    if getattr(page, "js_dependent_navigation", False):
        issues.append(make_issue("JS_DEPENDENT_NAVIGATION", url))


def check_amphtml_links(
    pages: list[ParsedPage],
    amp_statuses: dict[str, int],
) -> list[Issue]:
    """Emit AMPHTML_BROKEN for pages whose AMP URL returned a non-200 status.

    Args:
        pages: All crawled pages (only those with amphtml_url are checked).
        amp_statuses: Mapping of {amphtml_url: status_code} from the engine's
            post-crawl AMP HEAD requests.
    """
    issues: list[Issue] = []
    for page in pages:
        if not page.amphtml_url:
            continue
        status = amp_statuses.get(page.amphtml_url)
        if status is not None and status != 200:
            issues.append(make_issue(
                "AMPHTML_BROKEN", page.url,
                extra={"amphtml_url": page.amphtml_url, "amp_status": status},
            ))
    return issues
