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


# WA1 (2026-09-02) — `get`/`post`/`patch`/`delete` join `{site_url}/wp-json/wp/v2/`
# to the endpoint, so an endpoint that already carries the namespace produces
# `/wp-json/wp/v2//wp/v2/plugins`, a 404 on every WordPress install. Four call
# sites in `wp_audit.py` did exactly that and the audit never worked. Writing a
# REST route with its namespace is the natural thing to do, so the client
# accepts either spelling rather than leaving the trap armed for the next caller.
# Spec:  docs/functional-specification.md §7.8 (WA1)
# Tests: tests/test_wp_client_routes.py::TestBothSpellingsAgree
_WP_V2_PREFIX = "wp/v2/"


def _wp_v2_endpoint(endpoint: str) -> str:
    """Return *endpoint* relative to the ``wp/v2`` namespace, however it was written."""
    e = endpoint.lstrip("/")
    if e.startswith(_WP_V2_PREFIX):
        e = e[len(_WP_V2_PREFIX):]
    return e


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
        response = await client.post(
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
            raise WPAuthError(self._login_failure_message(response))

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

    def _login_failure_message(self, response: httpx.Response) -> str:
        """Say what was observed, and name the causes this cannot tell apart.

        WA4 (2026-09-02). The message used to be "Login failed — no
        wordpress_logged_in cookie received. Check username and password in
        wp-credentials.json." for every failure. On livingsystems.ca the
        password was correct: the site had moved its login page, and the stored
        pretty URL 302s to ``wp-login.php?sgs-token=...``. httpx replays a 302
        on a POST as a GET, so the credentials were dropped in flight and never
        reached WordPress. The message sent the reader to the one thing that was
        not wrong (P14), and cost a diagnostic round.

        Tests: tests/test_wp_client_routes.py::TestTheLoginErrorNamesWhatItSaw
        """
        parts = [f"Login failed at {self.login_url} — WordPress did not set a "
                 f"wordpress_logged_in cookie."]

        if response.history:
            # The POST was redirected. A 302 on a POST is replayed as a GET, so
            # the credentials were never submitted — this is a URL fault, not a
            # credential one, and it is invisible from the status code alone.
            parts.append(
                f"The request was redirected to {response.url} and arrived as a GET, "
                f"so the credentials were not submitted. Point login_url at the "
                f"final address (the one the browser lands on), not the one that "
                f"redirects."
            )

        # Take the WHOLE element, not up to the first closing tag. WordPress 6.x
        # renders `<div id="login_error" ...><p><strong>Error:</strong> The
        # password you entered ... is incorrect.</p></div>`, so a lazy `(.*?)</`
        # yielded "Error:" and dropped the reason — the only thing this clause
        # exists to surface. Balanced-tag matching is not a job for a regex, so
        # take everything to the closing </div> and strip the markup.
        m = re.search(r'id=["\']login_error["\'][^>]*>(.*?)</div>', response.text or "",
                      re.S | re.I)
        if m:
            detail = " ".join(re.sub(r"<[^>]+>", " ", m.group(1)).split())
            # WordPress prefixes "Error:" as a label; the sentence after it is
            # the content. Drop a bare leading label so the quote reads.
            detail = re.sub(r"^(error|warning)\s*:\s*", "", detail, flags=re.I).strip()
            if detail:
                parts.append(f'WordPress said: "{detail[:200]}"')

        parts.append(
            "Causes this check cannot tell apart: a wrong password, a wrong login URL, "
            "a login URL that redirects, or two-factor/CAPTCHA protection on the login "
            "form (which this client cannot complete)."
        )
        return " ".join(parts)

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

    async def get(self, endpoint: str, *, expect_denial: bool = False,
                  **kwargs: object) -> httpx.Response:
        """Authenticated GET to ``/wp-json/wp/v2/{endpoint}``.

        ``expect_denial`` suppresses the session-invalidation side effect for a
        call whose 403 is a normal answer rather than a rejected credential. The
        capability probe asks a question an editor is SUPPOSED to be refused;
        without this every editor connection test logged `wp_session_invalidated`
        at WARNING, implying the credentials had failed, and threw away the
        session it had just established so the next WP fix had to log in again.
        """
        assert self._client is not None
        r = await self._client.get(
            f"{self.site_url}/wp-json/wp/v2/{_wp_v2_endpoint(endpoint)}",
            headers=self._auth_headers,
            **kwargs,
        )
        if not expect_denial:
            self._check_auth(r)
        return r

    async def get_route(self, route: str, **kwargs: object) -> httpx.Response:
        """Authenticated GET to ``/wp-json/{route}`` — a route in ANY namespace.

        WA2 (2026-09-02). :meth:`get` hard-codes ``wp/v2``, so Site Health
        (``wp-site-health/v1/tests/background-updates``) was unreachable by any
        endpoint string — a structural fault, not a typo. It sat behind a bare
        ``except Exception`` in the audit, so the missing section read as
        "checked, nothing to report".

        Tests: tests/test_wp_client_routes.py::TestANamespaceThatIsNotWpV2
        """
        assert self._client is not None
        # httpx normalises dot segments, so `../wp-admin/admin-ajax.php` would
        # leave /wp-json/ entirely and arrive at wp-admin carrying the session
        # cookie and the nonce. No caller passes anything but a literal today;
        # this closes the class before one does.
        if ".." in route.split("?")[0].split("/"):
            raise ValueError(f"route must stay under /wp-json/: {route!r}")
        r = await self._client.get(
            f"{self.site_url}/wp-json/{route.lstrip('/')}",
            headers=self._auth_headers,
            **kwargs,
        )
        self._check_auth(r)
        return r

    async def post(self, endpoint: str, **kwargs: object) -> httpx.Response:
        """Authenticated POST to ``/wp-json/wp/v2/{endpoint}``."""
        assert self._client is not None
        r = await self._client.post(
            f"{self.site_url}/wp-json/wp/v2/{_wp_v2_endpoint(endpoint)}",
            headers=self._auth_headers,
            **kwargs,
        )
        self._check_auth(r)
        return r

    async def patch(self, endpoint: str, **kwargs: object) -> httpx.Response:
        """Authenticated PATCH to ``/wp-json/wp/v2/{endpoint}``."""
        assert self._client is not None
        r = await self._client.patch(
            f"{self.site_url}/wp-json/wp/v2/{_wp_v2_endpoint(endpoint)}",
            headers=self._auth_headers,
            **kwargs,
        )
        self._check_auth(r)
        return r

    async def delete(self, endpoint: str, **kwargs: object) -> httpx.Response:
        """Authenticated DELETE to ``/wp-json/wp/v2/{endpoint}``."""
        assert self._client is not None
        r = await self._client.delete(
            f"{self.site_url}/wp-json/wp/v2/{_wp_v2_endpoint(endpoint)}",
            headers=self._auth_headers,
            **kwargs,
        )
        self._check_auth(r)
        return r

    async def list_media(self, per_page: int = 100, max_pages: int = 20) -> list[dict]:
        """Fetch all media items from the WordPress Media Library.

        Paginates through results up to *max_pages* pages of *per_page* items.
        Returns the raw WP REST API media objects.
        """
        all_items: list[dict] = []
        for page in range(1, max_pages + 1):
            r = await self.get(
                f"media?per_page={per_page}&page={page}"
                f"&_fields=id,source_url,title,alt_text,mime_type,date,post,media_details"
            )
            if r.status_code != 200:
                break
            items = r.json()
            if not items:
                break
            all_items.extend(items)
            # Check if we've reached the last page
            total_pages = int(r.headers.get("x-wp-totalpages", "1"))
            if page >= total_pages:
                break
        return all_items

    async def delete_media(self, media_id: int, force: bool = True) -> bool:
        """Delete a media item from WordPress.

        Args:
            media_id: The ID of the media item to delete.
            force: Whether to bypass the trash and delete permanently.
        """
        r = await self.delete(f"media/{media_id}?force={'true' if force else 'false'}")
        return r.status_code == 200

    async def upload_media(
        self,
        file_path: str | Path,
        title: str | None = None,
        alt_text: str | None = None,
    ) -> dict | None:
        """Upload a file to the WordPress Media Library.

        Returns the created media attachment object as a dict, or None on failure.
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        from mimetypes import guess_type
        mime_type, _ = guess_type(file_path.name)
        if not mime_type:
            mime_type = "application/octet-stream"

        headers = self._auth_headers.copy()
        headers["Content-Disposition"] = f'attachment; filename="{file_path.name}"'
        headers["Content-Type"] = mime_type

        assert self._client is not None
        with open(file_path, "rb") as f:
            r = await self._client.post(
                f"{self.site_url}/wp-json/wp/v2/media",
                content=f.read(),
                headers=headers,
            )

        if r.status_code != 201:
            logger.error(
                "wp_upload_failed",
                extra={"file": file_path.name, "status": r.status_code, "error": r.text},
            )
            return None

        data = r.json()
        attachment_id = data.get("id")

        # Update metadata if provided
        if attachment_id and (title or alt_text):
            payload = {}
            if title:
                payload["title"] = title
            if alt_text:
                payload["alt_text"] = alt_text
            
            if payload:
                await self.patch(f"media/{attachment_id}", json=payload)

        return data

    async def update_media_metadata(
        self,
        media_id: int,
        alt_text: str | None = None,
        title: str | None = None,
        caption: str | None = None,
        description: str | None = None,
    ) -> dict | None:
        """Update metadata for an existing media item.

        Args:
            media_id: The ID of the media item to update.
            alt_text: New alt text (for accessibility).
            title: New title.
            caption: New caption (displayed below image).
            description: New description (long-form text).

        Returns:
            Updated media object as dict, or None on failure.
        """
        payload = {}
        if alt_text is not None:
            payload["alt_text"] = alt_text
        if title is not None:
            payload["title"] = title
        if caption is not None:
            payload["caption"] = caption
        if description is not None:
            payload["description"] = description

        if not payload:
            return None

        try:
            r = await self.patch(f"media/{media_id}", json=payload)
            if r.status_code == 200:
                return r.json()
            else:
                logger.error(
                    "wp_update_media_failed",
                    extra={"media_id": media_id, "status": r.status_code, "error": r.text},
                )
                return None
        except Exception as exc:
            logger.error("wp_update_media_error", extra={"media_id": media_id, "error": str(exc)})
            return None
