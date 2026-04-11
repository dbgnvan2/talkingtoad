"""
URL normalisation and domain boundary utilities for the TalkingToad crawler.

Implements the rules from spec §2.7.
"""

from urllib.parse import (
    urlparse,
    urlunparse,
    urlencode,
    parse_qsl,
    ParseResult,
)

# Tracking parameters stripped before deduplication (spec §2.7)
_STRIP_PARAMS: frozenset[str] = frozenset(
    [
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "ref",
        "session_id",
        "sid",
        "fbclid",
        "gclid",
    ]
)

# Maximum unique query-string variants per path before we stop queuing new ones (spec §2.7)
QUERY_VARIANT_CAP = 50

# Admin / login path prefixes and exact paths that must be skipped (spec §2.9)
_SKIP_PATH_PREFIXES: tuple[str, ...] = (
    "/wp-admin/",
    "/admin/",
)
_SKIP_PATH_EXACT: frozenset[str] = frozenset(
    [
        "/wp-login.php",
        "/login",
        "/logout",
        "/signin",
        "/signout",
        "/user/login",
        "/user/logout",
    ]
)


def normalise_url(url: str) -> str:
    """Return a canonical string form of *url*.

    Steps applied (spec §2.7):
    1. Lowercase scheme and host.
    2. Remove fragment identifier.
    3. Strip known tracking/session parameters.
    4. Rebuild sorted, stable query string from surviving params.
    5. Strip trailing slash from path (root path "/" is kept).

    Returns the normalised URL string.
    Raises ``ValueError`` if *url* has no scheme or host.
    """
    parsed: ParseResult = urlparse(url)

    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid URL (missing scheme or host): {url!r}")

    scheme = parsed.scheme.lower()
    host = parsed.netloc.lower()

    # Strip tracking params; preserve order of remaining params
    surviving = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k not in _STRIP_PARAMS
    ]
    query = urlencode(surviving)

    path = parsed.path

    # Strip trailing slash unless path is bare root
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    # Fragment is always dropped
    normalised = urlunparse((scheme, host, path, "", query, ""))
    return normalised


def is_same_domain(url: str, base_url: str) -> bool:
    """Return True if *url* is within the same crawl domain as *base_url*.

    Rules (spec §2.7):
    - ``www`` prefix is treated as the same domain.
    - Any other subdomain is external.
    - Protocol differences (http/https) are ignored for boundary purposes.
    """
    url_host = urlparse(url).netloc.lower()
    base_host = urlparse(base_url).netloc.lower()

    url_host = _strip_www(url_host)
    base_host = _strip_www(base_host)

    return url_host == base_host


def _strip_www(host: str) -> str:
    """Remove the leading ``www.`` prefix from *host* if present."""
    if host.startswith("www."):
        return host[4:]
    return host


def is_admin_path(url: str) -> bool:
    """Return True if *url* should be skipped as an admin/login path (spec §2.9)."""
    path = urlparse(url).path

    for prefix in _SKIP_PATH_PREFIXES:
        if path.startswith(prefix):
            return True

    if path in _SKIP_PATH_EXACT:
        return True

    return False


# WordPress auto-generated / system URL patterns that produce non-actionable
# SEO noise. Skipped by default; can be disabled via CrawlSettings.
_WP_NOISE_PATH_PREFIXES: tuple[str, ...] = (
    # Taxonomy / user archives
    "/author/",
    "/category/",
    "/tag/",
    # Feed URLs
    "/feed/",
    "/rss/",
    "/rss2/",
    "/atom/",
    "/comments/feed/",
)

_WP_NOISE_PATH_SUFFIXES: tuple[str, ...] = (
    "/feed/",
    "/feed",
    "/rss",
    "/rss2",
    "/atom",
)

import re as _re

# Date archive: /2024/, /2024/03/, /2024/03/15/
_DATE_ARCHIVE_RE = _re.compile(r"^/\d{4}(/\d{2}(/\d{2})?)?/?$")

# Paginated archive: /page/2/, /page/10/
_PAGINATION_RE = _re.compile(r"/page/\d+/?$")


def is_wp_noise_path(url: str) -> bool:
    """Return True if *url* is a WordPress auto-generated page that produces
    non-actionable SEO noise (archives, feeds, search, pagination).

    Covers:
    - Author / category / tag archives
    - Date-based archives  (/2024/, /2024/03/, /2024/03/15/)
    - Paginated archives   (/page/2/)
    - Feed URLs            (/feed/, /?feed=rss2)
    - Search results       (?s=query)
    - Query-style author   (?author=1)
    """
    parsed = urlparse(url)
    path = parsed.path
    qs = parsed.query

    # Path prefix matches
    for prefix in _WP_NOISE_PATH_PREFIXES:
        if path.startswith(prefix):
            return True

    # Path suffix matches (e.g. /any-page/feed/)
    for suffix in _WP_NOISE_PATH_SUFFIXES:
        if path.endswith(suffix):
            return True

    # Date archive paths
    if _DATE_ARCHIVE_RE.match(path):
        return True

    # Paginated archive paths
    if _PAGINATION_RE.search(path):
        return True

    # Query string signals
    if qs:
        params: dict[str, str] = {}
        for part in qs.split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                params[k] = v

        # Search results: ?s=
        if "s" in params:
            return True

        # Query-style feed: ?feed=rss2
        if "feed" in params:
            return True

        # Query-style author: ?author=1
        if params.get("author", "").isdigit():
            return True

    return False


# Keep old name as alias so existing engine import still works
is_wp_archive_path = is_wp_noise_path


class QueryVariantTracker:
    """Track unique query-string variants per path within a crawl job.

    When ``record`` returns ``False`` the caller should stop queuing new
    variants for that path (cap reached — spec §2.7).
    """

    def __init__(self, cap: int = QUERY_VARIANT_CAP) -> None:
        self._cap = cap
        # path → set of normalised query strings
        self._variants: dict[str, set[str]] = {}

    def record(self, url: str) -> bool:
        """Record *url* as a variant of its path.

        Returns ``True`` if the URL is within the cap and should be crawled.
        Returns ``False`` if the cap has already been reached for this path.
        """
        parsed = urlparse(url)
        path = parsed.path

        # URLs with no query string are never subject to the variant cap
        if not parsed.query:
            return True

        variants = self._variants.setdefault(path, set())

        if parsed.query in variants:
            # Already seen this exact query string — deduplicated
            return True

        if len(variants) >= self._cap:
            return False

        variants.add(parsed.query)
        return True

    def variant_count(self, path: str) -> int:
        """Return number of unique query variants recorded for *path*."""
        return len(self._variants.get(path, set()))
