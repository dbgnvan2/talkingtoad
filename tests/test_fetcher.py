"""
SSRF protection tests for api/crawler/fetcher.py (v2.3 / M0.6.2).

v1.9.3 introduced is_ssrf_safe() and the redirect-chain SSRF guard in fetch_page,
but never shipped adversarial tests for either. This file fills that gap.

Per CLAUDE.md self-review protocol: "what does a correct-looking but wrong
result look like?" The most dangerous SSRF bypasses are:
  - Hostname resolves to a private IP via DNS (looks like a public domain)
  - IPv6 mapped addresses (::ffff:127.0.0.1)
  - Mixed case ("LocalHost", "LOCALHOST")
  - Redirect chain hops to private IPs
  - The reserved/link-local ranges most people forget (169.254.x.x, 100.64.x.x carrier-grade NAT, fc00::/7 IPv6 unique-local)

Each test is named so a future regression names itself in the test output.
"""

from __future__ import annotations

import socket
from unittest.mock import patch

import pytest

from api.crawler.fetcher import _is_private_ip, is_ssrf_safe


# ---------------------------------------------------------------------------
# Pure IP-classification tests (_is_private_ip)
# ---------------------------------------------------------------------------


class TestIsPrivateIp:
    """Pure-function tests against the IP classifier."""

    @pytest.mark.parametrize(
        "ip",
        [
            # IPv4 RFC1918
            "10.0.0.1",
            "10.255.255.255",
            "172.16.0.1",
            "172.31.255.255",
            "192.168.0.1",
            "192.168.255.255",
            # IPv4 loopback
            "127.0.0.1",
            "127.255.255.255",
            # IPv4 link-local (AWS metadata endpoint sits here)
            "169.254.169.254",
            "169.254.0.1",
            # IPv4 0.0.0.0 (binds to all interfaces; should be blocked)
            "0.0.0.0",
            # IPv6 loopback
            "::1",
            # IPv6 link-local
            "fe80::1",
            # IPv6 unique-local
            "fc00::1",
            "fd00::1",
            # IPv6 mapped IPv4 loopback (the canonical SSRF bypass)
            "::ffff:127.0.0.1",
            "::ffff:10.0.0.1",
        ],
    )
    def test_classifies_as_private(self, ip):
        assert _is_private_ip(ip) is True, f"{ip} must be classified as private"

    @pytest.mark.parametrize(
        "ip",
        [
            "1.1.1.1",
            "8.8.8.8",
            "93.184.216.34",  # example.com
            "2606:4700:4700::1111",  # Cloudflare DNS IPv6
            "2001:4860:4860::8888",  # Google DNS IPv6
        ],
    )
    def test_classifies_as_public(self, ip):
        assert _is_private_ip(ip) is False, f"{ip} must be classified as public"

    def test_malformed_input_returns_false(self):
        """Bad input must not crash; returns False (then upstream decides)."""
        assert _is_private_ip("not-an-ip") is False
        assert _is_private_ip("") is False
        assert _is_private_ip("999.999.999.999") is False


# ---------------------------------------------------------------------------
# URL-level SSRF check (is_ssrf_safe)
# ---------------------------------------------------------------------------


class TestIsSsrfSafeHostnameLiterals:
    """is_ssrf_safe rejects obvious private hostname literals without DNS lookup."""

    @pytest.mark.parametrize(
        "url",
        [
            "http://localhost/",
            "http://localhost:6379/",
            "https://localhost:8080/",
            "http://127.0.0.1/",
            "http://127.0.0.1:5432/admin",
            "http://0.0.0.0/",
            "http://[::1]/",
        ],
    )
    def test_rejects_obvious_private_literals(self, url):
        assert is_ssrf_safe(url) is False, f"{url} must be rejected as SSRF target"

    @pytest.mark.parametrize(
        "url",
        [
            # Adversarial: case variations of localhost
            "http://LocalHost/",
            "http://LOCALHOST:8080/",
            "http://localhost./",  # trailing dot — DNS-equivalent but might bypass naive string check
        ],
    )
    def test_case_variations_of_localhost(self, url):
        """Adversarial: 'LocalHost' or 'LOCALHOST' must be rejected just like 'localhost'.

        Current implementation does an exact lowercase compare against 'localhost' etc.
        urlparse().hostname returns the lowercased hostname, so 'LocalHost' becomes
        'localhost' and matches. Trailing-dot 'localhost.' is a DNS-equivalent form
        — if it resolves at all, getaddrinfo returns the loopback address and the
        DNS-resolution path of is_ssrf_safe will catch it.
        """
        # We assert based on what's safe — if a future change loosens the check,
        # this test catches it.
        result = is_ssrf_safe(url)
        # The trailing-dot case is allowed to pass the literal check but must
        # fail via DNS resolution; assert end-to-end safety either way.
        assert result is False, (
            f"{url} must be rejected — either via literal match or DNS resolution"
        )


