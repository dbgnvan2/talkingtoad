"""
WordPress REST API client with cookie-based authentication.

Authenticates via the WordPress login form (supports custom login URLs such as
those created by WPS Hide Login or similar plugins), then uses the session
cookie + REST API nonce for authenticated REST API calls.

Used by the v2.0 WordPress Automation Engine.
"""

import json
import logging
import re
import time
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_CREDENTIALS_PATH = Path("wp-credentials.json")

# ---------------------------------------------------------------------------
# In-process session cache — avoids re-authenticating on every API call.
# Keyed by (login_url, username). WP nonces expire after 12 h by default;
# we cache for 10 h to stay comfortably inside that window.
# ---------------------------------------------------------------------------
_SESSION_CACHE: dict[tuple[str, str], dict] = {}
_CACHE_TTL = 10 * 3600  # seconds


def _cache_key(login_url: str, username: str) -> tuple[str, str]:
    return (login_url, username)


def invalidate_session(login_url: str, username: str) -> None:
    """Remove a cached session so the next request triggers a fresh login."""
    _SESSION_CACHE.pop(_cache_key(login_url, username), None)


class WPAuthError(Exception):
    """Raised when authentication with WordPress fails."""


class WPClient:
    """Async WordPress REST API client using cookie-based authentication.

    Usage::

        async with WPClient.from_credentials_file() as wp:
            response = await wp.get("users/me")
            print(response.json())
    """

    def __init__(
        self,
        site_url: str,
        login_url: str,
        username: str,
        password: str,
    ) -> None:
        self.site_url = site_url.rstrip("/")
        self.login_url = login_url
        self.username = username
        self.password = password
        self._client: httpx.AsyncClient | None = None
        self._nonce: str | None = None

    @classmethod
    def from_credentials_file(cls, path: Path | None = None) -> "WPClient":
        """Load credentials from *wp-credentials.json* and return a :class:`WPClient`.

        Args:
            path: Override the default credentials file path.

        Raises:
            WPAuthError: If the file is missing, invalid JSON, or missing required fields.
        """
        creds_path = path or _CREDENTIALS_PATH
        try:
            with open(creds_path) as f:
                creds = json.load(f)
        except FileNotFoundError:
            raise WPAuthError(f"Credentials file not found: {creds_path}")
        except json.JSONDecodeError as exc:
            raise WPAuthError(f"Invalid JSON in credentials file: {exc}")

        required = ("site_url", "login_url", "username", "password")
        missing = [k for k in required if not creds.get(k)]
        if missing:
            raise WPAuthError(
                f"Missing fields in wp-credentials.json: {', '.join(missing)}"
            )

        return cls(
            site_url=creds["site_url"],
            login_url=creds["login_url"],
            username=creds["username"],
            password=creds["password"],
        )

    async def __aenter__(self) -> "WPClient":
        self._client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=15.0,
            headers={
                "User-Agent": "TalkingToad/1.0 (+https://github.com/dbgnvan2/talkingtoad)"
            },
        )
        await self.login()
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def login(self) -> None:
        """Authenticate via the WordPress login form and retrieve a REST nonce.

        Checks the in-process session cache first; only performs the full
        login flow (3 HTTP requests) when the cache is empty or expired.

        Raises:
            WPAuthError: If login fails or the nonce cannot be retrieved.
        """
        client = self._client
        assert client is not None, "login() must be called within async context manager"

        key = _cache_key(self.login_url, self.username)
        cached = _SESSION_CACHE.get(key)
        if cached and (time.monotonic() - cached["cached_at"]) < _CACHE_TTL:
            # Restore cookies and nonce — no login round-trips needed
            for name, value in cached["cookies"].items():
                client.cookies.set(name, value)
            self._nonce = cached["nonce"]
            logger.info("wp_session_cache_hit", extra={"site_url": self.site_url})
            return

        # ── Full login flow ────────────────────────────────────────────────

        # Step 1: GET login page to prime the WordPress test cookie
        await client.get(self.login_url)
        client.cookies.set("wordpress_test_cookie", "WP Cookie check")

        # Step 2: POST credentials to the login form
        await client.post(
            self.login_url,
            data={
                "log": self.username,
                "pwd": self.password,
                "wp-submit": "Log In",
                "redirect_to": f"{self.site_url}/wp-admin/",
                "testcookie": "1",
            },
        )

        # Verify we received a logged-in session cookie
        cookie_names = [c.name for c in client.cookies.jar]
        if not any("wordpress_logged_in" in name for name in cookie_names):
            raise WPAuthError(
                "Login failed — no wordpress_logged_in cookie received. "
                "Check username and password in wp-credentials.json."
            )

        logger.info("wp_login_success", extra={"site_url": self.site_url})

        # Step 3: Extract the REST API nonce from the WP admin page
        self._nonce = await self._fetch_nonce()
        if not self._nonce:
            raise WPAuthError(
                "Login succeeded but could not retrieve REST API nonce from wp-admin. "
                "The account may not have sufficient permissions."
            )

        logger.info("wp_nonce_retrieved", extra={"site_url": self.site_url})

        # Save session to cache so subsequent requests skip the login flow
        cookies_dict = {c.name: c.value for c in client.cookies.jar}
        _SESSION_CACHE[key] = {
            "cookies": cookies_dict,
            "nonce": self._nonce,
            "cached_at": time.monotonic(),
        }
        logger.info("wp_session_cached", extra={"site_url": self.site_url})

    async def _fetch_nonce(self) -> str | None:
        """Return the WP REST API nonce by parsing the wp-admin page inline script.

        Tries three increasingly broad patterns to locate the nonce that
        ``wp.apiFetch`` uses for REST API requests.
        """
        assert self._client is not None
        response = await self._client.get(f"{self.site_url}/wp-admin/")
        text = response.text

        # Most specific: the nonce passed to wp.apiFetch.createNonceMiddleware()
        m = re.search(
            r'wp\.apiFetch\.createNonceMiddleware\(\s*["\']([a-f0-9]+)["\']',
            text,
        )
        if m:
            return m.group(1)

        # Fallback: nonce inside wpApiSettings object (near versionString)
        m = re.search(
            r'"nonce"\s*:\s*"([a-f0-9]+)"\s*,\s*"versionString"',
            text,
        )
        if m:
            return m.group(1)

        # Broad fallback: X-WP-Nonce value in inline script
        m = re.search(r"['\"]X-WP-Nonce['\"]\s*:\s*['\"]([a-f0-9]+)['\"]", text)
        return m.group(1) if m else None

    @property
    def _auth_headers(self) -> dict[str, str]:
        """Return headers required for authenticated REST API requests."""
        if self._nonce:
            return {"X-WP-Nonce": self._nonce}
        return {}

    # -------------------------------------------------------------------------
    # REST API methods
    # -------------------------------------------------------------------------

    def _check_auth(self, response: httpx.Response) -> None:
        """Invalidate the session cache if WP rejected our credentials."""
        if response.status_code in (401, 403):
            invalidate_session(self.login_url, self.username)
            logger.warning(
                "wp_session_invalidated",
                extra={"site_url": self.site_url, "status": response.status_code},
            )

    async def get(self, endpoint: str, **kwargs: object) -> httpx.Response:
        """Authenticated GET to ``/wp-json/wp/v2/{endpoint}``."""
        assert self._client is not None
        r = await self._client.get(
            f"{self.site_url}/wp-json/wp/v2/{endpoint}",
            headers=self._auth_headers,
            **kwargs,
        )
        self._check_auth(r)
        return r

    async def post(self, endpoint: str, **kwargs: object) -> httpx.Response:
        """Authenticated POST to ``/wp-json/wp/v2/{endpoint}``."""
        assert self._client is not None
        r = await self._client.post(
            f"{self.site_url}/wp-json/wp/v2/{endpoint}",
            headers=self._auth_headers,
            **kwargs,
        )
        self._check_auth(r)
        return r

    async def patch(self, endpoint: str, **kwargs: object) -> httpx.Response:
        """Authenticated PATCH to ``/wp-json/wp/v2/{endpoint}``."""
        assert self._client is not None
        r = await self._client.patch(
            f"{self.site_url}/wp-json/wp/v2/{endpoint}",
            headers=self._auth_headers,
            **kwargs,
        )
        self._check_auth(r)
        return r
