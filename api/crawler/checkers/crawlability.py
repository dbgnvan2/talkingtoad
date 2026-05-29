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
        if page.robots_source == "header":
            issues.append(make_issue("NOINDEX_HEADER", url,
                                     extra={"source": "X-Robots-Tag HTTP header",
                                            "directive": page.robots_directive}))
        else:
            issues.append(make_issue("NOINDEX_META", url,
                                     extra={"source": "meta robots tag",
                                            "directive": page.robots_directive}))

    # ── Tier 1 §4.6: Long paragraphs ────────────────────────────────────────
    long_para = getattr(page, "long_paragraph_count", 0)
    if long_para > 0:
        issues.append(make_issue("PARA_TOO_LONG", url, extra={
            "long_paragraph_count": long_para,
        }))


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
