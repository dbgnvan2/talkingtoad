"""
Async HTTP page fetcher for the TalkingToad crawler.

Implements spec §2.4, §2.5, §2.9, and logging from §8.2.
"""

import asyncio
import ipaddress
import logging
import os
import socket
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

from api.crawler.normaliser import is_admin_path

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = float(os.getenv("CRAWL_REQUEST_TIMEOUT_S", "5"))
_RESCAN_TIMEOUT = float(os.getenv("RESCAN_TIMEOUT_S", "20"))

# Retry policy (audit 2026-07-03, R0.3): a single transient failure must not
# become a permanent negative (BROKEN_LINK_5XX / PAGE_TIMEOUT / EXTERNAL_LINK_
# TIMEOUT). We retry ONLY transient conditions — network errors/timeouts and
# 5xx responses — with exponential backoff. Deterministic outcomes (2xx, 3xx,
# 4xx, redirect loops, SSRF blocks) are never retried. Set CRAWL_MAX_RETRIES=0
# to disable.
_MAX_RETRIES = int(os.getenv("CRAWL_MAX_RETRIES", "1"))
_RETRY_BACKOFF_S = float(os.getenv("CRAWL_RETRY_BACKOFF_S", "0.5"))
_DEFAULT_USER_AGENT = os.getenv(
    "CRAWLER_USER_AGENT",
    "NonprofitCrawler/1.0 (+https://github.com/dbgnvan2/talkingtoad)",
)
_MAX_REDIRECTS = 10

# Path patterns that indicate a login redirect (spec §2.9)
_LOGIN_PATHS: frozenset[str] = frozenset(
    ["/login", "/logout", "/signin", "/signout", "/wp-login.php", "/user/login", "/user/logout"]
)


def _is_private_ip(ip_str: str) -> bool:
    """Return True if *ip_str* is a private, loopback, or link-local address."""
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved


def is_ssrf_safe(url: str) -> bool:
    """Return True if the URL's hostname does **not** resolve to a private IP.

    Used to block SSRF attacks where a user-supplied URL targets internal
    services (localhost, 169.254.x.x, 10.x.x.x, 192.168.x.x, etc.).
    """
    try:
        hostname = urlparse(url).hostname
        if not hostname:
            return False
        # Quick check for obvious private hostnames
        if hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
            return False
        # Resolve and check all addresses
        for family, _, _, _, sockaddr in socket.getaddrinfo(hostname, None):
            ip_str = sockaddr[0]
            if _is_private_ip(ip_str):
                return False
    except (socket.gaierror, OSError):
        # Can't resolve — allow (will fail at fetch time with a clear error)
        pass
    return True


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
        text: Decoded body for non-HTML text/* responses (e.g. text/plain llms.txt),
            or None. HTML bodies go to ``html``, not here.
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
    text: str | None = None          # decoded body for non-HTML text/* (e.g. text/plain llms.txt)
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

    # v2.3 (M0.6.10) SSRF pre-check on the initial URL itself.
    # Previously the check only ran after the response on the redirect chain,
    # which meant the initial request was already issued to the target (could
    # have side effects on internal services). Now we refuse to issue the
    # request at all if the initial URL resolves to a private address.
    # Defense-in-depth: callers (engine, sitemap, advisor, etc.) should also
    # gate their inputs, but this is the universal backstop for anything that
    # goes through fetch_page() — including the AMP HEAD check in engine.py:820
    # where attacker-controlled <link rel="amphtml"> could otherwise point at
    # 169.254.169.254 (AWS metadata).
    if not is_ssrf_safe(url):
        logger.warning("ssrf_initial_blocked", extra={"url": url})
        return FetchResult(
            url=url, final_url=url, status_code=0,
            error="SSRF_BLOCKED: URL resolves to a private/internal network",
        )

    # Retry loop (R0.3): only transient failures are retried — network
    # errors/timeouts (httpx.RequestError) and 5xx responses — with exponential
    # backoff. Deterministic outcomes (2xx/3xx/4xx, redirect loops, SSRF blocks)
    # return immediately and are never retried.
    for attempt in range(_MAX_RETRIES + 1):
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

                # SSRF protection on redirect chain: reject if any hop resolves to a private IP
                for hop_url in redirect_chain + [final_url]:
                    if not is_ssrf_safe(hop_url):
                        logger.warning("ssrf_redirect_blocked", extra={"url": url, "blocked_hop": hop_url})
                        return FetchResult(
                            url=url, final_url=hop_url, status_code=0,
                            error="SSRF_BLOCKED: redirect to private/internal network",
                        )

                is_login_redirect = _check_login_redirect(redirect_chain + [final_url])
                first_status = response.history[0].status_code if response.history else response.status_code
                content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()

                html: str | None = None
                text: str | None = None
                is_html = "html" in content_type
                is_pdf = "pdf" in content_type
                # Non-HTML text/* bodies (llms.txt, ai.txt, robots.txt) must be
                # decoded so structural checks in engine.py can read them.
                is_text = content_type.startswith("text/") and not is_html
                result_size = 0

                if not is_head and (is_html or is_pdf or is_text):
                    raw = await response.aread()
                    result_size = len(raw)
                    if len(raw) <= _MAX_HTML_BYTES:
                        if is_html:
                            html = raw.decode(response.encoding or "utf-8", errors="replace")
                        elif is_text:
                            text = raw.decode(response.encoding or "utf-8", errors="replace")
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
                    text=text,
                    content=result_content,
                    content_type=content_type,
                    redirect_chain=redirect_chain,
                    is_login_redirect=is_login_redirect,
                    response_size_bytes=result_size,
                )

        except httpx.TooManyRedirects:
            # Deterministic — never retry.
            logger.warning("redirect_loop_detected", extra={"url": url})
            return FetchResult(url=url, final_url=url, status_code=0, error="REDIRECT_LOOP")
        except httpx.RequestError as exc:
            # Transient network error / timeout — retry with backoff if attempts remain.
            if attempt < _MAX_RETRIES:
                logger.info("fetch_retry", extra={"url": url, "attempt": attempt + 1, "error": str(exc)})
                await asyncio.sleep(_RETRY_BACKOFF_S * (2 ** attempt))
                continue
            logger.warning("fetch_error", extra={"url": url, "error": str(exc)})
            return FetchResult(url=url, final_url=url, status_code=0, error=str(exc))

        # Got a response. Retry only transient 5xx responses.
        if 500 <= result.status_code <= 599 and attempt < _MAX_RETRIES:
            logger.info(
                "fetch_retry_5xx",
                extra={"url": url, "attempt": attempt + 1, "status": result.status_code},
            )
            await asyncio.sleep(_RETRY_BACKOFF_S * (2 ** attempt))
            continue

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
