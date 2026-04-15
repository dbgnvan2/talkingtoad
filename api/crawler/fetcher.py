"""
Async HTTP page fetcher for the TalkingToad crawler.

Implements spec §2.4, §2.5, §2.9, and logging from §8.2.
"""

import logging
import os
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

from api.crawler.normaliser import is_admin_path

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = float(os.getenv("CRAWL_REQUEST_TIMEOUT_S", "5"))
_RESCAN_TIMEOUT = float(os.getenv("RESCAN_TIMEOUT_S", "20"))
_DEFAULT_USER_AGENT = os.getenv(
    "CRAWLER_USER_AGENT",
    "NonprofitCrawler/1.0 (+https://github.com/dbgnvan2/talkingtoad)",
)
_MAX_REDIRECTS = 10

# Path patterns that indicate a login redirect (spec §2.9)
_LOGIN_PATHS: frozenset[str] = frozenset(
    ["/login", "/logout", "/signin", "/signout", "/wp-login.php", "/user/login", "/user/logout"]
)


@dataclass
class FetchResult:
    """Result of fetching a single URL.

    Attributes:
        url: The URL that was originally requested.
        final_url: The URL after following all redirects.
        status_code: HTTP status code of the final response (0 if request failed).
        first_status_code: HTTP status code of the first response in a redirect chain
            (same as status_code when there are no redirects).
        headers: Response headers from the final response.
        html: Response body text, or None if the response was not HTML or request failed.
        redirect_chain: Ordered list of intermediate URLs visited (not including final_url).
        is_login_redirect: True if a redirect in the chain pointed to a login path.
        error: Error message if the request failed, None on success.
    """

    url: str
    final_url: str
    status_code: int
    first_status_code: int = 0
    headers: dict[str, str] = field(default_factory=dict)
    html: str | None = None
    content: bytes | None = None     # raw response body for non-HTML (e.g. PDFs)
    content_type: str = ""           # normalised value from Content-Type header
    redirect_chain: list[str] = field(default_factory=list)
    is_login_redirect: bool = False
    response_size_bytes: int = 0
    error: str | None = None

    @property
    def is_redirect(self) -> bool:
        return bool(self.redirect_chain)

    @property
    def redirect_count(self) -> int:
        return len(self.redirect_chain)


_MAX_HTML_BYTES = 5 * 1024 * 1024  # 5 MB — refuse to parse larger HTML pages


async def fetch_page(
    url: str,
    client: httpx.AsyncClient,
    *,
    is_head: bool = False,
    timeout: float | None = None,
    bypass_cache: bool = False,
) -> FetchResult:
    """Fetch *url* and return a :class:`FetchResult`.

    Uses streaming so that non-HTML responses (PDFs, images, large binaries in
    /wp-content/uploads/ etc.) never block the crawler waiting for a full
    download.  Only HTML responses are read into memory, up to _MAX_HTML_BYTES.

    Follows redirects automatically (up to ``_MAX_REDIRECTS`` hops).
    Records the full redirect chain and detects login redirects.

    Args:
        url: The URL to fetch.
        client: A configured ``httpx.AsyncClient`` with appropriate headers.
        is_head: If True, issue a HEAD request (used for external link checking).
        bypass_cache: If True, send Cache-Control/Pragma no-cache headers so
            CDNs and server-side caches (Cloudflare, WP Rocket, etc.) return
            a fresh copy.  Used during rescan to see just-applied fixes.
    """
    method = "HEAD" if is_head else "GET"
    extra_headers: dict[str, str] = {}
    if bypass_cache:
        extra_headers["Cache-Control"] = "no-cache, no-store"
        extra_headers["Pragma"] = "no-cache"

    try:
        async with client.stream(
            method,
            url,
            timeout=timeout if timeout is not None else _DEFAULT_TIMEOUT,
            follow_redirects=True,
            headers=extra_headers,
        ) as response:
            redirect_chain = [str(r.url) for r in response.history]
            final_url = str(response.url)
            is_login_redirect = _check_login_redirect(redirect_chain + [final_url])
            first_status = response.history[0].status_code if response.history else response.status_code
            content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()

            html: str | None = None
            is_html = "html" in content_type
            is_pdf = "pdf" in content_type
            result_size = 0

            if not is_head and (is_html or is_pdf):
                raw = await response.aread()
                result_size = len(raw)
                if len(raw) <= _MAX_HTML_BYTES:
                    if is_html:
                        html = raw.decode(response.encoding or "utf-8", errors="replace")
                    result_content = raw if is_pdf else None
                else:
                    logger.warning(
                        "content_too_large",
                        extra={"url": url, "bytes": len(raw), "type": content_type},
                    )
                    result_content = None
            else:
                result_content = None
                try:
                    result_size = int(response.headers.get("content-length", 0))
                except (ValueError, TypeError):
                    result_size = 0

            result = FetchResult(
                url=url,
                final_url=final_url,
                status_code=response.status_code,
                first_status_code=first_status,
                headers=dict(response.headers),
                html=html,
                content=result_content,
                content_type=content_type,
                redirect_chain=redirect_chain,
                is_login_redirect=is_login_redirect,
                response_size_bytes=result_size,
            )

    except httpx.TooManyRedirects:
        logger.warning("redirect_loop_detected", extra={"url": url})
        return FetchResult(url=url, final_url=url, status_code=0, error="REDIRECT_LOOP")
    except httpx.RequestError as exc:
        logger.warning("fetch_error", extra={"url": url, "error": str(exc)})
        return FetchResult(url=url, final_url=url, status_code=0, error=str(exc))

    logger.debug(
        "page_fetched",
        extra={
            "url": url,
            "final_url": final_url,
            "status_code": result.status_code,
            "redirect_count": result.redirect_count,
            "is_login_redirect": is_login_redirect,
        },
    )

    return result


def make_client(user_agent: str | None = None) -> httpx.AsyncClient:
    """Return a configured ``httpx.AsyncClient`` for crawling."""
    return httpx.AsyncClient(
        headers={"User-Agent": user_agent or _DEFAULT_USER_AGENT},
        follow_redirects=True,
        max_redirects=_MAX_REDIRECTS,
    )


def _check_login_redirect(urls: list[str]) -> bool:
    """Return True if any URL in *urls* is a login-type path."""
    for url in urls:
        path = urlparse(url).path
        if path in _LOGIN_PATHS:
            return True
    return False
