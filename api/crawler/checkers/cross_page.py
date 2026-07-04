"""Cross-page duplicate and orphan detection — run after the crawl finishes.

Extracted from api/crawler/issue_checker.py in v2.6 M9.1 (Cycle K).
Zero-logic move — function body is byte-identical to the original
check_cross_page() (which already carries Cycle J's whitespace-strip fix).
"""

from urllib.parse import urlparse

from api.crawler.normaliser import normalise_url
from api.crawler.parser import ParsedPage

from api.crawler.checkers.registry import Issue, make_issue


def check_cross_page(pages: list[ParsedPage], start_url: str | None = None) -> list[Issue]:
    """Run duplicate-detection checks across all crawled pages.

    Detects:
    - TITLE_DUPLICATE: same title on multiple pages
    - META_DESC_DUPLICATE: same meta description on multiple pages
    - TITLE_META_DUPLICATE_PAIR: both title and meta_desc duplicated together
    - CANONICAL_MISSING (near-duplicate condition): same title+meta_desc, no canonical
    - ORPHAN_PAGE: page has no internal links pointing to it

    Args:
        pages: All crawled HTML pages.
        start_url: Normalised start URL of the crawl (homepage — excluded from orphan check).

    Returns a flat list of issues (one per affected URL, not per pair).
    """
    issues: list[Issue] = []

    # Build lookup maps — skip redirect pages (3xx status or has redirect_url).
    # The grouping key is .casefold()ed so semantically-identical titles
    # like "About Us" / "ABOUT US" / "about us" bucket together (search
    # engines treat them as duplicate content). We preserve the *first*
    # observed original casing so the issue extra still reports the
    # human-meaningful string. Each map stores: key -> (original, [urls]).
    title_map: dict[str, tuple[str, list[str]]] = {}
    desc_map: dict[str, tuple[str, list[str]]] = {}
    pair_map: dict[tuple[str, str], tuple[tuple[str, str], list[str]]] = {}

    for page in pages:
        # Skip redirects — they shouldn't be flagged as duplicates
        if page.redirect_url or (300 <= page.status_code < 400):
            continue

        # Normalise both sides: a whitespace-only title is functionally
        # empty and must NOT bucket-up with other whitespace-only titles
        # as TITLE_DUPLICATE (`bool("   ")` is True — the original
        # `if t:` admitted them and inflated the issue count with garbage).
        # We also strip outer whitespace so "My Page" and "My Page " group
        # together — accidental trailing whitespace is a real duplicate.
        t_orig = (page.title or "").strip()
        d_orig = (page.meta_description or "").strip()
        t_key = t_orig.casefold()
        d_key = d_orig.casefold()

        if t_key:
            if t_key not in title_map:
                title_map[t_key] = (t_orig, [])
            title_map[t_key][1].append(page.url)
        if d_key:
            if d_key not in desc_map:
                desc_map[d_key] = (d_orig, [])
            desc_map[d_key][1].append(page.url)
        if t_key and d_key:
            pair_key = (t_key, d_key)
            if pair_key not in pair_map:
                pair_map[pair_key] = ((t_orig, d_orig), [])
            pair_map[pair_key][1].append(page.url)

    # TITLE_DUPLICATE
    for _t_key, (title, urls) in title_map.items():
        if len(urls) > 1:
            for url in urls:
                other_urls = [u for u in urls if u != url]
                issue = make_issue("TITLE_DUPLICATE", url)
                issue.extra = {
                    "title": title,  # The actual duplicated title (first observed casing)
                    "duplicate_urls": other_urls,  # Other pages with same title
                }
                issues.append(issue)

    # META_DESC_DUPLICATE
    for _d_key, (desc, urls) in desc_map.items():
        if len(urls) > 1:
            for url in urls:
                other_urls = [u for u in urls if u != url]
                issue = make_issue("META_DESC_DUPLICATE", url)
                issue.extra = {
                    "description": desc,  # The actual duplicated description (first observed casing)
                    "duplicate_urls": other_urls,  # Other pages with same description
                }
                issues.append(issue)

    # TITLE_META_DUPLICATE_PAIR and CANONICAL_MISSING (near-duplicate condition)
    duplicate_urls: set[str] = set()
    for _pair_key, ((title, desc), urls) in pair_map.items():
        if len(urls) > 1:
            for url in urls:
                other_urls = [u for u in urls if u != url]
                issue = make_issue("TITLE_META_DUPLICATE_PAIR", url)
                issue.extra = {
                    "title": title,  # The actual duplicated title (first observed casing)
                    "description": desc,  # The actual duplicated description (first observed casing)
                    "duplicate_urls": other_urls,  # Other pages with same pair
                }
                issues.append(issue)
                duplicate_urls.add(url)

    # CANONICAL_MISSING — near-duplicate condition (spec §3.1.2 condition 2)
    page_by_url = {p.url: p for p in pages}
    for url in duplicate_urls:
        page = page_by_url.get(url)
        if page and page.canonical_url is None and not urlparse(url).query:
            # No query string (that's condition 1, already emitted in check_page)
            # and no canonical → emit CANONICAL_MISSING for near-duplicate condition
            issues.append(make_issue("CANONICAL_MISSING", url))

    # ORPHAN_PAGE — pages with no internal links pointing to them.
    # A page linking to itself does NOT make it discoverable; only links
    # from OTHER pages do. The pre-fix code added every internal link to
    # the discovered bucket, so a genuinely orphan page with a self-link
    # (a "Back to top" anchor, a logo link to the current URL, etc.)
    # silently evaded detection.
    linked_urls: set[str] = set()
    for page in pages:
        try:
            page_norm = normalise_url(page.url)
        except Exception:
            page_norm = None

        for link in page.links:
            if link.is_internal:
                try:
                    link_norm = normalise_url(link.url)
                except Exception:
                    continue
                # Drop self-links — a page linking to itself does not
                # make it discoverable.
                if link_norm and link_norm != page_norm:
                    linked_urls.add(link_norm)

    for page in pages:
        try:
            norm = normalise_url(page.url)
        except Exception:
            continue
        if norm == start_url:
            continue  # homepage is always the entry point
        if norm not in linked_urls:
            issues.append(make_issue("ORPHAN_PAGE", page.url,
                                     extra={"title": page.title,
                                            # R2.x #4: link discovery is raw-HTML only.
                                            "caveat": "Internal links are discovered from raw HTML; "
                                            "pages linked only via JavaScript or query-driven "
                                            "listings (e.g. loop grids) may be false positives."}))

    return issues
