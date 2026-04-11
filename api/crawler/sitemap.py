"""
Sitemap auto-discovery and parsing for the TalkingToad crawler.

Implements spec §3.1.7.
"""

import gzip
import io
import logging
from urllib.parse import urlparse, urljoin

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_FETCH_TIMEOUT = 5.0
_STANDARD_SITEMAP_PATH = "/sitemap.xml"


class SitemapResult:
    """Outcome of sitemap discovery and parsing.

    Attributes:
        urls (list[str]): All ``<loc>`` URLs extracted from the sitemap(s).
        found (bool): True if a sitemap was successfully located and parsed.
        missing_issue (dict | None): ``SITEMAP_MISSING`` issue dict when not found.
        source_url (str | None): The URL from which the sitemap was actually read.
    """

    def __init__(
        self,
        urls: list[str],
        found: bool,
        missing_issue: dict | None,
        source_url: str | None,
    ) -> None:
        self.urls = urls
        self.found = found
        self.missing_issue = missing_issue
        self.source_url = source_url


async def fetch_sitemap(
    base_url: str,
    client: httpx.AsyncClient,
    *,
    sitemap_url_override: str | None = None,
    robots_sitemap_urls: list[str] | None = None,
) -> SitemapResult:
    """Discover and parse the sitemap for the site at *base_url*.

    Discovery order (spec §3.1.7):
    1. ``sitemap_url_override`` if provided.
    2. ``/sitemap.xml`` on the base domain.
    3. ``Sitemap:`` URLs found in robots.txt (``robots_sitemap_urls``).

    If none succeed, returns a ``SitemapResult`` with ``found=False`` and a
    ``SITEMAP_MISSING`` info issue.
    """
    candidates: list[str] = []

    if sitemap_url_override:
        candidates.append(sitemap_url_override)
    else:
        parsed = urlparse(base_url)
        candidates.append(f"{parsed.scheme}://{parsed.netloc}{_STANDARD_SITEMAP_PATH}")
        if robots_sitemap_urls:
            candidates.extend(robots_sitemap_urls)

    for candidate in candidates:
        result = await _try_fetch_sitemap(candidate, client)
        if result is not None:
            return result

    logger.warning("sitemap_missing", extra={"base_url": base_url})
    return SitemapResult(
        urls=[],
        found=False,
        missing_issue={
            "code": "SITEMAP_MISSING",
            "severity": "info",
            "category": "sitemap",
            "message": "No sitemap found. A sitemap helps search engines discover all pages on your site.",
        },
        source_url=None,
    )


async def _try_fetch_sitemap(
    url: str, client: httpx.AsyncClient
) -> SitemapResult | None:
    """Attempt to fetch and parse a sitemap at *url*.

    Returns a populated :class:`SitemapResult` on success, or ``None`` if the
    URL is unreachable or returns a non-200 status.
    """
    try:
        response = await client.get(url, timeout=_FETCH_TIMEOUT, follow_redirects=True)
    except httpx.RequestError as exc:
        logger.debug(
            "sitemap_fetch_error", extra={"url": url, "error": str(exc)}
        )
        return None

    if response.status_code != 200:
        logger.debug(
            "sitemap_not_found",
            extra={"url": url, "status_code": response.status_code},
        )
        return None

    content = _decompress(response)
    urls = _parse_sitemap_content(content, url, client)

    if not urls and not _is_valid_sitemap_xml(content):
        return None

    logger.info(
        "sitemap_fetched",
        extra={"url": url, "url_count": len(urls)},
    )
    return SitemapResult(urls=urls, found=True, missing_issue=None, source_url=url)


def _decompress(response: httpx.Response) -> bytes:
    """Return the raw bytes of *response*, decompressing gzip if needed."""
    content_encoding = response.headers.get("content-encoding", "")
    raw = response.content

    if content_encoding == "gzip" or _is_gzip_bytes(raw):
        try:
            return gzip.decompress(raw)
        except Exception:
            pass  # Fall through — try parsing as-is

    return raw