class TestIsSsrfSafePrivateIpsViaDns:
    """is_ssrf_safe rejects hostnames that resolve to private IPs.

    The DNS-rebinding scenario: a public-looking hostname like 'evil.example.com'
    resolves to 169.254.169.254 (AWS metadata) or 10.0.0.1 (internal service).
    """

    @pytest.mark.parametrize(
        "private_addr",
        [
            "127.0.0.1",
            "169.254.169.254",  # AWS metadata
            "10.0.0.1",
            "172.16.0.1",
            "192.168.1.1",
        ],
    )
    def test_rejects_hostname_resolving_to_private_ip(self, private_addr):
        """A real-looking hostname that resolves to a private IP must be rejected."""
        # getaddrinfo returns: list of (family, socktype, proto, canonname, sockaddr)
        # where sockaddr is (ip_str, port) for IPv4 or (ip_str, port, flow, scope) for IPv6
        fake_resolution = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (private_addr, 0))
        ]
        with patch("api.crawler.fetcher.socket.getaddrinfo", return_value=fake_resolution):
            assert is_ssrf_safe("http://evil-rebound.example.com/") is False

    def test_rejects_when_any_resolution_is_private(self):
        """If a hostname returns MULTIPLE addresses and ANY is private, reject.

        Adversarial: a hostname returns [public_ip, private_ip]. If the SSRF check
        iterates and returns False on the first private address it sees, this passes.
        If it short-circuits on the first public address, this fails.
        """
        fake_resolution = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 0)),
        ]
        with patch("api.crawler.fetcher.socket.getaddrinfo", return_value=fake_resolution):
            assert is_ssrf_safe("http://multi-result.example.com/") is False

    def test_rejects_ipv6_mapped_ipv4_private(self):
        """IPv6 mapped to private IPv4 (::ffff:127.0.0.1) must be rejected.

        Without this, an attacker can bypass IPv4-only checks by using the v6 form.
        """
        fake_resolution = [
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("::ffff:127.0.0.1", 0, 0, 0))
        ]
        with patch("api.crawler.fetcher.socket.getaddrinfo", return_value=fake_resolution):
            assert is_ssrf_safe("http://v6mapped.example.com/") is False


class TestIsSsrfSafePublicAllowed:
    """is_ssrf_safe allows legitimate public hostnames."""

    def test_allows_public_resolution(self):
        fake_resolution = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0)),
        ]
        with patch("api.crawler.fetcher.socket.getaddrinfo", return_value=fake_resolution):
            assert is_ssrf_safe("https://example.com/") is True

    def test_allows_when_dns_fails(self):
        """If DNS resolution fails, allow — the fetch will fail with a clear error
        and the SSRF check is not the right gate for unreachable hostnames.

        This is current behaviour (documented in is_ssrf_safe). The test pins it
        so a future change doesn't silently flip to fail-closed without thought.
        """
        with patch("api.crawler.fetcher.socket.getaddrinfo", side_effect=socket.gaierror):
            assert is_ssrf_safe("https://does-not-exist.example.invalid/") is True


