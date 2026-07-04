"""Security-related checks: HTTP-page, mixed content, HSTS, unsafe cross-origin.

Extracted from api/crawler/issue_checker.py in v2.6 M9.1 (Cycle K).
Zero-logic move — function body is byte-identical to the original
_check_security().
"""

from urllib.parse import urlparse

from api.crawler.parser import ParsedPage

from api.crawler.checkers.registry import Issue, make_issue


def _check_security(
    page: ParsedPage,
    issues: list[Issue],
    *,
    hsts_checked_hosts: set[str] | None,
) -> None:
    url = page.url

    # HTTP_PAGE — non-HTTPS final URL.
    # RFC 3986 specifies URL schemes are case-insensitive; httpx will
    # happily fetch "HTTP://example.com". The original strict
    # startswith("http://") missed uppercase / title-case schemes, which
    # then fell through to the HTTPS-only checks below and produced a
    # MISSING_HSTS false positive on an actually-unencrypted page.
    # Compare against the lowercased URL; `url[7:]` still slices the
    # original (the "HTTP://" prefix is exactly 7 chars regardless of
    # case) so the https_url field stays correctly formed.
    # (QA Cycle R V3.)
    if url.lower().startswith("http://"):
        issues.append(make_issue("HTTP_PAGE", url,
                                 extra={"http_url": url,
                                        "https_url": "https://" + url[7:]}))
        return  # HTTPS-only checks below don't apply

    # MIXED_CONTENT — report the active/passive breakdown (R2.x #2). Active
    # resources (script/iframe/stylesheet) are BLOCKED by the browser (real
    # breakage); passive (img/media) are auto-upgraded or load with a warning.
    if page.mixed_content_count > 0:
        active = getattr(page, "mixed_content_active_count", 0) or 0
        passive = getattr(page, "mixed_content_passive_count", 0) or 0
        issues.append(make_issue("MIXED_CONTENT", url,
                                 extra={"mixed_count": page.mixed_content_count,
                                        "active_count": active,
                                        "passive_count": passive,
                                        "has_active": active > 0}))

    # MISSING_HSTS — emit once per host
    if page.has_hsts is False:
        host = urlparse(url).netloc
        if hsts_checked_hosts is None or host not in hsts_checked_hosts:
            issues.append(make_issue("MISSING_HSTS", url,
                                     extra={"host": host}))
            if hsts_checked_hosts is not None:
                hsts_checked_hosts.add(host)

    # UNSAFE_CROSS_ORIGIN_LINK
    if page.unsafe_cross_origin_count > 0:
        issues.append(make_issue("UNSAFE_CROSS_ORIGIN_LINK", url,
                                 extra={"unsafe_link_count": page.unsafe_cross_origin_count}))
