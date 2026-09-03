"""WA5 — GET /api/wp/connection: does WordPress actually answer us?

Spec:  docs/functional-specification.md §7.8a (WA5)
Tests: tests/test_wp_connection_endpoint.py

The Connections panel tested the AI provider and Google Search Console. Nothing
tested WordPress, so the first sign of a stale credential was a failed fix or a
502 from the audit. On 2026-09-02 livingsystems.ca moved its login page and
every WordPress feature broke at once, with nothing in the app able to say why.

Read-only by construction: the single call is `users/me`. It answers 200 with a
state rather than an HTTP error, because "not configured", "credentials
rejected" and "logged in but under-privileged" are three different problems with
three different fixes, and a panel needs to render them differently — collapsing
them into one red box would rebuild the guessing error WA4 exists to remove.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from api.routers.fixes_shared import (
    _CREDS_PATH,
    _validate_wp_domain_for_job,
    get_store,
)
from api.services.auth import require_auth
from api.services.rate_limiter import WP_CONNECTION_LIMIT, limiter
from api.services.wp_client import WPAuthError, WPClient, invalidate_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/wp", tags=["wp"],
                   dependencies=[Depends(require_auth)])

# The capabilities the app's own flows need. `manage_options` is separated out
# because `/wp/v2/plugins` requires an administrator: an editor authenticates
# perfectly well, can run every title/heading/image fix, and still cannot run
# the configuration audit. Reporting one green tick for both would send the
# operator to a button that 403s.
_FIX_CAPS = ("edit_posts", "edit_pages", "upload_files")
# `WP_REST_Plugins_Controller::get_items_permissions_check` gates on
# `activate_plugins`, NOT `manage_options`. Checking the wrong one reproduces the
# exact failure this split exists to prevent: a green tick, then a 403 from the
# button it just promised. `manage_options` is kept as a fallback for installs
# that do not report `activate_plugins` in `allcaps`.
_AUDIT_CAPS = ("activate_plugins", "manage_options")


def _redact(text: str, secret: str | None) -> str:
    """Never forward a message containing the stored password.

    The client's own failure message does not include it, but this endpoint
    passes that message verbatim to a browser, and a future client change — or a
    WordPress error echoing a submitted value — would leak it with no other
    guard in the path.
    """
    if secret and len(secret) >= 4 and secret in text:
        return text.replace(secret, "[redacted]")
    return text


def _state(**kw) -> dict:
    base = {
        "configured": False,
        "authenticated": False,
        "site_url": None,
        "user_id": None,
        "roles": [],
        "capabilities": {},
        "can_run_fixes": False,
        "can_run_wp_audit": False,
        "message": "",
    }
    base.update(kw)
    return base


@router.get("/connection", response_model=None)
@limiter.limit(WP_CONNECTION_LIMIT)
async def wp_connection(
    request: Request,
    job_id: str | None = Query(
        None, description="Optional crawl job to domain-validate against."),
    store=Depends(get_store),
) -> dict | JSONResponse:
    """Report whether the stored WordPress credentials still work.

    With no ``job_id`` there is nothing to domain-validate: the endpoint takes
    no address and can only ever contact the site named in the credentials file.
    When a caller names a job, the job's domain must match the credentials —
    otherwise this becomes a way to confirm credentials while looking at
    somebody else's crawl (CLAUDE.md, WordPress Safety).
    """
    if job_id:
        domain_err = await _validate_wp_domain_for_job(store, job_id)
        if domain_err is not None:
            return domain_err

    if not _CREDS_PATH.exists():
        return _state(message=(
            "No WordPress credentials are stored. Add wp-credentials.json with "
            "site_url, login_url, username and a password to enable the fix "
            "flows and the configuration audit."))

    # Read the identifiers from the FILE, not off the client: the operator needs
    # to see which site was tried even when the client cannot be constructed,
    # and the answer must not depend on the client object's shape.
    creds: dict = {}
    try:
        loaded = json.loads(_CREDS_PATH.read_text())
        if isinstance(loaded, dict):
            creds = loaded
    except Exception:  # noqa: BLE001
        pass
    site_url = creds.get("site_url")

    try:
        client = WPClient.from_credentials_file(_CREDS_PATH)
    except WPAuthError as exc:
        return _state(site_url=site_url, message=_redact(
            f"The stored credentials are unusable: {exc}", creds.get("password")))

    # A connection TEST must do the round trip it claims to. `login()` returns
    # early on a session-cache hit — restoring a cookie and a nonce, never
    # touching the password — and that cache lives 10 hours. Without this, an
    # operator who changed the WordPress password would click Test connection
    # and be told "Connected. This account can run the fixes and the
    # configuration audit." on the strength of a cookie (P6). Every other caller
    # of WPClient legitimately wants the cache; this one must not have it.
    invalidate_session(creds.get("login_url") or "", creds.get("username") or "")

    try:
        async with client as wp:
            me = await wp.get("users/me?context=edit")
    except WPAuthError as exc:
        # WA4's diagnosis reaches the screen verbatim. It names the URL it tried,
        # whether the POST was redirected, and what it cannot tell apart —
        # which is the whole reason this endpoint exists.
        return _state(configured=True, site_url=site_url,
                      message=_redact(str(exc), creds.get("password")))
    except Exception as exc:  # noqa: BLE001
        logger.info("wp_connection_failed", exc_info=True)
        return _state(configured=True, site_url=site_url, message=_redact(
            f"Could not reach {site_url or 'the WordPress site'}: "
            f"{type(exc).__name__}: {exc}", creds.get("password")))

    if me.status_code in (401, 403):
        return _state(configured=True, site_url=site_url, message=(
            "Logged in, but WordPress refused to describe the account "
            f"(HTTP {me.status_code}). The user may lack the capabilities the "
            "fix flows need."))

    if me.status_code != 200:
        # P2: a non-200 here establishes nothing. A 404 in particular means the
        # REST route is wrong or the REST API is disabled — never a pass.
        return _state(configured=True, site_url=site_url, message=(
            f"WordPress returned HTTP {me.status_code} for the account check. "
            "That is not a permissions answer: the REST API may be disabled or "
            "blocked, so nothing was verified."))

    # A 200 is not by itself an answer. A cache interstitial, a WAF challenge or
    # a maintenance page all answer 200 with HTML; parsing that to `{}` made
    # every capability read False and produced a specific, wrong, actionable
    # verdict about the operator's account — rendered in the GREEN box. WA3 set
    # the rule for the audit: a response that establishes nothing must never be
    # reported as a finding (P2/P14). A body with no `id` is not the account
    # description we asked for.
    try:
        body = me.json()
    except Exception:  # noqa: BLE001
        body = None
    if not isinstance(body, dict) or body.get("id") is None:
        return _state(configured=True, site_url=site_url, message=(
            "WordPress answered the account check with something that is not an "
            "account (HTTP 200, but no user object). A cache, a firewall or a "
            "maintenance page may be answering instead of the REST API, so "
            "nothing was verified."))

    caps = {k: bool(v) for k, v in (body.get("capabilities") or {}).items()}
    roles = [str(r) for r in (body.get("roles") or [])]
    can_fix = all(caps.get(c) for c in _FIX_CAPS)
    # An explicit False is an answer; an absent key is not. Only fall back to
    # `manage_options` when the install does not report `activate_plugins` at
    # all — otherwise the fallback would override the real gate with a laxer one.
    if "activate_plugins" in caps:
        can_audit = bool(caps["activate_plugins"])
    else:
        can_audit = bool(caps.get("manage_options"))

    if can_fix and can_audit:
        message = "Connected. This account can run the fixes and the configuration audit."
    elif can_fix:
        message = ("Connected. This account can run the fixes, but not the "
                   "configuration audit — listing plugins needs an administrator.")
    else:
        missing = ", ".join(c for c in _FIX_CAPS if not caps.get(c)) or "the required capabilities"
        message = f"Connected, but this account is missing {missing}, so the fixes will fail."

    return _state(
        configured=True,
        authenticated=True,
        site_url=site_url,
        user_id=body.get("id"),
        roles=roles,
        # Only the capabilities the app depends on — the raw list is ~60 keys of
        # WordPress internals and nothing here reads them.
        capabilities={c: bool(caps.get(c)) for c in (*_FIX_CAPS, *_AUDIT_CAPS)},
        can_run_fixes=can_fix,
        can_run_wp_audit=can_audit,
        message=message,
    )
