"""Title-related fix endpoints (v2.3 M0.12.1).

Endpoints:
- GET  /api/fixes/predefined-codes      — list of WP-automatable issue codes
- POST /api/fixes/bulk-trim-titles      — trim site-name suffix from all titles in a job
- POST /api/fixes/trim-title-one        — trim site-name suffix from one page's title

These endpoints were documented in CLAUDE.md and the v1.9 release notes but
were never registered after the v2.0 fixes.py split. The service-layer code
(api/services/wp_title_fixer.py) survived the split — this router restores
the HTTP wiring.

Every WP-touching endpoint validates that the credentials file's domain
matches the crawl job's target domain (or the request URL's domain) before
opening a WPClient, per the v1.9.4 cross-site protection model.
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from api.routers.fixes_shared import (
    _CREDS_PATH,
    _validate_wp_domain_for_job,
    _validate_wp_domain_for_url,
    get_store,
)
from api.services.auth import require_auth
from api.services.error_responses import _err
from api.services.wp_client import WPClient, WPAuthError
from api.services.wp_fixer import detect_seo_plugin
from api.services.wp_shared import get_fixable_codes
from api.services.wp_title_fixer import bulk_trim_titles, trim_title_one

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/fixes", dependencies=[Depends(require_auth)])


# ---------------------------------------------------------------------------
# GET /predefined-codes
# ---------------------------------------------------------------------------

@router.get("/predefined-codes", response_model=None)
async def list_predefined_codes() -> dict:
    """Return the set of issue codes the WP automation engine knows how to fix.

    No auth-bypass on this one — it returns metadata that informs the UI
    about which fix buttons to show. Returned as a sorted list so the response
    is deterministic.
    """
    codes = sorted(get_fixable_codes())
    return {"codes": codes, "count": len(codes)}


# ---------------------------------------------------------------------------
# POST /bulk-trim-titles
# ---------------------------------------------------------------------------

@router.post("/bulk-trim-titles", response_model=None)
async def bulk_trim_titles_endpoint(
    job_id: str = Query(..., description="Job ID whose pages will have their titles trimmed"),
    store=Depends(get_store),
) -> dict | JSONResponse:
    """Strip the site-name suffix from SEO titles across all pages in a job.

    Reads pages from the crawl job, opens a WPClient against the credentials
    file (validated against the job's domain), detects the active SEO plugin
    (Yoast / Rank Math), and runs `wp_title_fixer.bulk_trim_titles`.
    """
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", f"No job with id {job_id}", 404)

    if not _CREDS_PATH.exists():
        return _err(
            "NO_CREDENTIALS",
            "wp-credentials.json not found. Create it with site_url, login_url, "
            "username, password.",
            400,
        )

    domain_err = await _validate_wp_domain_for_job(store, job_id)
    if domain_err is not None:
        return domain_err

    pages = await store.get_pages(job_id)
    page_payload = [
        {"page_url": p.url, "title": p.title}
        for p in pages
        if p.title is not None and p.status_code == 200
    ]

    if not page_payload:
        return {"applied": 0, "skipped": 0, "results": []}

    try:
        async with WPClient.from_credentials_file(_CREDS_PATH) as wp:
            seo_plugin = await detect_seo_plugin(wp)
            results = await bulk_trim_titles(wp, page_payload, seo_plugin)
    except WPAuthError as exc:
        return _err("WP_AUTH_FAILED", str(exc), 401)
    except Exception as exc:
        logger.exception("bulk_trim_titles_failed", extra={"job_id": job_id})
        return _err("BULK_TRIM_FAILED", str(exc), 500)

    applied = sum(1 for r in results if r.get("success"))
    skipped = sum(1 for r in results if not r.get("success"))
    return {"applied": applied, "skipped": skipped, "results": results}


# ---------------------------------------------------------------------------
# POST /trim-title-one
# ---------------------------------------------------------------------------

@router.post("/trim-title-one", response_model=None)
async def trim_title_one_endpoint(
    page_url: str = Query(..., description="Full URL of the page whose title to trim"),
) -> dict | JSONResponse:
    """Strip the site-name suffix from a single page's SEO title.

    The credentials file's domain must match the requested page_url's domain,
    enforced by `_validate_wp_domain_for_url` (per v1.9.4 cross-site protection).
    """
    if not _CREDS_PATH.exists():
        return _err(
            "NO_CREDENTIALS",
            "wp-credentials.json not found.",
            400,
        )

    domain_err = _validate_wp_domain_for_url(page_url)
    if domain_err is not None:
        return domain_err

    try:
        async with WPClient.from_credentials_file(_CREDS_PATH) as wp:
            seo_plugin = await detect_seo_plugin(wp)
            result = await trim_title_one(wp, page_url, seo_plugin)
    except WPAuthError as exc:
        return _err("WP_AUTH_FAILED", str(exc), 401)
    except Exception as exc:
        logger.exception("trim_title_one_failed", extra={"page_url": page_url})
        return _err("TRIM_FAILED", str(exc), 500)

    return result
