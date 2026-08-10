"""Shared URL join key for the performance ledger (CLN4).

`match_key` folds the differences that routinely separate a crawl seed from the
GSC/GA4 property it is joined against: beyond what `normalise_url` does (lowercase
host, drop fragment, strip tracking params, strip trailing slash) it ALSO folds a
leading `www.` and the http/https scheme — because a crawl seeded at
`https://example.org` is commonly joined against a `https://www.example.org/` or
`http://…` GSC property.

Used ONLY for MATCHING a performance-source URL (a GSC row or a bundle page) to a
crawled page. Ledger rows are always STORED under the crawled page's exact `url`,
which is the key the page-priority consumer (`crawl.py`) reads by — so storage
key, match, and lookup all agree.

Spec: docs/pending/2026-08-08_debt-cleanup-batch.md#CLN4
"""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse

from api.crawler.normaliser import _strip_www, normalise_url


def match_key(url: str) -> str:
    """www/scheme/trailing-slash-tolerant join key. Raises ``ValueError`` (from
    `normalise_url`) on a scheme/host-less URL."""
    p = urlparse(normalise_url(url))
    return urlunparse(("", _strip_www(p.netloc), p.path, "", p.query, ""))


def build_crawled_key_map(pages) -> dict[str, str]:
    """Map ``match_key(crawled url) -> the crawled page's exact url`` for joining
    a performance source onto the key the ledger consumer reads by. URLs that
    cannot be normalised are skipped."""
    out: dict[str, str] = {}
    for pg in pages:
        try:
            out[match_key(pg.url)] = pg.url
        except ValueError:
            continue
    return out
