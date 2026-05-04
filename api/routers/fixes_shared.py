"""Shared utilities, models, and helpers for Fix Manager routers."""

from __future__ import annotations

import json as _json_mod
import logging
from pathlib import Path
from urllib.parse import urlparse
from pydantic import BaseModel
from fastapi.responses import JSONResponse

from api.models.fix import Fix
from api.services.error_responses import _err

logger = logging.getLogger(__name__)

_CREDS_PATH = Path("wp-credentials.json")


# ── Request/Response Models ────────────────────────────────────────────────

class WPCredentials(BaseModel):
    site_url: str
    login_url: str
    username: str
    password: str


class UpdateImageMetaBody(BaseModel):
    wp_credentials: WPCredentials | None = None


class MarkAnchorFixedRequest(BaseModel):
    job_id: str
    page_url: str
    link_href: str


class MarkAnchorFixedResponse(BaseModel):
    success: bool
    remaining: int
    error: str | None = None


class VerifyResult(BaseModel):
    url: str
    previous_status: int | None = None
    current_status: int | None = None
    is_fixed: bool
    error: str | None = None


class VerifyBrokenLinksResponse(BaseModel):
    total: int
    checked: int
    fixed: int
    still_broken: int
    errors: int
    results: list[VerifyResult]


class MarkBrokenLinkFixedRequest(BaseModel):
    job_id: str
    source_url: str
    target_url: str


class MarkBrokenLinkFixedResponse(BaseModel):
    success: bool
    remaining: int
    error: str | None = None


class MarkIssueFixedRequest(BaseModel):
    job_id: str
    page_url: str
    issue_code: str


class MarkIssueFixedResponse(BaseModel):
    success: bool
    error: str | None = None


# ── Helper Functions ──────────────────────────────────────────────────────

def get_store():
    """Dependency injection for job store."""
    from api.main import _store
    return _store


def _get_wp_creds_domain() -> str | None:
    """Return the netloc from wp-credentials.json's site_url, or None."""
    if not _CREDS_PATH.exists():
        return None
    try:
        with open(_CREDS_PATH) as f:
            creds = _json_mod.load(f)
        return urlparse(creds.get("site_url", "")).netloc
    except (FileNotFoundError, _json_mod.JSONDecodeError) as e:
        logger.debug(f"Could not load WordPress domain from credentials: {e}")
        return None


def _domain_mismatch_error(target_domain: str, creds_domain: str) -> JSONResponse:
    """Return a standard DOMAIN_MISMATCH error response."""
    return _err(
        "DOMAIN_MISMATCH",
        f"WordPress credentials are for {creds_domain}, but you are working on "
        f"{target_domain}. Update wp-credentials.json or provide credentials for "
        f"{target_domain}.",
        403,
    )


async def _validate_wp_domain_for_job(store, job_id: str) -> JSONResponse | None:
    """Check that the WP credentials domain matches the crawl job's target domain.

    Returns a JSONResponse error if there's a mismatch, or None if OK.
    """
    creds_domain = _get_wp_creds_domain()
    if not creds_domain:
        return None  # no creds file — let downstream handle FileNotFoundError

    job = await store.get_job(job_id)
    if not job:
        return None  # let downstream handle missing job

    job_domain = urlparse(job.target_url).netloc
    if job_domain != creds_domain:
        return _domain_mismatch_error(job_domain, creds_domain)
    return None


def _validate_wp_domain_for_url(url: str) -> JSONResponse | None:
    """Check that the WP credentials domain matches a page/image URL's domain.

    Returns a JSONResponse error if there's a mismatch, or None if OK.
    """
    creds_domain = _get_wp_creds_domain()
    if not creds_domain:
        return None

    url_domain = urlparse(url).netloc
    if not url_domain:
        return None  # relative URL — can't validate

    if url_domain != creds_domain:
        return _domain_mismatch_error(url_domain, creds_domain)
    return None


def _row_to_fix(row: dict) -> Fix:
    """Convert database row dict to Fix model."""
    return Fix(
        id=row["id"],
        job_id=row["job_id"],
        issue_code=row["issue_code"],
        page_url=row["page_url"],
        wp_post_id=row.get("wp_post_id"),
        wp_post_type=row.get("wp_post_type"),
        field=row["field"],
        label=row["label"],
        current_value=row.get("current_value"),
        proposed_value=row.get("proposed_value", ""),
        status=row.get("status", "pending"),
        error=row.get("error"),
        applied_at=row.get("applied_at"),
    )
