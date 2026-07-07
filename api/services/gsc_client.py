"""Google Search Console client with OAuth, backoff, and data fetching (M6.1).

Provides:
  - build_flow(): OAuth flow from env-based client config (no JSON file).
  - fetch_page_performance(): GSC searchanalytics query with exponential backoff.
  - list_properties(): Enumerate verified GSC properties.

Tokens/creds are NEVER logged or returned in API responses.
"""

from __future__ import annotations

import os
import time
import logging
from typing import Optional

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

CLIENT_CONFIG = {
    "web": {
        "client_id": os.environ.get("GSC_OAUTH_CLIENT_ID", ""),
        "client_secret": os.environ.get("GSC_OAUTH_CLIENT_SECRET", ""),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [os.environ.get("GSC_OAUTH_REDIRECT_URI", "")],
    }
}

# webmasters.readonly is the functional scope. openid + userinfo.email are
# standard non-sensitive scopes used only to identify which Google account
# connected (surfaced as "Connected as ..." in the panel). Adding them means
# existing users reconnect once to populate the account email; connections
# made before this change keep working (email shows null until reconnect).
SCOPES = [
    "https://www.googleapis.com/auth/webmasters.readonly",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]


def build_flow(state: Optional[str] = None) -> Flow:
    """Build a Google OAuth flow from CLIENT_CONFIG (env-based, no JSON file)."""
    flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES)
    redirect_uri = os.environ.get("GSC_OAUTH_REDIRECT_URI", "")
    flow.redirect_uri = redirect_uri

    # OAUTHLIB_INSECURE_TRANSPORT: only for localhost redirects (oauthlib
    # refuses non-https by default; safe for loopback on dev machine).
    if "localhost" in redirect_uri or "127.0.0.1" in redirect_uri:
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    if state:
        flow.state = state
    return flow


async def fetch_page_performance(
    creds: Credentials, site_url: str, *, days: int = 30
) -> list[dict]:
    """Fetch GSC performance data for pages, with exponential backoff.

    Returns list of dicts with keys: url, clicks, impressions, ctr, position.
    Retries up to 5 times on 429/5xx with exponential delay.
    """
    service = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
    end_date = time.strftime("%Y-%m-%d")
    start_date = time.strftime(
        "%Y-%m-%d", time.localtime(time.time() - days * 86400)
    )

    request_body = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": ["page"],
        "rowLimit": 25000,
    }

    max_retries = 5
    base_delay = 1.0
    response = None

    for attempt in range(max_retries):
        try:
            response = (
                service.searchanalytics()
                .query(siteUrl=site_url, body=request_body)
                .execute()
            )
            break
        except HttpError as e:
            if e.resp.status in (429, 500, 502, 503) and attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    "GSC API retry %d/%d after %.1fs: %s",
                    attempt + 1, max_retries, delay, e,
                )
                time.sleep(delay)
            else:
                raise

    rows = response.get("rows", []) if response else []
    results = []
    for row in rows:
        results.append({
            "url": row["keys"][0],
            "clicks": row.get("clicks", 0),
            "impressions": row.get("impressions", 0),
            "ctr": row.get("ctr", 0.0),
            "position": row.get("position", 0.0),
        })
    return results


def list_properties(creds: Credentials) -> list[dict]:
    """List GSC properties with permission levels.

    Returns list of dicts: [{site_url, permission_level}, ...].
    Prefer siteOwner properties (frontend/caller decides).
    """
    service = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
    response = service.sites().list().execute()
    return [
        {"site_url": site["siteUrl"], "permission_level": site["permissionLevel"]}
        for site in response.get("siteEntry", [])
    ]