def _is_gzip_bytes(data: bytes) -> bool:
    """Return True if *data* starts with the gzip magic bytes."""
    return len(data) >= 2 and data[0] == 0x1F and data[1] == 0x8B


def _is_valid_sitemap_xml(content: bytes) -> bool:
    """Return True if *content* looks like a sitemap XML document."""
    try:
        soup = BeautifulSoup(content, "lxml-xml")
        return bool(soup.find("urlset") or soup.find("sitemapindex"))
    except Exception:
        return False


def _parse_sitemap_content(
    content: bytes,
    source_url: str,
    client: httpx.AsyncClient,
) -> list[str]:
    """Parse sitemap XML *content* and return all ``<loc>`` page URLs.

    Handles both ``<urlset>`` (standard) and ``<sitemapindex>`` (index) documents.
    Child sitemaps within an index are fetched synchronously here — callers
    that need true async recursion should use :func:`fetch_sitemap` instead.

    Note: This function is intentionally synchronous for the parsing phase.
    Nested index fetching is done via a fresh async call chain in the async
    variant below.
    """
    soup = BeautifulSoup(content, "lxml-xml")

    if soup.find("sitemapindex"):
        # Index sitemap — collect child sitemap <loc> values.
        # Actual fetching of children is handled by the async caller.
        return [loc.get_text(strip=True) for loc in soup.find_all("loc")]

    # Standard urlset sitemap
    return [loc.get_text(strip=True) for loc in soup.find_all("loc")]


async def fetch_sitemap_recursive(
    base_url: str,
    client: httpx.AsyncClient,
    *,
    sitemap_url_override: str | None = None,
    robots_sitemap_urls: list[str] | None = None,
) -> SitemapResult:
    """Like :func:`fetch_sitemap` but fully resolves sitemap index files.

    When the root sitemap is a ``<sitemapindex>``, each child is fetched in
    turn and all ``<loc>`` URLs are aggregated.
    """
    candidates: list[str] = []

    if sitemap_url_override:
        candidates.append(sitemap_url_override)
    else:
        parsed = urlparse(base_url)
        candidates.append(f"{parsed.scheme}://{parsed.netloc}{_STANDARD_SITEMAP_PATH}")
        if robots_sitemap_urls:
            candidates.extend(robots_sitemap_urls)

    for candidate in candidates:
        result = await _fetch_and_resolve(candidate, client)
        if result is not None:
            return result

    logger.warning("sitemap_missing", extra={"base_url": base_url})
    return SitemapResult(
        urls=[],
        found=False,
        missing_issue={
            "code": "SITEMAP_MISSING",
            "severity": "info",
            "category": "sitemap",
            "message": "No sitemap found. A sitemap helps search engines discover all pages on your site.",
        },
        source_url=None,
    )


async def _fetch_and_resolve(
    url: str, client: httpx.AsyncClient
) -> SitemapResult | None:
    """Fetch *url*, resolve index files, and return aggregated URLs."""
    try:
        response = await client.get(url, timeout=_FETCH_TIMEOUT, follow_redirects=True)
    except httpx.RequestError as exc:
        logger.debug("sitemap_fetch_error", extra={"url": url, "error": str(exc)})
        return None

    if response.status_code != 200:
        return None

    content = _decompress(response)
    soup = BeautifulSoup(content, "lxml-xml")

    if soup.find("sitemapindex"):
        # Fetch each child sitemap and aggregate
        child_urls_raw = [loc.get_text(strip=True) for loc in soup.find_all("loc")]
        all_page_urls: list[str] = []
        for child_url in child_urls_raw:
            child_result = await _fetch_and_resolve(child_url, client)
            if child_result is not None:
                all_page_urls.extend(child_result.urls)
        if not all_page_urls and not child_urls_raw:
            return None
        return SitemapResult(
            urls=all_page_urls, found=True, missing_issue=None, source_url=url
        )

    page_urls = [loc.get_text(strip=True) for loc in soup.find_all("loc")]
    if not page_urls and not soup.find("urlset"):
        return None

    return SitemapResult(
        urls=page_urls, found=True, missing_issue=None, source_url=url
    )