class TestIsSsrfSafeMalformedUrls:
    """Malformed URLs are rejected as unsafe (defensive default)."""

    @pytest.mark.parametrize(
        "url",
        [
            "",
            "not-a-url",
            "http://",
            "file:///etc/passwd",  # No hostname
        ],
    )
    def test_no_hostname_rejected(self, url):
        """URLs with no extractable hostname must be rejected."""
        assert is_ssrf_safe(url) is False, f"{url} must be rejected (no hostname)"


# ---------------------------------------------------------------------------
# fetch_page() pre-check (M0.6.10)
# ---------------------------------------------------------------------------


class TestFetchPagePreCheck:
    """fetch_page() must reject private-IP URLs BEFORE issuing the request.

    Pre-v2.3 the check ran only on the redirect chain post-response, meaning
    the initial request was still made to the target. For HEAD requests
    (like the AMP HEAD check in engine.py:820), that's enough to trigger
    side effects on internal services with auth-cookie-equivalents.
    """

    @pytest.mark.asyncio
    async def test_fetch_page_rejects_localhost_before_request(self):
        """Calling fetch_page on http://localhost/ returns SSRF_BLOCKED without making the request."""
        import httpx
        from api.crawler.fetcher import fetch_page

        # Use a mocked transport that would raise if any request actually fired.
        def _explode(request: httpx.Request) -> httpx.Response:
            raise AssertionError(
                f"fetch_page must not issue the request when SSRF guard rejects "
                f"the initial URL. Request was: {request.method} {request.url}"
            )

        transport = httpx.MockTransport(_explode)
        async with httpx.AsyncClient(transport=transport) as client:
            result = await fetch_page("http://localhost:6379/", client)

        assert result.status_code == 0
        assert result.error is not None
        assert "SSRF_BLOCKED" in result.error

    @pytest.mark.asyncio
    async def test_fetch_page_rejects_aws_metadata_endpoint(self):
        """The canonical SSRF target: AWS instance metadata at 169.254.169.254."""
        import httpx
        from api.crawler.fetcher import fetch_page

        def _explode(request: httpx.Request) -> httpx.Response:
            raise AssertionError(f"Request should not fire: {request.url}")

        transport = httpx.MockTransport(_explode)
        async with httpx.AsyncClient(transport=transport) as client:
            result = await fetch_page(
                "http://169.254.169.254/latest/meta-data/iam/security-credentials/",
                client,
            )

        assert result.status_code == 0
        assert "SSRF_BLOCKED" in (result.error or "")

    @pytest.mark.asyncio
    async def test_fetch_page_head_request_rejected(self):
        """AMP HEAD check in engine.py:820 must be blocked when amphtml points internally.

        Attacker scenario: a malicious site declares
        <link rel="amphtml" href="http://169.254.169.254/...">. The crawler's
        AMP HEAD check goes through _check_external_link -> fetch_page.
        With is_head=True the pre-check must still fire.
        """
        import httpx
        from api.crawler.fetcher import fetch_page

        def _explode(request: httpx.Request) -> httpx.Response:
            raise AssertionError(f"HEAD must not fire: {request.url}")

        transport = httpx.MockTransport(_explode)
        async with httpx.AsyncClient(transport=transport) as client:
            result = await fetch_page(
                "http://169.254.169.254/", client, is_head=True
            )

        assert result.status_code == 0
        assert "SSRF_BLOCKED" in (result.error or "")

    @pytest.mark.asyncio
    async def test_fetch_page_allows_public_url(self):
        """Confirm pre-check doesn't false-positive on legitimate public URLs."""
        import httpx
        from api.crawler.fetcher import fetch_page

        def _ok(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                headers={"Content-Type": "text/html"},
                content=b"<html><body>hi</body></html>",
            )

        # Patch resolution so example.com resolves to a public IP for the test
        fake_resolution = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0)),
        ]
        transport = httpx.MockTransport(_ok)
        with patch("api.crawler.fetcher.socket.getaddrinfo", return_value=fake_resolution):
            async with httpx.AsyncClient(transport=transport) as client:
                result = await fetch_page("https://example.com/", client)

        assert result.status_code == 200
        assert result.error is None
