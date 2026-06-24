"""Link / redirect helpers: broken-link status mapping, redirect classification,
and the auto-redirect heuristics (trailing-slash, case-normalise).

Extracted from api/crawler/issue_checker.py in v2.6 M9.1 (Cycle K).
Zero-logic move — function bodies are byte-identical to the originals.
"""

from api.crawler.normaliser import is_same_domain

from api.crawler.checkers.registry import Issue, make_issue


def check_placeholder_links(page, issues: list[Issue]) -> None:
    """Emit PLACEHOLDER_LINK / WRONG_PLACEHOLDER_LINK (Agent-readiness WP4).

    Reads the ``page.placeholder_links`` list pre-computed by the parser. Each
    entry has a ``kind`` of ``"placeholder"`` (dead CTA: ``#`` /
    ``javascript:void(0)``) or ``"wrong_domain"`` (example.com / localhost /
    stray search-engine homepage). One issue is emitted per kind that occurs.
    """
    entries = getattr(page, "placeholder_links", None) or []
    if not entries:
        return
    dead = [e for e in entries if e.get("kind") == "placeholder"]
    wrong = [e for e in entries if e.get("kind") == "wrong_domain"]
    if dead:
        issues.append(make_issue(
            "PLACEHOLDER_LINK", page.url,
            extra={"count": len(dead), "examples": dead[:5]},
        ))
    if wrong:
        issues.append(make_issue(
            "WRONG_PLACEHOLDER_LINK", page.url,
            extra={"count": len(wrong), "examples": wrong[:5]},
        ))


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

    # Count "real" intermediates by filtering out any chain entry that is
    # equal to the final URL. This collapses two conventions that exist
    # in the test suite and the wild (chain == [final_url] for a single
    # direct redirect vs. chain == [real_intermediates...] for true
    # multi-hop) into a single notion: how many hops happened beyond the
    # direct A → final redirect?
    #
    # The original `<= 1` gate on the forgiveness branch was too permissive:
    # it admitted both 0-intermediate (direct A → A/) and 1-real-intermediate
    # (A → B → A/) chains. The latter is a genuine multi-hop redirect that
    # should NOT be classified as a harmless trailing-slash fix.
    #
    # The original REDIRECT_CHAIN gate (`len(redirect_chain) > 1`) had the
    # mirror image of the same bug — it missed real 2-hop chains where the
    # chain happens to have only one intermediate entry (because the
    # convention varies). Using `real_intermediates >= 1` aligns both gates
    # to the same definition of "real chain".
    #
    # (QA Cycle R V1.)
    real_intermediates = [h for h in redirect_chain if h != final_url]

    # Detect whether the redirect is one that CMSes and servers handle automatically,
    # so we can flag it as informational rather than actionable. Only applies
    # when there are NO real intermediate hops — a chain that detours through
    # another URL on the way to a trailing-slash final URL is NOT a harmless
    # auto-correction.
    if final_url and first_status == 301 and len(real_intermediates) == 0:
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

    if len(real_intermediates) >= 1:
        issue = make_issue("REDIRECT_CHAIN", url)
        # Build full chain: original → intermediates → final
        full_chain = [url] + redirect_chain + ([final_url] if final_url else [])
        issue.extra = {"chain": full_chain, "hops": len(real_intermediates)}
        result.append(issue)

    return result
