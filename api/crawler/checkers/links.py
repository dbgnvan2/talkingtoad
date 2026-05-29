"""Link / redirect helpers: broken-link status mapping, redirect classification,
and the auto-redirect heuristics (trailing-slash, case-normalise).

Extracted from api/crawler/issue_checker.py in v2.6 M9.1 (Cycle K).
Zero-logic move — function bodies are byte-identical to the originals.
"""

from api.crawler.normaliser import is_same_domain

from api.crawler.checkers.registry import Issue, make_issue


def issue_for_status(status_code: int, url: str) -> Issue | None:
    """Return a broken-link issue if *status_code* indicates a broken link, else None.

    Only standard HTTP 4xx/5xx codes (400–599) are considered broken.
    Non-standard codes such as LinkedIn's 999 anti-bot response are ignored.
    503 is treated as a warning (not critical) because it is commonly returned by
    bot-protection layers and CDNs even when the page loads fine for real visitors.
    """
    if status_code == 404:
        return make_issue("BROKEN_LINK_404", url, extra={"status_code": status_code})
    if status_code == 410:
        return make_issue("BROKEN_LINK_410", url, extra={"status_code": status_code})
    if status_code == 503:
        return make_issue("BROKEN_LINK_503", url, extra={"status_code": status_code})
    if 500 <= status_code <= 599:
        return make_issue("BROKEN_LINK_5XX", url, extra={"status_code": status_code})
    return None


def _is_trailing_slash_only(url: str, final_url: str) -> bool:
    """Return True if the only difference between *url* and *final_url* is a trailing slash."""
    return url.rstrip("/") == final_url.rstrip("/")


def _is_case_normalise_only(url: str, final_url: str) -> bool:
    """Return True if the only difference is URL path casing (server auto-lowercase)."""
    from urllib.parse import urlparse as _urlparse
    u, f = _urlparse(url), _urlparse(final_url)
    return (
        u.scheme == f.scheme
        and u.netloc.lower() == f.netloc.lower()
        and u.path.lower() == f.path.lower()
        and u.query == f.query
        and u.path != f.path          # path IS different (otherwise no redirect)
    )


def issues_for_redirect(
    url: str,
    first_status: int,
    redirect_chain: list[str],
    final_url: str | None = None,
    base_url: str | None = None,
) -> list[Issue]:
    """Return redirect issues for a URL that redirected.

    Args:
        url: The original URL that was fetched.
        first_status: HTTP status code of the first response in the chain.
        redirect_chain: Intermediate URLs (not including the final destination).
        final_url: The URL after all redirects have been followed (used to detect
            auto-corrected redirects like trailing-slash and case normalisation).
        base_url: The crawl start URL — used to distinguish internal from external
            301 redirects. If provided and the URL is internal, INTERNAL_REDIRECT_301
            is emitted instead of the generic REDIRECT_301.
    """
    result: list[Issue] = []

    # Detect whether the redirect is one that CMSes and servers handle automatically,
    # so we can flag it as informational rather than actionable.
    if final_url and first_status == 301 and len(redirect_chain) <= 1:
        if _is_trailing_slash_only(url, final_url):
            result.append(make_issue("REDIRECT_TRAILING_SLASH", url,
                                     extra={"from": url, "to": final_url}))
            return result
        if _is_case_normalise_only(url, final_url):
            result.append(make_issue("REDIRECT_CASE_NORMALISE", url,
                                     extra={"from": url, "to": final_url}))
            return result

    if first_status == 301:
        if base_url and is_same_domain(url, base_url):
            issue = make_issue("INTERNAL_REDIRECT_301", url)
        else:
            issue = make_issue("REDIRECT_301", url)
        issue.extra = {"redirect_to": final_url or (redirect_chain[0] if redirect_chain else None)}
        result.append(issue)
    elif first_status == 302:
        issue = make_issue("REDIRECT_302", url)
        issue.extra = {"redirect_to": final_url or (redirect_chain[0] if redirect_chain else None)}
        result.append(issue)

    if len(redirect_chain) > 1:
        issue = make_issue("REDIRECT_CHAIN", url)
        # Build full chain: original → intermediates → final
        full_chain = [url] + redirect_chain + ([final_url] if final_url else [])
        issue.extra = {"chain": full_chain, "hops": len(redirect_chain)}
        result.append(issue)

    return result
