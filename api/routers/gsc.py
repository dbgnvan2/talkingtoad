"""GSC OAuth + data ingest endpoints (M6.1 + M6.4).

Prefix: /api/gsc
Auth: all endpoints require bearer token (require_auth dependency).
Opt-in: when GSC_OAUTH_CLIENT_ID / _SECRET / _REDIRECT_URI are unset,
every endpoint returns 503 and TalkingToad behaves exactly as before.

Credential storage: encrypted with Fernet (AI_CREDS_ENCRYPTION_KEY)
when configured; raw JSON in local dev (single-tenant).
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from api.models.performance import PerformanceRecord
from api.services.auth import require_auth
from api.services.gsc_client import build_flow, fetch_page_performance, list_properties
from api.services.refresh_trigger import ReviewFlag, evaluate_refresh

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/gsc", dependencies=[Depends(require_auth)])

# In-memory PKCE state store (single-tenant; keyed by OAuth state param).
_pkce_store: dict[str, dict] = {}


# ── Helpers ───────────────────────────────────────────────────────────────────


def _gsc_env_configured() -> bool:
    """Check if all required GSC env vars are set."""
    return all([
        os.environ.get("GSC_OAUTH_CLIENT_ID"),
        os.environ.get("GSC_OAUTH_CLIENT_SECRET"),
        os.environ.get("GSC_OAUTH_REDIRECT_URI"),
    ])


def _require_gsc_configured() -> None:
    """Raise 503 if GSC env vars are not set (opt-in guarantee)."""
    if not _gsc_env_configured():
        raise HTTPException(status_code=503, detail="GSC not configured")


def _get_store():
    """Return the app-level job store."""
    from api.main import _store
    return _store


def _get_encryption_key() -> Optional[str]:
    """Get encryption key for credential storage, or None."""
    return os.environ.get("AI_CREDS_ENCRYPTION_KEY")


def _encrypt_creds(creds_json: str) -> str:
    """Encrypt credentials using Fernet if key available."""
    key = _get_encryption_key()
    if not key:
        return creds_json  # No encryption configured; store raw (local dev)
    from cryptography.fernet import Fernet
    f = Fernet(key.encode())
    return f.encrypt(creds_json.encode()).decode()


def _decrypt_creds(encrypted: str) -> str:
    """Decrypt credentials using Fernet if key available."""
    key = _get_encryption_key()
    if not key:
        return encrypted
    from cryptography.fernet import Fernet
    f = Fernet(key.encode())
    return f.decrypt(encrypted.encode()).decode()


# Credential persistence — uses the job store's key-value surface.
# Single-tenant: one credential set for the whole app.

_creds_cache: dict[str, str] = {}  # in-memory fallback for test/dev


def _store_creds(creds_json: str, account_email: Optional[str] = None) -> None:
    """Store encrypted credentials plus the connected account email (best-effort).

    The account email is stored in a separate cache slot; legacy stored creds
    (written before this field existed) leave it absent -> _load_account_email
    returns None. Existing callers of _load_creds() are unaffected.
    """
    encrypted = _encrypt_creds(creds_json)
    _creds_cache["gsc_credentials"] = encrypted
    if account_email:
        _creds_cache["gsc_account_email"] = account_email
    else:
        _creds_cache.pop("gsc_account_email", None)


def _load_creds() -> Optional[str]:
    """Load and decrypt credentials."""
    encrypted = _creds_cache.get("gsc_credentials")
    if not encrypted:
        return None
    return _decrypt_creds(encrypted)


def _load_account_email() -> Optional[str]:
    """Return the connected Google account email, or None (legacy/unknown)."""
    return _creds_cache.get("gsc_account_email")


def _fetch_account_email(flow) -> Optional[str]:
    """Best-effort: derive the connected account email after fetch_token.

    Wrapped entirely so ANY failure returns None — the connect flow must still
    succeed and store creds even if the email cannot be identified.
    """
    try:
        import google.auth.transport.requests
        from google.oauth2 import id_token

        client_id = os.environ.get("GSC_OAUTH_CLIENT_ID", "")
        id_tok = getattr(flow.credentials, "id_token", None)
        if id_tok and client_id:
            info = id_token.verify_oauth2_token(
                id_tok,
                google.auth.transport.requests.Request(),
                client_id,
            )
            email = info.get("email")
            if email:
                return email
    except Exception as e:  # noqa: BLE001 — best-effort, never break connect
        logger.info("Could not identify GSC account email (continuing): %s", e)
    return None


def _delete_creds() -> None:
    """Remove stored credentials."""
    _creds_cache.pop("gsc_credentials", None)
    _creds_cache.pop("gsc_account_email", None)


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/connect")
async def gsc_connect():
    """Initiate GSC OAuth flow — redirects to Google consent screen."""
    _require_gsc_configured()

    flow = build_flow()
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        # "select_account" forces Google to always show the account picker so
        # the user knows (and can change) which Google account they connect as —
        # no silent reuse of the browser's default account.
        prompt="select_account consent",
    )

    # Persist PKCE code_verifier + state (CRITICAL: Google rejects the
    # exchange with "Missing code verifier" if this isn't restored).
    _pkce_store[state] = {
        "code_verifier": flow.code_verifier,
        "state": state,
    }

    return RedirectResponse(url=authorization_url, status_code=302)


@router.get("/callback")
async def gsc_callback(
    request: Request, code: str, state: str, error: Optional[str] = None
):
    """Handle OAuth callback — exchange code for credentials."""
    if error:
        raise HTTPException(status_code=400, detail=f"OAuth error: {error}")

    # Restore PKCE state
    stored = _pkce_store.pop(state, None)
    if not stored:
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    flow = build_flow(state=state)
    flow.code_verifier = stored["code_verifier"]

    flow.fetch_token(code=code)

    # Best-effort: identify the connected account email. MUST NOT break connect.
    # _fetch_account_email is internally guarded; the call site is guarded too so
    # even an unexpected failure here can never prevent creds from being stored.
    try:
        account_email = _fetch_account_email(flow)
    except Exception as e:  # noqa: BLE001 — connect must survive any email failure
        logger.info("Account-email fetch failed (continuing): %s", e)
        account_email = None

    # Store credentials (never log token values)
    creds_json = flow.credentials.to_json()
    _store_creds(creds_json, account_email=account_email)

    return HTMLResponse(
        content="<h1>GSC Connected!</h1><p>You can close this window.</p>",
        status_code=200,
    )


@router.get("/status")
async def gsc_status():
    """Check GSC connection status and list properties."""
    _require_gsc_configured()

    creds_json = _load_creds()
    if not creds_json:
        return {
            "connected": False,
            "properties": [],
            "configured": True,
            "account_email": None,
        }

    try:
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_info(json.loads(creds_json))
        properties = list_properties(creds)
        return {
            "connected": True,
            "properties": properties,
            "configured": True,
            "account_email": _load_account_email(),
        }
    except Exception as e:
        logger.error("Failed to list GSC properties: %s", e)
        return {
            "connected": False,
            "properties": [],
            "configured": True,
            "account_email": None,
        }


@router.post("/disconnect")
async def gsc_disconnect():
    """Remove stored GSC credentials."""
    _require_gsc_configured()
    _delete_creds()
    return {"status": "disconnected"}


class IngestResponse(BaseModel):
    ingested: int
    period: str


@router.post("/ingest")
async def gsc_ingest(site_url: str, job_id: str, days: int = 30):
    """Fetch GSC data and store as PerformanceRecords in the ledger."""
    _require_gsc_configured()

    creds_json = _load_creds()
    if not creds_json:
        raise HTTPException(status_code=401, detail="GSC not connected")

    from google.oauth2.credentials import Credentials
    creds = Credentials.from_authorized_user_info(json.loads(creds_json))

    try:
        rows = await fetch_page_performance(creds, site_url, days=days)
    except Exception as e:
        logger.error("GSC fetch failed: %s", e)
        raise HTTPException(status_code=502, detail=f"GSC API error: {str(e)}")

    period = time.strftime("%Y-%m")
    store = _get_store()
    records = []
    for row in rows:
        records.append(PerformanceRecord(
            url=row["url"],
            period=period,
            gsc_clicks_mo=row["clicks"],
            gsc_impressions_mo=row["impressions"],
            gsc_ctr_mo=row["ctr"],
            gsc_avg_position_mo=row["position"],
        ))

    await store.save_performance_records(records)

    return IngestResponse(ingested=len(records), period=period)


class PerformanceResponse(BaseModel):
    records: list[dict]
    review_flag: Optional[dict] = None


@router.get("/performance")
async def gsc_performance(
    url: str, job_id: Optional[str] = None, health_score: int = 50
):
    """Get GSC performance data + ReviewFlag for a URL.

    health_score defaults to 50 if not provided (the caller should pass the
    page's computed health score for accurate Vulnerable Star / Hidden Gem
    flagging).
    """
    _require_gsc_configured()

    store = _get_store()
    records = await store.get_performance_records(url=url)

    review_flag = None
    if records:
        flag = evaluate_refresh(
            records=records,
            health_score=health_score,
            today=date.today(),
        )
        review_flag = {"flagged": flag.flagged, "reasons": flag.reasons}

    return PerformanceResponse(
        records=[r.model_dump() for r in records],
        review_flag=review_flag,
    )
