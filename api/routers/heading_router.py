"""Heading-related fix endpoints (v2.3 M0.12.2).

Endpoints:
- GET  /api/fixes/find-heading             search crawled pages for a heading
- GET  /api/fixes/analyze-heading-sources  diagnose where a page's heading lives
- POST /api/fixes/change-heading-level     change H{n} -> H{m} on one page
- POST /api/fixes/change-heading-text      change heading text on one page
- POST /api/fixes/bulk-replace-heading     change H{n} -> H{m} across many pages
- POST /api/fixes/heading-to-bold          convert <h{n}> to <p><strong>

Restoration of routes documented in CLAUDE.md and frontend/src/api.js. Three
of the underlying services (find_heading, bulk_replace_heading,
convert_heading_to_bold) were re-implemented in wp_heading_fixer.py as part
of this milestone — they previously had no backend at all.

Every WP-touching endpoint validates the credentials file's domain against
either the crawl job's target domain or the request URL's domain.
"""

from __future__ import annotations

import logging

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
from api.services.wp_heading_fixer import (
    analyze_heading_sources,
    bulk_replace_heading,
    change_heading_level,
    change_heading_text,
    convert_heading_to_bold,
    find_heading,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/fixes", dependencies=[Depends(require_auth)])


# ---------------------------------------------------------------------------
# GET /find-heading  (no WP, pure store read)
# ---------------------------------------------------------------------------

@router.get("/find-heading", response_model=None)
async def find_heading_endpoint(
    job_id: str = Query(..., description="Job ID whose pages to search"),
    heading_text: str = Query(..., min_length=1, description="Heading text to match"),
    level: int | None = Query(
        None, ge=1, le=6,
        description="Optional: restrict to a specific H level (1-6)",
    ),
    store=Depends(get_store),
) -> dict | JSONResponse:
    """Return every page in *job_id* that contains a heading matching *heading_text*.

    Text comparison is fuzzy (smart quotes/dashes normalized, whitespace
    collapsed, case-insensitive). No WP API call; reads `headings_outline`
    from crawled pages.
    """
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", f"No job with id {job_id}", 404)

    matches = await find_heading(store, job_id, heading_text, level)
    return {"matches": matches, "count": len(matches)}


# ---------------------------------------------------------------------------
# GET /analyze-heading-sources
# ---------------------------------------------------------------------------

@router.get("/analyze-heading-sources", response_model=None)
async def analyze_heading_sources_endpoint(
    page_url: str = Query(..., description="URL of the page to analyze"),
    job_id: str | None = Query(
        None,
        description="Optional: job_id to source the crawled headings list from",
    ),
    store=Depends(get_store),
) -> dict | JSONResponse:
    """Identify where each heading on *page_url* lives (post content, reusable
    block, widget, template part, theme PHP, etc.) so the UI can show which
    are user-fixable.
    """
    if not _CREDS_PATH.exists():
        return _err("NO_CREDENTIALS", "wp-credentials.json not found.", 400)

    domain_err = _validate_wp_domain_for_url(page_url)
    if domain_err is not None:
        return domain_err

    # Crawled headings for this page — used for fuzzy matching against WP content.
    crawled_headings: list[dict] = []
    if job_id:
        pages = await store.get_pages(job_id)
        for p in pages:
            if p.url == page_url or p.url.rstrip("/") == page_url.rstrip("/"):
                crawled_headings = p.headings_outline or []
                break

    try:
        async with WPClient.from_credentials_file(_CREDS_PATH) as wp:
            results = await analyze_heading_sources(wp, page_url, crawled_headings)
    except WPAuthError as exc:
        return _err("WP_AUTH_FAILED", str(exc), 401)
    except Exception as exc:
        logger.exception("analyze_heading_sources_failed", extra={"page_url": page_url})
        return _err("ANALYZE_FAILED", str(exc), 500)

    return {"headings": results, "count": len(results)}


# ---------------------------------------------------------------------------
# POST /change-heading-level
# ---------------------------------------------------------------------------

@router.post("/change-heading-level", response_model=None)
async def change_heading_level_endpoint(
    page_url: str = Query(..., description="URL of the page containing the heading"),
    heading_text: str = Query(..., min_length=1),
    from_level: int = Query(..., ge=1, le=6),
    to_level: int = Query(..., ge=1, le=6),
) -> dict | JSONResponse:
    """Change the H level of a specific heading on one page."""
    if not _CREDS_PATH.exists():
        return _err("NO_CREDENTIALS", "wp-credentials.json not found.", 400)

    domain_err = _validate_wp_domain_for_url(page_url)
    if domain_err is not None:
        return domain_err

    try:
        async with WPClient.from_credentials_file(_CREDS_PATH) as wp:
            result = await change_heading_level(
                wp, page_url, heading_text, from_level, to_level,
            )
    except WPAuthError as exc:
        return _err("WP_AUTH_FAILED", str(exc), 401)
    except Exception as exc:
        logger.exception("change_heading_level_failed", extra={"page_url": page_url})
        return _err("CHANGE_LEVEL_FAILED", str(exc), 500)

    return result


# ---------------------------------------------------------------------------
# POST /change-heading-text
# ---------------------------------------------------------------------------

@router.post("/change-heading-text", response_model=None)
async def change_heading_text_endpoint(
    page_url: str = Query(..., description="URL of the page containing the heading"),
    old_text: str = Query(..., min_length=1),
    new_text: str = Query(..., min_length=1),
    level: int = Query(1, ge=1, le=6),
) -> dict | JSONResponse:
    """Change the text of a specific heading on one page."""
    if not _CREDS_PATH.exists():
        return _err("NO_CREDENTIALS", "wp-credentials.json not found.", 400)

    domain_err = _validate_wp_domain_for_url(page_url)
    if domain_err is not None:
        return domain_err

    try:
        async with WPClient.from_credentials_file(_CREDS_PATH) as wp:
            result = await change_heading_text(
                wp, page_url, old_text, new_text, level,
            )
    except WPAuthError as exc:
        return _err("WP_AUTH_FAILED", str(exc), 401)
    except Exception as exc:
        logger.exception("change_heading_text_failed", extra={"page_url": page_url})
        return _err("CHANGE_TEXT_FAILED", str(exc), 500)

    return result


# ---------------------------------------------------------------------------
# POST /bulk-replace-heading
# ---------------------------------------------------------------------------

@router.post("/bulk-replace-heading", response_model=None)
async def bulk_replace_heading_endpoint(
    job_id: str = Query(..., description="Job ID whose pages to process"),
    heading_text: str = Query(..., min_length=1),
    from_level: int = Query(..., ge=1, le=6),
    to_level: int | None = Query(
        None, ge=1, le=6,
        description="Target H level. Omit to preview matches without changing anything.",
    ),
    store=Depends(get_store),
) -> dict | JSONResponse:
    """Change a heading's level across every matching page in a job.

    When *to_level* is omitted, the endpoint returns the list of pages that
    would be affected, without touching WP. Useful for the UI to show "this
    will affect N pages" before the user confirms.
    """
    job = await store.get_job(job_id)
    if job is None:
        return _err("JOB_NOT_FOUND", f"No job with id {job_id}", 404)

    if not _CREDS_PATH.exists():
        return _err("NO_CREDENTIALS", "wp-credentials.json not found.", 400)

    domain_err = await _validate_wp_domain_for_job(store, job_id)
    if domain_err is not None:
        return domain_err

    # Preview mode — no WP needed at all.
    if to_level is None:
        try:
            # The service handles the to_level=None preview branch internally,
            # but we still need a WPClient placeholder for the signature.
            # Use a context manager but won't actually call WP.
            async with WPClient.from_credentials_file(_CREDS_PATH) as wp:
                result = await bulk_replace_heading(
                    wp, store, job_id, heading_text, from_level, None,
                )
        except WPAuthError as exc:
            return _err("WP_AUTH_FAILED", str(exc), 401)
        except Exception as exc:
            logger.exception("bulk_replace_preview_failed", extra={"job_id": job_id})
            return _err("BULK_REPLACE_FAILED", str(exc), 500)
        return result

    try:
        async with WPClient.from_credentials_file(_CREDS_PATH) as wp:
            result = await bulk_replace_heading(
                wp, store, job_id, heading_text, from_level, to_level,
            )
    except WPAuthError as exc:
        return _err("WP_AUTH_FAILED", str(exc), 401)
    except Exception as exc:
        logger.exception("bulk_replace_failed", extra={"job_id": job_id})
        return _err("BULK_REPLACE_FAILED", str(exc), 500)

    return result


# ---------------------------------------------------------------------------
# POST /heading-to-bold
# ---------------------------------------------------------------------------

@router.post("/heading-to-bold", response_model=None)
async def heading_to_bold_endpoint(
    page_url: str = Query(..., description="URL of the page containing the heading"),
    heading_text: str = Query(..., min_length=1),
    level: int = Query(4, ge=1, le=6, description="H level the heading currently is at"),
) -> dict | JSONResponse:
    """Convert a specific heading to bold paragraph (`<p><strong>...</strong></p>`).

    Useful when the heading is structurally wrong (e.g. an H4 sprinkled in
    body text for emphasis — should be inline emphasis, not a heading).
    """
    if not _CREDS_PATH.exists():
        return _err("NO_CREDENTIALS", "wp-credentials.json not found.", 400)

    domain_err = _validate_wp_domain_for_url(page_url)
    if domain_err is not None:
        return domain_err

    try:
        async with WPClient.from_credentials_file(_CREDS_PATH) as wp:
            result = await convert_heading_to_bold(
                wp, page_url, heading_text, level,
            )
    except WPAuthError as exc:
        return _err("WP_AUTH_FAILED", str(exc), 401)
    except Exception as exc:
        logger.exception("heading_to_bold_failed", extra={"page_url": page_url})
        return _err("HEADING_TO_BOLD_FAILED", str(exc), 500)

    return result
